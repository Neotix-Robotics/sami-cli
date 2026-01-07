#!/usr/bin/env python3
"""
Upload test datasets to SAMI.

Usage:
    # Upload tiny test dataset:
    python upload_test.py --email user@example.com --password secret --test

    # Upload droid dataset:
    python upload_test.py --email user@example.com --password secret --droid
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sami_datasets import SamiClient


def create_test_dataset(output_path="/tmp/test-dataset"):
    """Create a minimal LeRobot-compatible test dataset."""
    output_dir = Path(output_path)
    meta_dir = output_dir / "meta"
    data_dir = output_dir / "data" / "chunk-000"

    meta_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    info = {
        "codebase_version": "v3.0",
        "robot_type": "test_robot",
        "total_episodes": 10,
        "total_frames": 1000,
        "fps": 30,
        "features": {
            "observation.state": {"dtype": "float32", "shape": [7], "names": None},
            "action": {"dtype": "float32", "shape": [7], "names": None}
        }
    }

    with open(meta_dir / "info.json", "w") as f:
        json.dump(info, f, indent=2)

    with open(data_dir / "file-000.parquet", "wb") as f:
        f.write(b"dummy parquet data")

    print(f"Created test dataset at: {output_dir}")
    return str(output_dir)


def main():
    parser = argparse.ArgumentParser(description="Upload datasets to SAMI")
    parser.add_argument("--email", required=True, help="User email")
    parser.add_argument("--password", required=True, help="User password")
    parser.add_argument("--api-url", default="http://localhost:5001/api/v1")
    parser.add_argument("--test", action="store_true", help="Upload tiny test dataset")
    parser.add_argument("--droid", action="store_true", help="Upload droid dataset")

    args = parser.parse_args()

    if not args.test and not args.droid:
        print("Specify --test or --droid")
        sys.exit(1)

    print(f"Connecting to {args.api_url}...")
    client = SamiClient(api_url=args.api_url, email=args.email, password=args.password)
    print("Authenticated!")

    if args.test:
        path = create_test_dataset()
        name = "Test Dataset"
        desc = "Minimal test dataset"
    else:
        path = "/Users/mats2/Documents/GitHub/SAMI-client/lerobot/droid_1.0.1"
        name = "DROID Kitchen Tasks"
        desc = "Franka robot manipulation data"

    print(f"\nUploading: {name}")
    dataset = client.upload_dataset(name=name, path=path, description=desc)

    print(f"\nSuccess! ID: {dataset.id}")
    print(f"Status: {dataset.upload_status}")
    print(f"Episodes: {dataset.episode_count}")
    print(f"View at: http://localhost:3000/datasets/{dataset.id}")


if __name__ == "__main__":
    main()
