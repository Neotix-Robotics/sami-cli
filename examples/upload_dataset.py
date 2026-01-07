#!/usr/bin/env python3
"""Example: Upload a LeRobot dataset to SAMI.

Usage:
    python upload_dataset.py /path/to/lerobot/dataset --name "My Dataset"
"""

import argparse
import sys
import os

# Add parent directory to path for development
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sami_cli import SamiClient


def main():
    parser = argparse.ArgumentParser(description="Upload a LeRobot dataset to SAMI")
    parser.add_argument("path", help="Path to the LeRobot dataset directory")
    parser.add_argument("--name", required=True, help="Name for the dataset")
    parser.add_argument("--description", help="Optional description")
    parser.add_argument("--task-category", help="Task category (e.g., manipulation)")
    parser.add_argument("--api-url", default="http://localhost:5001/api/v1",
                        help="SAMI API URL")
    parser.add_argument("--email", required=True, help="User email")
    parser.add_argument("--password", required=True, help="User password")
    parser.add_argument("--workers", type=int, default=4,
                        help="Number of parallel upload workers")

    args = parser.parse_args()

    # Initialize client
    print(f"Connecting to SAMI at {args.api_url}...")
    client = SamiClient(
        api_url=args.api_url,
        email=args.email,
        password=args.password,
    )
    print("Authenticated successfully!")

    # Upload dataset
    dataset = client.upload_dataset(
        name=args.name,
        path=args.path,
        description=args.description,
        task_category=args.task_category,
        max_workers=args.workers,
    )

    print("\n" + "=" * 50)
    print("Upload Summary:")
    print("=" * 50)
    print(f"  Dataset ID:    {dataset.id}")
    print(f"  Name:          {dataset.name}")
    print(f"  Episodes:      {dataset.episode_count:,}" if dataset.episode_count else "  Episodes: N/A")
    print(f"  Total Frames:  {dataset.total_frames:,}" if dataset.total_frames else "  Total Frames: N/A")
    print(f"  FPS:           {dataset.fps}" if dataset.fps else "  FPS: N/A")
    print(f"  Robot Type:    {dataset.robot_type or 'N/A'}")
    print(f"  Status:        {dataset.upload_status}")
    print(f"  Organization:  {dataset.organization_name}")
    print("=" * 50)


if __name__ == "__main__":
    main()
