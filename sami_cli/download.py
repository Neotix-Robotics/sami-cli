"""Dataset download functionality."""

import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from tqdm import tqdm

from .auth import SamiAuth
from .models import DownloadUrl
from .exceptions import DownloadError, NotFoundError, PermissionDeniedError


def download_file(url: str, output_path: Path, expected_size: int = None) -> None:
    """Download a single file from S3 using presigned URL."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    response = requests.get(url, stream=True)
    if response.status_code != 200:
        raise DownloadError(f"Failed to download: HTTP {response.status_code}")

    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    # Verify size if provided
    if expected_size is not None:
        actual_size = output_path.stat().st_size
        if actual_size != expected_size:
            raise DownloadError(
                f"Size mismatch for {output_path}: expected {expected_size}, got {actual_size}"
            )


def download_dataset(
    auth: SamiAuth,
    api_url: str,
    dataset_id: str,
    output_path: str,
    max_workers: int = 4,
    dataset_format: str = "lerobot",
) -> Path:
    """Download a dataset from SAMI.

    Args:
        auth: Authenticated SamiAuth instance
        api_url: SAMI API base URL
        dataset_id: ID of the dataset to download
        output_path: Local path to download to
        max_workers: Number of parallel download threads
        dataset_format: Format to download ('lerobot' or 'hdf5')

    Returns:
        Path to the downloaded dataset
    """
    output_dir = Path(output_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get download URLs - use format-specific endpoint
    print(f"Getting download URLs for dataset {dataset_id} ({dataset_format} format)...")
    response = requests.get(
        f"{api_url}/datasets/{dataset_id}/download",
        params={"format": dataset_format},
        headers=auth.get_headers(),
    )

    if response.status_code == 404:
        raise NotFoundError(f"Dataset not found: {dataset_id}")
    if response.status_code == 403:
        raise PermissionDeniedError("You do not have download permission for this dataset")
    if response.status_code != 200:
        try:
            error = response.json().get("error", {}).get("message", "Unknown error")
        except Exception:
            error = f"HTTP {response.status_code}"
        raise DownloadError(f"Failed to get download URLs: {error}")

    data = response.json()["data"]
    download_urls = data["downloadUrls"]
    total_files = data["totalFiles"]
    total_size = sum(d["size"] for d in download_urls)

    print(f"  Found {total_files} files ({total_size / (1024**3):.2f} GB)")

    # Download files in parallel
    print(f"Downloading with {max_workers} workers...")
    failed = []
    downloaded_bytes = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for url_info in download_urls:
            file_output = output_dir / url_info["relativePath"]
            future = executor.submit(
                download_file,
                url_info["downloadUrl"],
                file_output,
                url_info["size"]
            )
            futures[future] = (url_info["relativePath"], url_info["size"])

        with tqdm(total=len(futures), desc="Downloading", unit="files") as pbar:
            for future in as_completed(futures):
                rel_path, size = futures[future]
                try:
                    future.result()
                    downloaded_bytes += size
                except Exception as e:
                    failed.append((rel_path, str(e)))
                pbar.update(1)

    if failed:
        print(f"Warning: {len(failed)} files failed to download")
        for path, error in failed[:5]:
            print(f"  - {path}: {error}")
        if len(failed) > 5:
            print(f"  ... and {len(failed) - 5} more")
        raise DownloadError(f"Failed to download {len(failed)} files")

    print(f"Download complete! Dataset saved to: {output_dir}")
    return output_dir
