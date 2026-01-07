"""Unit tests for sami_cli.models module."""

import pytest
from datetime import datetime

from sami_cli.models import Dataset, UploadUrl, DownloadUrl


class TestDataset:
    """Tests for the Dataset model."""

    @pytest.mark.unit
    def test_from_api_response_minimal(self):
        """Test creating Dataset from minimal API response."""
        data = {
            "id": "test-id-123",
            "name": "Test Dataset",
            "fileSizeBytes": "1024",
            "uploadStatus": "ready",
            "createdAt": "2024-01-15T10:30:00Z",
            "organization": {"name": "Test Org"},
        }

        dataset = Dataset.from_api_response(data)

        assert dataset.id == "test-id-123"
        assert dataset.name == "Test Dataset"
        assert dataset.file_size_bytes == 1024
        assert dataset.upload_status == "ready"
        assert dataset.organization_name == "Test Org"
        assert dataset.description is None
        assert dataset.episode_count is None

    @pytest.mark.unit
    def test_from_api_response_full(self):
        """Test creating Dataset from complete API response."""
        data = {
            "id": "dataset-456",
            "name": "Full Dataset",
            "description": "A complete test dataset",
            "taskCategory": "manipulation",
            "robotType": "Franka",
            "episodeCount": 100,
            "totalFrames": 5000,
            "fps": 30.0,
            "fileSizeBytes": "1073741824",
            "uploadStatus": "ready",
            "createdAt": "2024-01-15T10:30:00Z",
            "organization": {"name": "Robotics Lab"},
            "features": {
                "observation.state": {"dtype": "float32", "shape": [7]}
            },
            "assignments": [
                {"id": "assign-1", "organizationId": "org-1", "permissionLevel": "download"}
            ],
        }

        dataset = Dataset.from_api_response(data)

        assert dataset.id == "dataset-456"
        assert dataset.name == "Full Dataset"
        assert dataset.description == "A complete test dataset"
        assert dataset.task_category == "manipulation"
        assert dataset.robot_type == "Franka"
        assert dataset.episode_count == 100
        assert dataset.total_frames == 5000
        assert dataset.fps == 30.0
        assert dataset.file_size_bytes == 1073741824
        assert dataset.organization_name == "Robotics Lab"
        assert "observation.state" in dataset.features
        assert len(dataset.assignments) == 1

    @pytest.mark.unit
    def test_from_api_response_handles_missing_organization(self):
        """Test handling missing organization field."""
        data = {
            "id": "test-id",
            "name": "Test",
            "fileSizeBytes": "0",
            "uploadStatus": "pending",
            "createdAt": "2024-01-15T10:30:00Z",
        }

        dataset = Dataset.from_api_response(data)
        assert dataset.organization_name == "Unknown"

    @pytest.mark.unit
    def test_from_api_response_handles_invalid_date(self):
        """Test handling invalid date format."""
        data = {
            "id": "test-id",
            "name": "Test",
            "fileSizeBytes": "0",
            "uploadStatus": "pending",
            "createdAt": "invalid-date",
            "organization": {"name": "Test"},
        }

        dataset = Dataset.from_api_response(data)
        # Should not raise, should use current time as fallback
        assert isinstance(dataset.created_at, datetime)

    @pytest.mark.unit
    def test_str_representation(self):
        """Test Dataset string representation."""
        data = {
            "id": "test-id",
            "name": "My Dataset",
            "episodeCount": 1000,
            "totalFrames": 50000,
            "robotType": "ALOHA",
            "fileSizeBytes": "5368709120",  # 5GB
            "uploadStatus": "ready",
            "createdAt": "2024-01-15T10:30:00Z",
            "organization": {"name": "Test"},
        }

        dataset = Dataset.from_api_response(data)
        str_repr = str(dataset)

        assert "My Dataset" in str_repr
        assert "1,000" in str_repr  # episodes formatted
        assert "50,000" in str_repr  # frames formatted
        assert "ALOHA" in str_repr
        assert "ready" in str_repr


class TestUploadUrl:
    """Tests for the UploadUrl model."""

    @pytest.mark.unit
    def test_creation(self):
        """Test UploadUrl creation."""
        url = UploadUrl(
            relative_path="meta/info.json",
            upload_url="https://s3.example.com/presigned-url",
            key="datasets/123/meta/info.json"
        )

        assert url.relative_path == "meta/info.json"
        assert "presigned-url" in url.upload_url
        assert url.key == "datasets/123/meta/info.json"


class TestDownloadUrl:
    """Tests for the DownloadUrl model."""

    @pytest.mark.unit
    def test_creation(self):
        """Test DownloadUrl creation."""
        url = DownloadUrl(
            relative_path="data/chunk-000/file-000.parquet",
            download_url="https://s3.example.com/download-url",
            size=1048576
        )

        assert url.relative_path == "data/chunk-000/file-000.parquet"
        assert url.size == 1048576
