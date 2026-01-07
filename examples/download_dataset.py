#!/usr/bin/env python3
"""Example: Download a dataset from SAMI.

Usage:
    python download_dataset.py DATASET_ID --output ./my_dataset
"""

import argparse
import sys
import os

# Add parent directory to path for development
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sami_datasets import SamiClient


def main():
    parser = argparse.ArgumentParser(description="Download a dataset from SAMI")
    parser.add_argument("dataset_id", help="ID of the dataset to download")
    parser.add_argument("--output", "-o", required=True,
                        help="Output directory for the dataset")
    parser.add_argument("--api-url", default="http://localhost:5001/api/v1",
                        help="SAMI API URL")
    parser.add_argument("--email", required=True, help="User email")
    parser.add_argument("--password", required=True, help="User password")
    parser.add_argument("--workers", type=int, default=4,
                        help="Number of parallel download workers")

    args = parser.parse_args()

    # Initialize client
    print(f"Connecting to SAMI at {args.api_url}...")
    client = SamiClient(
        api_url=args.api_url,
        email=args.email,
        password=args.password,
    )
    print("Authenticated successfully!")

    # Get dataset info first
    print(f"\nFetching dataset info for {args.dataset_id}...")
    dataset = client.get_dataset(args.dataset_id)
    print(f"  Name:     {dataset.name}")
    print(f"  Episodes: {dataset.episode_count:,}" if dataset.episode_count else "  Episodes: N/A")
    print(f"  Size:     {dataset.file_size_bytes / (1024**3):.2f} GB")

    # Download
    output_path = client.download_dataset(
        dataset_id=args.dataset_id,
        output_path=args.output,
        max_workers=args.workers,
    )

    print("\n" + "=" * 50)
    print("Download Complete!")
    print("=" * 50)
    print(f"  Dataset saved to: {output_path}")
    print("\nTo use with LeRobot:")
    print(f'  from lerobot.common.datasets.lerobot_dataset import LeRobotDataset')
    print(f'  dataset = LeRobotDataset("{output_path}")')
    print("=" * 50)


if __name__ == "__main__":
    main()
