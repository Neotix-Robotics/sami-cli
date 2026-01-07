"""Unit tests for dataset validation functionality."""

import json
import pytest
from pathlib import Path

from sami_cli.upload import validate_lerobot_structure, list_dataset_files
from sami_cli.exceptions import ValidationError


class TestValidateLerobotStructure:
    """Tests for LeRobot dataset structure validation."""

    @pytest.mark.unit
    def test_valid_dataset(self, temp_dataset_dir: Path):
        """Test validation of a valid LeRobot dataset."""
        info = validate_lerobot_structure(temp_dataset_dir)

        assert info["total_episodes"] == 5
        assert info["total_frames"] == 100
        assert info["fps"] == 30
        assert info["robot_type"] == "TestBot"
        assert "observation.state" in info["features"]
        assert "action" in info["features"]

    @pytest.mark.unit
    def test_missing_info_json(self, invalid_dataset_dir: Path):
        """Test validation fails when info.json is missing."""
        with pytest.raises(ValidationError) as exc_info:
            validate_lerobot_structure(invalid_dataset_dir)

        assert "Missing meta/info.json" in str(exc_info.value)

    @pytest.mark.unit
    def test_missing_required_fields(self, temp_dataset_dir: Path):
        """Test validation fails when required fields are missing."""
        # Overwrite info.json with incomplete data
        info_path = temp_dataset_dir / "meta" / "info.json"
        with open(info_path, "w") as f:
            json.dump({"robot_type": "Test"}, f)  # Missing required fields

        with pytest.raises(ValidationError) as exc_info:
            validate_lerobot_structure(temp_dataset_dir)

        assert "missing required field" in str(exc_info.value).lower()

    @pytest.mark.unit
    def test_invalid_json(self, temp_dataset_dir: Path):
        """Test validation fails with invalid JSON."""
        info_path = temp_dataset_dir / "meta" / "info.json"
        info_path.write_text("{ invalid json }")

        with pytest.raises(Exception):  # Could be JSONDecodeError or ValidationError
            validate_lerobot_structure(temp_dataset_dir)

    @pytest.mark.unit
    def test_nonexistent_path(self):
        """Test validation fails for nonexistent path."""
        with pytest.raises(ValidationError):
            validate_lerobot_structure(Path("/nonexistent/path"))


class TestListDatasetFiles:
    """Tests for listing dataset files."""

    @pytest.mark.unit
    def test_list_files(self, temp_dataset_dir: Path):
        """Test listing files in a dataset."""
        # Add some additional files
        data_dir = temp_dataset_dir / "data" / "chunk-000"
        data_dir.mkdir(parents=True)
        (data_dir / "file-000.parquet").write_text("test data")

        files = list_dataset_files(temp_dataset_dir)

        assert len(files) >= 2  # info.json + parquet file

        # Check file tuple structure: (absolute_path, relative_path, content_type, size)
        for abs_path, rel_path, content_type, size in files:
            assert abs_path.exists()
            assert isinstance(rel_path, str)
            assert isinstance(content_type, str)
            assert isinstance(size, int)
            assert size >= 0

    @pytest.mark.unit
    def test_content_type_detection(self, temp_dataset_dir: Path):
        """Test that content types are correctly detected."""
        # Create files with different extensions
        (temp_dataset_dir / "test.json").write_text("{}")
        (temp_dataset_dir / "test.parquet").write_text("parquet data")
        (temp_dataset_dir / "test.mp4").write_text("video data")

        files = list_dataset_files(temp_dataset_dir)
        content_types = {rel_path: ct for _, rel_path, ct, _ in files}

        assert content_types.get("test.json") == "application/json"
        # parquet might not have a registered MIME type
        assert content_types.get("test.mp4") in ("video/mp4", "application/octet-stream")

    @pytest.mark.unit
    def test_empty_directory(self, temp_dataset_dir: Path):
        """Test listing files in empty directory."""
        # Remove the meta directory to make it empty-ish
        import shutil
        shutil.rmtree(temp_dataset_dir / "meta")

        files = list_dataset_files(temp_dataset_dir)
        assert len(files) == 0

    @pytest.mark.unit
    def test_nested_directories(self, temp_dataset_dir: Path):
        """Test that nested directories are traversed."""
        # Create nested structure
        deep_path = temp_dataset_dir / "data" / "chunk-000" / "subfolder"
        deep_path.mkdir(parents=True)
        (deep_path / "nested_file.txt").write_text("nested")

        files = list_dataset_files(temp_dataset_dir)
        rel_paths = [rel for _, rel, _, _ in files]

        assert any("nested_file.txt" in p for p in rel_paths)


class TestDroidDatasetValidation:
    """Tests using the real DROID dataset."""

    @pytest.mark.integration
    def test_droid_info_json(self, droid_dataset_path: Path):
        """Test parsing DROID dataset info.json directly."""
        import json

        info_path = droid_dataset_path / "meta" / "info.json"
        assert info_path.exists(), "DROID info.json should exist"

        with open(info_path) as f:
            info = json.load(f)

        assert info["total_episodes"] == 95617
        assert info["total_frames"] == 27618651
        assert info["fps"] == 15
        assert info["robot_type"] == "Franka"
        assert "observation.images.wrist_left" in info["features"]

    @pytest.mark.integration
    def test_droid_validation(self, droid_dataset_path: Path):
        """Test validation of the DROID dataset.

        Note: This may fail if only partial dataset is available.
        The full DROID dataset requires data/ and videos/ directories.
        """
        try:
            info = validate_lerobot_structure(droid_dataset_path)
            assert info["total_episodes"] == 95617
        except ValidationError as e:
            # Accept validation errors for partial downloads
            # but verify it's about missing data, not corrupt metadata
            assert "missing" in str(e).lower() or "directory" in str(e).lower()
            pytest.skip(f"Partial dataset: {e}")

    @pytest.mark.integration
    def test_droid_file_listing(self, droid_dataset_path: Path):
        """Test listing files in the DROID dataset."""
        files = list_dataset_files(droid_dataset_path)

        assert len(files) > 0

        # Check for expected file types
        rel_paths = [rel for _, rel, _, _ in files]
        assert any("info.json" in p for p in rel_paths)
