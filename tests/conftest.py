"""Pytest configuration and fixtures for SAMI Datasets SDK tests."""

import os
import json
import pytest
import tempfile
from pathlib import Path
from typing import Generator

# Test configuration - can be overridden with environment variables
TEST_API_URL = os.getenv("SAMI_TEST_API_URL", "http://localhost:5001/api/v1")
TEST_EMAIL = os.getenv("SAMI_TEST_EMAIL", "admin@dextera.company")
TEST_PASSWORD = os.getenv("SAMI_TEST_PASSWORD", "Admin123!")


def pytest_configure(config):
    """Configure custom markers."""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (require running backend)"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests (no external dependencies)"
    )


@pytest.fixture(scope="session")
def api_url() -> str:
    """API URL for integration tests."""
    return TEST_API_URL


@pytest.fixture(scope="session")
def test_credentials() -> dict:
    """Test user credentials."""
    return {
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
    }


@pytest.fixture(scope="session")
def authenticated_client(api_url: str, test_credentials: dict):
    """Create an authenticated SamiClient for integration tests."""
    from sami_cli import SamiClient

    client = SamiClient(
        api_url=api_url,
        email=test_credentials["email"],
        password=test_credentials["password"],
    )
    return client


@pytest.fixture
def temp_dataset_dir() -> Generator[Path, None, None]:
    """Create a temporary directory with a valid LeRobot dataset structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dataset_path = Path(tmpdir) / "test_dataset"
        meta_path = dataset_path / "meta"
        meta_path.mkdir(parents=True)

        # Create info.json
        info = {
            "codebase_version": "v3.0",
            "robot_type": "TestBot",
            "total_episodes": 5,
            "total_frames": 100,
            "fps": 30,
            "features": {
                "observation.state": {
                    "dtype": "float32",
                    "shape": [7],
                    "names": None
                },
                "action": {
                    "dtype": "float32",
                    "shape": [7],
                    "names": None
                }
            }
        }

        with open(meta_path / "info.json", "w") as f:
            json.dump(info, f, indent=2)

        yield dataset_path


@pytest.fixture
def invalid_dataset_dir() -> Generator[Path, None, None]:
    """Create a temporary directory without valid LeRobot structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dataset_path = Path(tmpdir) / "invalid_dataset"
        dataset_path.mkdir(parents=True)

        # Create a file but no meta/info.json
        (dataset_path / "some_file.txt").write_text("test content")

        yield dataset_path


@pytest.fixture
def sample_info_json() -> dict:
    """Sample LeRobot info.json content."""
    return {
        "codebase_version": "v3.0",
        "robot_type": "Franka",
        "total_episodes": 100,
        "total_frames": 5000,
        "fps": 30,
        "features": {
            "observation.state": {
                "dtype": "float32",
                "shape": [7],
                "names": {"axes": ["j0", "j1", "j2", "j3", "j4", "j5", "j6"]}
            },
            "observation.images.camera": {
                "dtype": "video",
                "shape": [480, 640, 3],
                "names": ["height", "width", "channels"]
            },
            "action": {
                "dtype": "float32",
                "shape": [7],
                "names": None
            }
        }
    }


@pytest.fixture
def droid_dataset_path() -> Path:
    """Path to the DROID dataset for integration tests."""
    path = Path("/Users/mats2/Documents/GitHub/SAMI-client/lerobot/droid_1.0.1")
    if not path.exists():
        pytest.skip("DROID dataset not available")
    return path
