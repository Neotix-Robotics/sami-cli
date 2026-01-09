"""Dataset upload functionality."""

import os
import json
import struct
import shutil
import mimetypes
import subprocess
import tempfile
from pathlib import Path
from typing import List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from tqdm import tqdm

from .auth import SamiAuth
from .models import Dataset
from .exceptions import UploadError, ValidationError


def check_ffmpeg_available() -> bool:
    """Check if ffmpeg is available in PATH."""
    return shutil.which("ffmpeg") is not None


def needs_faststart(video_path: Path) -> bool:
    """Check if video needs faststart (moov atom at end).

    Returns True if moov atom comes after mdat atom, meaning
    the video is not optimized for web streaming.
    """
    try:
        with open(video_path, 'rb') as f:
            moov_offset = None
            mdat_offset = None

            while True:
                header = f.read(8)
                if len(header) < 8:
                    break

                size = struct.unpack('>I', header[:4])[0]
                atom_type = header[4:8].decode('latin-1', errors='ignore')
                current_offset = f.tell() - 8

                if atom_type == 'moov':
                    moov_offset = current_offset
                elif atom_type == 'mdat':
                    mdat_offset = current_offset

                if size == 0:
                    break
                if size == 1:
                    # 64-bit size
                    extended = f.read(8)
                    if len(extended) < 8:
                        break
                    size = struct.unpack('>Q', extended)[0]
                    f.seek(current_offset + size)
                else:
                    f.seek(current_offset + size)

            # If moov comes after mdat, needs faststart
            if moov_offset is not None and mdat_offset is not None:
                return moov_offset > mdat_offset

            return False
    except Exception:
        # If we can't parse, assume it needs processing
        return True


def apply_faststart(video_path: Path) -> bool:
    """Apply faststart to video by remuxing with ffmpeg.

    This moves the moov atom to the beginning of the file
    without re-encoding (lossless, fast operation).

    Returns True if successful, False otherwise.
    """
    temp_path = video_path.with_suffix('.tmp.mp4')

    try:
        result = subprocess.run(
            [
                'ffmpeg', '-i', str(video_path),
                '-c', 'copy',
                '-movflags', '+faststart',
                '-y',
                '-loglevel', 'error',
                str(temp_path)
            ],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout per video
        )

        if result.returncode == 0 and temp_path.exists():
            # Replace original with processed file
            temp_path.replace(video_path)
            return True
        else:
            # Clean up failed attempt
            if temp_path.exists():
                temp_path.unlink()
            return False

    except subprocess.TimeoutExpired:
        if temp_path.exists():
            temp_path.unlink()
        return False
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        return False


def process_videos_for_web(video_files: List[Tuple[Path, str, str, int]]) -> Tuple[int, int]:
    """Process video files to ensure web compatibility.

    Checks each video for faststart optimization and applies it if needed.

    Args:
        video_files: List of (absolute_path, relative_path, content_type, size) tuples

    Returns:
        Tuple of (processed_count, failed_count)
    """
    if not video_files:
        return 0, 0

    if not check_ffmpeg_available():
        print("  ⚠ ffmpeg not found - skipping video optimization")
        print("    Videos may not play in browser if not properly encoded")
        return 0, 0

    videos_needing_fix = []

    # First pass: check which videos need fixing
    print("  Checking video web compatibility...")
    for abs_path, rel_path, _, _ in video_files:
        if needs_faststart(abs_path):
            videos_needing_fix.append((abs_path, rel_path))

    if not videos_needing_fix:
        print("  ✓ All videos are web-optimized")
        return 0, 0

    print(f"  Processing {len(videos_needing_fix)} videos for web streaming...")

    processed = 0
    failed = 0

    with tqdm(total=len(videos_needing_fix), desc="  Optimizing", unit="videos") as pbar:
        for abs_path, rel_path in videos_needing_fix:
            if apply_faststart(abs_path):
                processed += 1
            else:
                failed += 1
                tqdm.write(f"    ⚠ Failed to process: {rel_path}")
            pbar.update(1)

    if processed > 0:
        print(f"  ✓ Optimized {processed} videos for web streaming")
    if failed > 0:
        print(f"  ⚠ Failed to optimize {failed} videos")

    return processed, failed


