# SAMI CLI

Python SDK and CLI for the SAMI Dataset Distribution Platform. Upload, download, and manage robotics datasets in LeRobot format.

> **Note:** Dataset uploads require **platform admin** privileges (`globalRole: platform_admin`). Regular users can browse and download datasets but cannot upload.

## Installation

```bash
pip install sami-cli
```

For development:
```bash
cd sami-cli
pip install -e ".[dev]"
```

## Quick Start (CLI)

```bash
# Login (credentials saved to ~/.sami/)
sami login
Email: user@example.com
Password: ********
Logged in as user@example.com
  Organization: Acme Robotics

# List datasets
sami list

# Upload a dataset (requires admin)
sami upload ./my_dataset --name "Robot Arm Demo"

# Download a dataset
sami download <dataset-id> --output ./downloaded

# Show your info
sami whoami

# Logout
sami logout
```

## CLI Reference

| Command | Description |
|---------|-------------|
| `sami login` | Authenticate and save credentials |
| `sami logout` | Clear saved credentials |
| `sami whoami` | Show current user info |
| `sami config` | View/set configuration |
| `sami list` | List accessible datasets |
| `sami upload <path>` | Upload a LeRobot dataset |
| `sami download <id>` | Download a dataset |
| `sami info <id>` | Show dataset details |
| `sami delete <id>` | Delete a dataset |

### Command Options

```bash
# Upload with options
sami upload ./dataset \
    --name "My Dataset" \
    --description "Kitchen manipulation tasks" \
    --task-category manipulation \
    --workers 8

# Download with options
sami download abc123 \
    --output ./my_data \
    --workers 8

# List with filters
sami list --status ready --limit 50

# Set custom API URL
sami config --api-url https://api.example.com/api/v1
```

## Environment Variables

For CI/CD pipelines, you can use environment variables instead of `sami login`:

| Variable | Description |
|----------|-------------|
| `SAMI_API_URL` | Override API URL |
| `SAMI_ACCESS_TOKEN` | Use token directly (skip login) |
| `SAMI_EMAIL` | Email for login |
| `SAMI_PASSWORD` | Password for login |

```bash
# Example: CI/CD usage
export SAMI_ACCESS_TOKEN="your-jwt-token"
sami list
sami download abc123
```

## Python SDK

### Using Saved Credentials

After running `sami login`, use credentials in Python:

```python
from sami_cli import SamiClient

# Use saved credentials from ~/.sami/
client = SamiClient.from_saved_credentials()

# List datasets
datasets = client.list_datasets()
for ds in datasets:
    print(f"{ds.name}: {ds.episode_count} episodes")
```

### Direct Authentication

```python
from sami_cli import SamiClient

# Authenticate directly
client = SamiClient(
    email="user@example.com",
    password="your-password",
)

# Upload a LeRobot dataset
dataset = client.upload_dataset(
    name="my-dataset-v1",
    path="/path/to/lerobot/dataset",
    description="Kitchen manipulation tasks",
    task_category="manipulation",
)
print(f"Uploaded: {dataset.id}")

# Download a dataset
client.download_dataset(
    dataset_id=dataset.id,
    output_path="./downloaded_dataset",
)
```

### API Methods

```python
# Authentication
client.login(email, password)
client.get_current_user()

# Datasets
client.list_datasets(page=1, limit=20, status=None)
client.get_dataset(dataset_id)
client.upload_dataset(name, path, description=None, task_category=None, max_workers=4)
client.download_dataset(dataset_id, output_path, max_workers=4)
client.delete_dataset(dataset_id)

# Sharing
client.assign_dataset(dataset_id, organization_id, permission_level)
client.remove_assignment(dataset_id, assignment_id)
```

## LeRobot Format

Datasets must be in LeRobot format:

```
my_dataset/
  meta/
    info.json       # Required: episodes, frames, fps, features
    stats.json      # Optional: statistics
    episodes/       # Optional: episode metadata
  data/
    chunk-000/      # Parquet files with episode data
    chunk-001/
  videos/           # Optional: video files
    chunk-000/
```

The `meta/info.json` must contain:
- `total_episodes`: Number of episodes
- `total_frames`: Total frame count
- `fps`: Frames per second

## LeRobot Integration

Downloaded datasets work directly with LeRobot:

```python
from lerobot.common.datasets.lerobot_dataset import LeRobotDataset

# Load downloaded dataset
dataset = LeRobotDataset("./my_dataset")

# Use in training
for batch in dataset:
    observation = batch["observation.state"]
    action = batch["action"]
    # ... train your model
```

## Dataset Object

```python
@dataclass
class Dataset:
    id: str
    name: str
    description: Optional[str]
    task_category: Optional[str]
    robot_type: Optional[str]
    episode_count: Optional[int]
    total_frames: Optional[int]
    fps: Optional[float]
    file_size_bytes: int
    upload_status: str  # pending, uploading, processing, ready, failed
    created_at: datetime
    organization_name: str
    features: Optional[Dict[str, Any]]
    assignments: List[Dict[str, Any]]
```

## Exceptions

```python
from sami_cli import (
    SamiError,              # Base exception
    AuthenticationError,    # Login failed
    NotFoundError,          # Resource not found
    PermissionDeniedError,  # Access denied
    UploadError,            # Upload failed
    DownloadError,          # Download failed
    ValidationError,        # Invalid dataset format
)
```

## Requirements

- Python >= 3.9
- requests >= 2.28.0
- tqdm >= 4.65.0
