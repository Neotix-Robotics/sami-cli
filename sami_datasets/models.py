"""Data models for SAMI Datasets SDK."""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime


@dataclass
class Dataset:
    """Represents a dataset in SAMI."""
    id: str
    name: str
    description: Optional[str]
    task_category: Optional[str]
    robot_type: Optional[str]
    episode_count: Optional[int]
    total_frames: Optional[int]
    fps: Optional[float]
    file_size_bytes: int
    upload_status: str
    created_at: datetime
    organization_name: str
    features: Optional[Dict[str, Any]] = None
    assignments: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "Dataset":
        """Create Dataset from API response."""
        created_at_str = data.get("createdAt", "")
        if created_at_str:
            # Handle ISO format with Z suffix
            created_at_str = created_at_str.replace("Z", "+00:00")
            try:
                created_at = datetime.fromisoformat(created_at_str)
            except ValueError:
                created_at = datetime.now()
        else:
            created_at = datetime.now()

        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description"),
            task_category=data.get("taskCategory"),
            robot_type=data.get("robotType"),
            episode_count=data.get("episodeCount"),
            total_frames=data.get("totalFrames"),
            fps=data.get("fps"),
            file_size_bytes=int(data.get("fileSizeBytes", 0)),
            upload_status=data.get("uploadStatus", "unknown"),
            created_at=created_at,
            organization_name=data.get("organization", {}).get("name", "Unknown"),
            features=data.get("features"),
            assignments=data.get("assignments", []),
        )

    def __str__(self) -> str:
        episodes = f"{self.episode_count:,}" if self.episode_count else "N/A"
        frames = f"{self.total_frames:,}" if self.total_frames else "N/A"
        size_mb = self.file_size_bytes / (1024 * 1024)
        return (
            f"Dataset(name='{self.name}', "
            f"episodes={episodes}, "
            f"frames={frames}, "
            f"robot='{self.robot_type or 'N/A'}', "
            f"size={size_mb:.1f}MB, "
            f"status='{self.upload_status}')"
        )


@dataclass
class UploadUrl:
    """Presigned upload URL for a file."""
    relative_path: str
    upload_url: str
    key: str


@dataclass
class DownloadUrl:
    """Presigned download URL for a file."""
    relative_path: str
    download_url: str
    size: int