def validate_lerobot_structure(path: Path, strict: bool = True) -> dict:
    """Validate that the path contains a valid LeRobot dataset.

    Performs comprehensive validation including:
    - Required metadata fields
    - Video features have corresponding video files
    - Data files exist if data_path is specified
    - Episode metadata exists

    Args:
        path: Path to the LeRobot dataset
        strict: If True, raise errors for missing data/videos.
                If False, only warn (for partial datasets).

    Returns the parsed info.json content if valid.
    """
    warnings = []
    info_path = path / "meta" / "info.json"
    if not info_path.exists():
        raise ValidationError(f"Missing meta/info.json at {path}")

    with open(info_path) as f:
        info = json.load(f)

    # Check required fields
    required_fields = ["total_episodes", "total_frames", "fps"]
    for field in required_fields:
        if field not in info:
            raise ValidationError(f"meta/info.json missing required field: {field}")

    # Validate features exist
    features = info.get("features", {})
    if not features:
        raise ValidationError("meta/info.json missing 'features' field")

    # Extract video features (dtype == "video")
    video_features = {
        key: feat for key, feat in features.items()
        if feat.get("dtype") == "video"
    }

    # Validate video directories and files exist for each video feature
    if video_features:
        videos_dir = path / "videos"
        if not videos_dir.exists():
            msg = (
                f"Dataset has {len(video_features)} video features but 'videos/' directory is missing. "
                f"Expected video keys: {list(video_features.keys())}"
            )
            if strict:
                raise ValidationError(msg)
            warnings.append(msg)
        else:
            # Use video_path template from metadata to find videos
            video_path_template = info.get("video_path", "")
            missing_videos = []
            empty_videos = []

            for video_key in video_features.keys():
                found_videos = False

                if video_path_template:
                    # Build expected path from template: videos/chunk-{chunk:03d}/{video_key}/episode_{episode:06d}.mp4
                    # Replace {video_key} and check if directory exists with any chunk
                    test_path = video_path_template.replace("{video_key}", video_key)
                    # Extract the directory portion (remove episode filename pattern)
                    dir_parts = test_path.split("/")[:-1]  # Remove filename
                    # Try to find matching directory with chunk-000
                    test_dir = "/".join(dir_parts).format(chunk=0)
                    video_dir = path / test_dir
                    if video_dir.exists():
                        mp4_files = list(video_dir.glob("*.mp4"))
                        if mp4_files:
                            found_videos = True

                if not found_videos:
                    # Fallback: try flat structure videos/{video_key}/
                    video_key_dir = videos_dir / video_key
                    if video_key_dir.exists():
                        mp4_files = list(video_key_dir.rglob("*.mp4"))
                        if mp4_files:
                            found_videos = True

                if not found_videos:
                    # Fallback: try nested structure videos/chunk-*/{video_key as path}/
                    nested_path = video_key.replace(".", "/")
                    for chunk_dir in videos_dir.glob("chunk-*"):
                        nested_video_dir = chunk_dir / nested_path
                        if nested_video_dir.exists():
                            mp4_files = list(nested_video_dir.glob("*.mp4"))
                            if mp4_files:
                                found_videos = True
                                break

                if not found_videos:
                    # Last fallback: check if any videos exist at all
                    all_mp4s = list(videos_dir.rglob("*.mp4"))
                    if all_mp4s:
                        found_videos = True
                    else:
                        missing_videos.append(video_key)

            if missing_videos:
                msg = (
                    f"Missing video directories for features: {missing_videos}. "
                    f"Expected directories under 'videos/' for each video feature."
                )
                if strict:
                    raise ValidationError(msg)
                warnings.append(msg)

            if empty_videos:
                msg = (
                    f"No .mp4 files found for video features: {empty_videos}. "
                    f"Video directories exist but contain no video files."
                )
                if strict:
                    raise ValidationError(msg)
                warnings.append(msg)

    # Validate data files exist if data_path is specified (v3.0 format)
    data_path_template = info.get("data_path")
    if data_path_template:
        data_dir = path / "data"
        if not data_dir.exists():
            msg = f"meta/info.json specifies data_path='{data_path_template}' but 'data/' directory is missing"
            if strict:
                raise ValidationError(msg)
            warnings.append(msg)
        else:
            # Check for at least one parquet file
            parquet_files = list(data_dir.rglob("*.parquet"))
            if not parquet_files:
                msg = "'data/' directory exists but contains no .parquet files"
                if strict:
                    raise ValidationError(msg)
                warnings.append(msg)

    # Validate episode metadata exists (v3.0 format)
    episodes_dir = path / "meta" / "episodes"
    if episodes_dir.exists():
        episode_files = list(episodes_dir.rglob("*.parquet"))
        if not episode_files:
            msg = "'meta/episodes/' directory exists but contains no .parquet files"
            if strict:
                raise ValidationError(msg)
            warnings.append(msg)

    # Store warnings in info for reporting
    if warnings:
        info["_validation_warnings"] = warnings

    return info


def get_video_features(info: dict) -> dict:
    """Extract video features from info.json.

    Returns dict of {feature_key: feature_config} for video features.
    """
    features = info.get("features", {})
    return {
        key: feat for key, feat in features.items()
        if feat.get("dtype") == "video"
    }


