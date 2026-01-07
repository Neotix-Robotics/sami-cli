"""Integration tests for sami_cli.client module."""

import pytest
from pathlib import Path

from sami_cli import SamiClient, SamiError, AuthenticationError, NotFoundError
from sami_cli.models import Dataset


class TestSamiClientUnit:
    """Unit tests for SamiClient."""

    @pytest.mark.unit
    def test_init_without_credentials(self):
        """Test client initialization without credentials."""
        client = SamiClient(api_url="http://localhost:5001/api/v1")

        assert client.api_url == "http://localhost:5001/api/v1"
        assert not client.auth.is_authenticated()

    @pytest.mark.unit
    def test_init_strips_trailing_slash(self):
        """Test that trailing slash is stripped."""
        client = SamiClient(api_url="http://localhost:5001/api/v1/")

        assert client.api_url == "http://localhost:5001/api/v1"


class TestSamiClientIntegration:
    """Integration tests for SamiClient (requires running backend)."""

    @pytest.mark.integration
    def test_init_with_credentials(self, api_url: str, test_credentials: dict):
        """Test client initialization with credentials."""
        client = SamiClient(
            api_url=api_url,
            email=test_credentials["email"],
            password=test_credentials["password"]
        )

        assert client.auth.is_authenticated()

    @pytest.mark.integration
    def test_login_method(self, api_url: str, test_credentials: dict):
        """Test explicit login method."""
        client = SamiClient(api_url=api_url)
        assert not client.auth.is_authenticated()

        client.login(test_credentials["email"], test_credentials["password"])

        assert client.auth.is_authenticated()

    @pytest.mark.integration
    def test_list_datasets(self, authenticated_client: SamiClient):
        """Test listing datasets."""
        datasets = authenticated_client.list_datasets()

        assert isinstance(datasets, list)
        for ds in datasets:
            assert isinstance(ds, Dataset)
            assert ds.id is not None
            assert ds.name is not None

    @pytest.mark.integration
    def test_list_datasets_with_pagination(self, authenticated_client: SamiClient):
        """Test listing datasets with pagination."""
        datasets_page1 = authenticated_client.list_datasets(page=1, limit=5)
        datasets_page2 = authenticated_client.list_datasets(page=2, limit=5)

        # Both should return lists (may be empty)
        assert isinstance(datasets_page1, list)
        assert isinstance(datasets_page2, list)

    @pytest.mark.integration
    def test_list_datasets_with_status_filter(self, authenticated_client: SamiClient):
        """Test listing datasets with status filter."""
        ready_datasets = authenticated_client.list_datasets(status="ready")

        for ds in ready_datasets:
            assert ds.upload_status == "ready"

    @pytest.mark.integration
    def test_get_dataset(self, authenticated_client: SamiClient):
        """Test getting a specific dataset."""
        datasets = authenticated_client.list_datasets()

        if not datasets:
            pytest.skip("No datasets available for testing")

        dataset = authenticated_client.get_dataset(datasets[0].id)

        assert isinstance(dataset, Dataset)
        assert dataset.id == datasets[0].id
        assert dataset.name == datasets[0].name

    @pytest.mark.integration
    def test_get_nonexistent_dataset(self, authenticated_client: SamiClient):
        """Test getting a nonexistent dataset."""
        with pytest.raises(NotFoundError):
            authenticated_client.get_dataset("00000000-0000-0000-0000-000000000000")


class TestDatasetUploadDownloadIntegration:
    """Integration tests for dataset upload and download."""

    @pytest.mark.integration
    def test_upload_dataset(self, authenticated_client: SamiClient, temp_dataset_dir: Path):
        """Test uploading a dataset."""
        dataset = authenticated_client.upload_dataset(
            name="Integration Test Upload",
            path=str(temp_dataset_dir),
            description="Test dataset for integration testing",
            task_category="testing"
        )

        assert isinstance(dataset, Dataset)
        assert dataset.name == "Integration Test Upload"
        assert dataset.description == "Test dataset for integration testing"
        assert dataset.task_category == "testing"
        assert dataset.upload_status == "ready"
        assert dataset.episode_count == 5
        assert dataset.robot_type == "TestBot"

        # Cleanup: delete the uploaded dataset
        authenticated_client.delete_dataset(dataset.id)

    @pytest.mark.integration
    def test_upload_and_download_dataset(
        self, authenticated_client: SamiClient, temp_dataset_dir: Path
    ):
        """Test full upload and download cycle."""
        import tempfile
        import json

        # Upload
        dataset = authenticated_client.upload_dataset(
            name="Upload Download Test",
            path=str(temp_dataset_dir),
            description="Testing upload and download"
        )

        try:
            # Download
            with tempfile.TemporaryDirectory() as download_dir:
                output_path = authenticated_client.download_dataset(
                    dataset_id=dataset.id,
                    output_path=download_dir
                )

                # Verify downloaded files
                assert output_path.exists()
                info_path = output_path / "meta" / "info.json"
                assert info_path.exists()

                with open(info_path) as f:
                    info = json.load(f)

                assert info["total_episodes"] == 5
                assert info["robot_type"] == "TestBot"
        finally:
            # Cleanup
            authenticated_client.delete_dataset(dataset.id)

    @pytest.mark.integration
    def test_delete_dataset(self, authenticated_client: SamiClient, temp_dataset_dir: Path):
        """Test deleting a dataset."""
        # First upload a dataset
        dataset = authenticated_client.upload_dataset(
            name="Delete Test Dataset",
            path=str(temp_dataset_dir)
        )

        # Delete it
        authenticated_client.delete_dataset(dataset.id)

        # Verify it's gone
        with pytest.raises(NotFoundError):
            authenticated_client.get_dataset(dataset.id)

    @pytest.mark.integration
    def test_upload_invalid_dataset(self, authenticated_client: SamiClient, invalid_dataset_dir: Path):
        """Test uploading an invalid dataset fails."""
        from sami_cli.exceptions import ValidationError

        with pytest.raises(ValidationError):
            authenticated_client.upload_dataset(
                name="Invalid Dataset",
                path=str(invalid_dataset_dir)
            )


class TestDatasetAssignmentIntegration:
    """Integration tests for dataset assignment (sharing)."""

    @pytest.mark.integration
    def test_assign_dataset_invalid_org(
        self, authenticated_client: SamiClient, temp_dataset_dir: Path
    ):
        """Test assigning dataset to nonexistent organization."""
        # Upload a dataset first
        dataset = authenticated_client.upload_dataset(
            name="Assignment Test Dataset",
            path=str(temp_dataset_dir)
        )

        try:
            with pytest.raises(NotFoundError):
                authenticated_client.assign_dataset(
                    dataset_id=dataset.id,
                    organization_id="00000000-0000-0000-0000-000000000000",
                    permission_level="download"
                )
        finally:
            authenticated_client.delete_dataset(dataset.id)

    @pytest.mark.integration
    def test_assign_dataset_invalid_permission(
        self, authenticated_client: SamiClient, temp_dataset_dir: Path
    ):
        """Test assigning dataset with invalid permission level."""
        with pytest.raises(ValueError):
            authenticated_client.assign_dataset(
                dataset_id="some-id",
                organization_id="some-org-id",
                permission_level="invalid"
            )
