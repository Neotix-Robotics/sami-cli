"""Main SAMI Datasets client."""

from typing import List, Optional
from pathlib import Path

import requests

from .auth import SamiAuth
from .config import SamiConfig, DEFAULT_API_URL
from .models import Dataset
from .upload import upload_dataset
from .download import download_dataset
from .exceptions import SamiError, NotFoundError, AuthenticationError


class SamiClient:
    """Client for interacting with SAMI Dataset Distribution Platform.

    Example usage:
        client = SamiClient(
            api_url="http://localhost:5001/api/v1",
            email="user@example.com",
            password="password"
        )

        # List datasets
        datasets = client.list_datasets()

        # Upload a dataset
        dataset = client.upload_dataset(
            name="my-dataset",
            path="/path/to/lerobot/dataset",
            description="My robot data"
        )

        # Download a dataset
        client.download_dataset(
            dataset_id="...",
            output_path="./my_dataset"
        )
    """

    def __init__(self, api_url: str = None, email: str = None, password: str = None):
        """Initialize the SAMI client.

        Args:
            api_url: Base URL of the SAMI API. Defaults to https://api.dextero.co/api/v1
            email: User email for authentication
            password: User password for authentication
        """
        if api_url is None:
            api_url = DEFAULT_API_URL
        self.api_url = api_url.rstrip("/")
        self.auth = SamiAuth(self.api_url)

        if email and password:
            self.auth.login(email, password)

    def login(self, email: str, password: str) -> None:
        """Authenticate with the SAMI API.

        Args:
            email: User email
            password: User password
        """
        self.auth.login(email, password)

    @classmethod
    def from_saved_credentials(cls) -> "SamiClient":
        """Create a client using saved credentials from ~/.sami/.

        This is useful for CLI tools that want to use previously saved
        login credentials.

        Returns:
            Authenticated SamiClient instance

        Raises:
            AuthenticationError: If no saved credentials found
        """
        config = SamiConfig()
        credentials = config.load_credentials()

        if not credentials or not credentials.get("access_token"):
            raise AuthenticationError("Not logged in. Run 'sami login' first.")

        client = cls(api_url=config.get_api_url())
        client.auth.access_token = credentials["access_token"]
        client.auth.refresh_token = credentials.get("refresh_token")
        return client

    def get_current_user(self) -> dict:
        """Get current authenticated user info.

        Returns:
            Dictionary with user info including email, firstName, lastName,
            role, and organization.
        """
        response = requests.get(
            f"{self.api_url}/auth/me",
            headers=self.auth.get_headers(),
        )

        if response.status_code == 401:
            raise AuthenticationError("Session expired. Please login again.")
        if response.status_code != 200:
            try:
                error = response.json().get("error", {}).get("message", "Unknown error")
            except Exception:
                error = f"HTTP {response.status_code}"
            raise SamiError(f"Failed to get user info: {error}")

        # API returns { data: { user: {...} } }
        return response.json()["data"]["user"]

    def list_datasets(
        self,
        page: int = 1,
        limit: int = 20,
        status: str = None,
    ) -> List[Dataset]:
        """List datasets accessible to the authenticated user.

        Args:
            page: Page number (1-indexed)
            limit: Number of results per page (max 100)
            status: Filter by status (pending, uploading, processing, ready, failed)

        Returns:
            List of Dataset objects
        """
        params = {"page": page, "limit": limit}
        if status:
            params["status"] = status

        response = requests.get(
            f"{self.api_url}/datasets",
            params=params,
            headers=self.auth.get_headers(),
        )

        if response.status_code != 200:
            try:
                error = response.json().get("error", {}).get("message", "Unknown error")
            except Exception:
                error = f"HTTP {response.status_code}"
            raise SamiError(f"Failed to list datasets: {error}")

        data = response.json()["data"]
        return [Dataset.from_api_response(d) for d in data]

    def get_dataset(self, dataset_id: str) -> Dataset:
        """Get details of a specific dataset.

        Args:
            dataset_id: ID of the dataset

        Returns:
            Dataset object
        """
        response = requests.get(
            f"{self.api_url}/datasets/{dataset_id}",
            headers=self.auth.get_headers(),
        )

        if response.status_code == 404:
            raise NotFoundError(f"Dataset not found: {dataset_id}")
        if response.status_code != 200:
            try:
                error = response.json().get("error", {}).get("message", "Unknown error")
            except Exception:
                error = f"HTTP {response.status_code}"
            raise SamiError(f"Failed to get dataset: {error}")

        return Dataset.from_api_response(response.json()["data"])

    def upload_dataset(
        self,
        name: str,
        path: str,
        description: str = None,
        task_category: str = None,
        max_workers: int = 4,
        strict: bool = True,
    ) -> Dataset:
        """Upload a LeRobot dataset.

        The dataset must be in LeRobot format with a meta/info.json file
        containing at least: total_episodes, total_frames, and fps fields.

        Args:
            name: Dataset name
            path: Path to local LeRobot dataset directory
            description: Optional description
            task_category: Optional task category (e.g., "manipulation", "navigation")
            max_workers: Number of parallel upload threads
            strict: If True, fail on missing videos/data. If False, warn only
                    (useful for uploading partial datasets like videos-only).

        Returns:
            Dataset object with metadata
        """
        return upload_dataset(
            auth=self.auth,
            api_url=self.api_url,
            name=name,
            path=path,
            description=description,
            task_category=task_category,
            max_workers=max_workers,
            strict=strict,
        )

    def download_dataset(
        self,
        dataset_id: str,
        output_path: str,
        max_workers: int = 4,
    ) -> Path:
        """Download a dataset.

        The downloaded dataset will be in LeRobot format and can be loaded
        directly with LeRobot's dataset loaders.

        Args:
            dataset_id: ID of the dataset to download
            output_path: Local path to download to
            max_workers: Number of parallel download threads

        Returns:
            Path to the downloaded dataset
        """
        return download_dataset(
            auth=self.auth,
            api_url=self.api_url,
            dataset_id=dataset_id,
            output_path=output_path,
            max_workers=max_workers,
        )

    def delete_dataset(self, dataset_id: str) -> None:
        """Delete a dataset.

        Only the owning organization can delete a dataset.

        Args:
            dataset_id: ID of the dataset to delete
        """
        response = requests.delete(
            f"{self.api_url}/datasets/{dataset_id}",
            headers=self.auth.get_headers(),
        )

        if response.status_code == 404:
            raise NotFoundError(f"Dataset not found: {dataset_id}")
        if response.status_code not in (200, 204):
            try:
                error = response.json().get("error", {}).get("message", "Unknown error")
            except Exception:
                error = f"HTTP {response.status_code}"
            raise SamiError(f"Failed to delete dataset: {error}")

    def assign_dataset(
        self,
        dataset_id: str,
        organization_id: str,
        permission_level: str = "download",
    ) -> None:
        """Assign a dataset to another organization.

        Only the owning organization can assign datasets.

        Args:
            dataset_id: ID of the dataset
            organization_id: ID of the organization to grant access
            permission_level: Permission level (view, download, admin)
        """
        if permission_level not in ("view", "download", "admin"):
            raise ValueError("permission_level must be 'view', 'download', or 'admin'")

        response = requests.post(
            f"{self.api_url}/datasets/{dataset_id}/assignments",
            json={
                "organizationId": organization_id,
                "permissionLevel": permission_level,
            },
            headers=self.auth.get_headers(),
        )

        if response.status_code == 404:
            raise NotFoundError(f"Dataset or organization not found")
        if response.status_code not in (200, 201):
            try:
                error = response.json().get("error", {}).get("message", "Unknown error")
            except Exception:
                error = f"HTTP {response.status_code}"
            raise SamiError(f"Failed to assign dataset: {error}")

    def remove_assignment(self, dataset_id: str, assignment_id: str) -> None:
        """Remove a dataset assignment.

        Only the owning organization can remove assignments.

        Args:
            dataset_id: ID of the dataset
            assignment_id: ID of the assignment to remove
        """
        response = requests.delete(
            f"{self.api_url}/datasets/{dataset_id}/assignments/{assignment_id}",
            headers=self.auth.get_headers(),
        )

        if response.status_code == 404:
            raise NotFoundError(f"Dataset or assignment not found")
        if response.status_code not in (200, 204):
            try:
                error = response.json().get("error", {}).get("message", "Unknown error")
            except Exception:
                error = f"HTTP {response.status_code}"
            raise SamiError(f"Failed to remove assignment: {error}")