def list_dataset_files(path: Path) -> List[Tuple[Path, str, str, int]]:
    """List all files in the dataset with their relative paths and sizes.

    Returns list of (absolute_path, relative_path, content_type, size) tuples.
    """
    files = []
    for file_path in path.rglob("*"):
        if file_path.is_file():
            relative = file_path.relative_to(path)
            content_type, _ = mimetypes.guess_type(str(file_path))
            content_type = content_type or "application/octet-stream"
            size = file_path.stat().st_size
            # Use as_posix() to ensure forward slashes on all platforms (Windows fix)
            files.append((file_path, relative.as_posix(), content_type, size))
    return files


def upload_file(
    file_path: Path,
    upload_url: str,
    content_type: str,
    timeout: int = 3600,
    max_retries: int = 3,
) -> None:
    """Upload a single file to S3 using presigned URL.

    Args:
        file_path: Local file path
        upload_url: Presigned S3 URL
        content_type: MIME type
        timeout: Request timeout in seconds (default 1 hour for large files)
        max_retries: Number of retry attempts for failed uploads
    """
    file_size = file_path.stat().st_size
    last_error = None

    for attempt in range(max_retries):
        try:
            with open(file_path, "rb") as f:
                response = requests.put(
                    upload_url,
                    data=f,
                    headers={"Content-Type": content_type},
                    timeout=timeout,
                )

            if response.status_code in (200, 204):
                return  # Success

            last_error = f"HTTP {response.status_code}"
            if response.status_code >= 500:
                # Server error, retry
                continue
            else:
                # Client error, don't retry
                break

        except requests.exceptions.Timeout:
            last_error = f"Timeout after {timeout}s (file size: {file_size / (1024**2):.1f} MB)"
            continue
        except requests.exceptions.ConnectionError as e:
            last_error = f"Connection error: {e}"
            continue
        except Exception as e:
            last_error = str(e)
            break

    raise UploadError(f"Failed to upload {file_path} after {attempt + 1} attempts: {last_error}")


