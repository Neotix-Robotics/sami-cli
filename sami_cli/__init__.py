"""SAMI Datasets SDK for robotics dataset distribution.

This SDK provides a Python interface for uploading, downloading, and managing
robotics datasets in LeRobot format through the SAMI platform.

CLI Usage:
    # Install and login
    pip install sami-datasets
    sami login

    # Use CLI commands
    sami list
    sami upload ./dataset --name "My Dataset"
    sami download <dataset-id>

Python SDK Usage:
    from sami_cli import SamiClient

    # Option 1: Use saved credentials (after 'sami login')
    client = SamiClient.from_saved_credentials()

    # Option 2: Authenticate directly
    client = SamiClient(
        email="user@example.com",
        password="password"
    )

    # List available datasets
    datasets = client.list_datasets()
    for ds in datasets:
        print(f"{ds.name}: {ds.episode_count} episodes")

    # Upload a LeRobot dataset
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

from .client import SamiClient
from .config import SamiConfig, DEFAULT_API_URL
from .models import Dataset, UploadUrl, DownloadUrl
from .exceptions import (
    SamiError,
    AuthenticationError,
    NotFoundError,
    PermissionDeniedError,
    UploadError,
    DownloadError,
    ValidationError,
)

__version__ = "0.1.0"
__all__ = [
    "SamiClient",
    "SamiConfig",
    "DEFAULT_API_URL",
    "Dataset",
    "UploadUrl",
    "DownloadUrl",
    "SamiError",
    "AuthenticationError",
    "NotFoundError",
    "PermissionDeniedError",
    "UploadError",
    "DownloadError",
    "ValidationError",
]