def upload_dataset(
    auth: SamiAuth,
    api_url: str,
    name: str,
    path: str,
    description: str = None,
    task_category: str = None,
    max_workers: int = 4,
    strict: bool = True,
) -> Dataset:
    """Upload a LeRobot dataset to SAMI.

    Args:
        auth: Authenticated SamiAuth instance
        api_url: SAMI API base URL
        name: Dataset name
        path: Path to local LeRobot dataset
        description: Optional description
        task_category: Optional task category
        max_workers: Number of parallel upload threads
        strict: If True, fail on missing videos/data. If False, warn only.

    Returns:
        Dataset object with metadata
    """
    dataset_path = Path(path)
    if not dataset_path.exists():
        raise UploadError(f"Dataset path does not exist: {path}")

    # Validate structure
    print("Validating LeRobot dataset structure...")
    info = validate_lerobot_structure(dataset_path, strict=strict)
    print(f"  ✓ Found {info['total_episodes']:,} episodes, {info['total_frames']:,} frames")
    print(f"  ✓ Format version: {info.get('codebase_version', 'unknown')}")

    # Display validation warnings
    validation_warnings = info.pop("_validation_warnings", [])
    if validation_warnings:
        print(f"\n  ⚠ Validation warnings ({len(validation_warnings)}):")
        for warning in validation_warnings:
            print(f"      - {warning}")
        print("")

    # Report on video features
    video_features = get_video_features(info)
    if video_features:
        print(f"  ✓ Video features ({len(video_features)}):")
        for key, feat in video_features.items():
            shape = feat.get("shape", [])
            codec = feat.get("info", {}).get("video.codec", "unknown")
            print(f"      - {key}: {shape} ({codec})")

    # List files
    print("Scanning dataset files...")
    files = list_dataset_files(dataset_path)
    total_size = sum(f[3] for f in files)

    # Categorize files by type
    video_files = [(p, r, c, s) for p, r, c, s in files if r.startswith("videos/") and r.endswith(".mp4")]
    data_files = [(p, r, c, s) for p, r, c, s in files if r.startswith("data/") and r.endswith(".parquet")]
    meta_files = [(p, r, c, s) for p, r, c, s in files if r.startswith("meta/")]
    other_files = [f for f in files if f not in video_files + data_files + meta_files]

    video_size = sum(f[3] for f in video_files)
    data_size = sum(f[3] for f in data_files)

    print(f"  Found {len(files)} files ({total_size / (1024**3):.2f} GB total)")
    print(f"      - {len(video_files)} video files ({video_size / (1024**3):.2f} GB)")
    print(f"      - {len(data_files)} data files ({data_size / (1024**3):.2f} GB)")
    print(f"      - {len(meta_files)} metadata files")
    if other_files:
        print(f"      - {len(other_files)} other files")

    # Process videos for web compatibility (faststart)
    if video_files:
        print("Optimizing videos for web streaming...")
        processed, failed = process_videos_for_web(video_files)
        if processed > 0:
            # Re-scan to get updated file sizes after processing
            files = list_dataset_files(dataset_path)
            video_files = [(p, r, c, s) for p, r, c, s in files if r.startswith("videos/") and r.endswith(".mp4")]
            total_size = sum(f[3] for f in files)

    # Warn about large video files (>1GB may have issues with presigned URLs)
    large_files = [(r, s) for _, r, _, s in files if s > 1024**3]
    if large_files:
        print(f"\n  ⚠ Warning: {len(large_files)} files exceed 1GB:")
        for rel_path, size in large_files[:5]:
            print(f"      - {rel_path}: {size / (1024**3):.2f} GB")
        if len(large_files) > 5:
            print(f"      ... and {len(large_files) - 5} more")
        print("    Large files may take longer to upload and could timeout.")
        print("")

    # Warn about very large files (>5GB requires multipart upload)
    very_large_files = [(r, s) for _, r, _, s in files if s > 5 * 1024**3]
    if very_large_files:
        print(f"\n  ⚠ ERROR: {len(very_large_files)} files exceed 5GB S3 single-PUT limit:")
        for rel_path, size in very_large_files:
            print(f"      - {rel_path}: {size / (1024**3):.2f} GB")
        raise UploadError(
            f"Files exceeding 5GB require multipart upload which is not yet supported. "
            f"Found {len(very_large_files)} files over 5GB."
        )

    # Create dataset record
    print("Creating dataset record...")
    create_payload = {"name": name}
    if description:
        create_payload["description"] = description
    if task_category:
        create_payload["taskCategory"] = task_category

    response = requests.post(
        f"{api_url}/datasets",
        json=create_payload,
        headers=auth.get_headers(),
    )

    if response.status_code != 201:
        try:
            error = response.json().get("error", {}).get("message", "Unknown error")
        except Exception:
            error = f"HTTP {response.status_code}"
        raise UploadError(f"Failed to create dataset: {error}")

    dataset_data = response.json()["data"]
    dataset_id = dataset_data["id"]
    print(f"  Created dataset: {dataset_id}")

    # Get upload URLs (batch by 500 to avoid request size limits)
    print("Getting upload URLs...")
    all_upload_urls = []
    batch_size = 500

    for i in range(0, len(files), batch_size):
        batch = files[i : i + batch_size]
        file_specs = [
            {"relativePath": rel_path, "contentType": ct, "size": size}
            for _, rel_path, ct, size in batch
        ]

        response = requests.post(
            f"{api_url}/datasets/{dataset_id}/upload-urls",
            json={"files": file_specs},
            headers=auth.get_headers(),
        )

        if response.status_code != 200:
            try:
                error = response.json().get("error", {}).get("message", "Unknown error")
            except Exception:
                error = f"HTTP {response.status_code}"
            raise UploadError(f"Failed to get upload URLs: {error}")

        all_upload_urls.extend(response.json()["data"]["uploadUrls"])
        print(f"  Got URLs for {len(all_upload_urls)}/{len(files)} files")

    # Create mapping of relative path to upload URL
    url_map = {u["relativePath"]: u["uploadUrl"] for u in all_upload_urls}

    # Upload files in parallel
    print(f"Uploading {len(files)} files with {max_workers} workers...")
    failed = []
    uploaded_bytes = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for file_path, rel_path, content_type, size in files:
            upload_url = url_map.get(rel_path)
            if upload_url:
                future = executor.submit(upload_file, file_path, upload_url, content_type)
                futures[future] = (rel_path, size)

        with tqdm(total=len(futures), desc="Uploading", unit="files") as pbar:
            for future in as_completed(futures):
                rel_path, size = futures[future]
                try:
                    future.result()
                    uploaded_bytes += size
                except Exception as e:
                    failed.append((rel_path, str(e)))
                pbar.update(1)

    if failed:
        print(f"Warning: {len(failed)} files failed to upload")
        for path, error in failed[:5]:
            print(f"  - {path}: {error}")
        if len(failed) > 5:
            print(f"  ... and {len(failed) - 5} more")
        raise UploadError(f"Failed to upload {len(failed)} files")

    # Complete upload
    print("Completing upload and parsing metadata...")
    response = requests.post(
        f"{api_url}/datasets/{dataset_id}/complete",
        headers=auth.get_headers(),
    )

    if response.status_code != 200:
        try:
            error = response.json().get("error", {}).get("message", "Unknown error")
        except Exception:
            error = f"HTTP {response.status_code}"
        raise UploadError(f"Failed to complete upload: {error}")

    dataset = Dataset.from_api_response(response.json()["data"])
    print(f"Upload complete! Dataset '{dataset.name}' is ready.")
    return dataset
