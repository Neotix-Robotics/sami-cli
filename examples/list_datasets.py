#!/usr/bin/env python3
"""Example: List available datasets from SAMI.

Usage:
    python list_datasets.py --email user@example.com --password secret
"""

import argparse
import sys
import os

# Add parent directory to path for development
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sami_datasets import SamiClient


def format_size(bytes_val: int) -> str:
    """Format bytes to human-readable size."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_val < 1024:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f} PB"


def main():
    parser = argparse.ArgumentParser(description="List datasets from SAMI")
    parser.add_argument("--api-url", default="http://localhost:5001/api/v1",
                        help="SAMI API URL")
    parser.add_argument("--email", required=True, help="User email")
    parser.add_argument("--password", required=True, help="User password")
    parser.add_argument("--status", choices=["pending", "uploading", "processing", "ready", "failed"],
                        help="Filter by status")
    parser.add_argument("--limit", type=int, default=20,
                        help="Number of results to show")

    args = parser.parse_args()

    # Initialize client
    client = SamiClient(
        api_url=args.api_url,
        email=args.email,
        password=args.password,
    )

    # List datasets
    datasets = client.list_datasets(
        limit=args.limit,
        status=args.status,
    )

    if not datasets:
        print("No datasets found.")
        return

    print(f"\nFound {len(datasets)} dataset(s):\n")
    print("-" * 100)
    print(f"{'ID':<40} {'Name':<25} {'Episodes':<12} {'Size':<12} {'Status':<10}")
    print("-" * 100)

    for ds in datasets:
        episodes = f"{ds.episode_count:,}" if ds.episode_count else "N/A"
        size = format_size(ds.file_size_bytes)
        name = ds.name[:23] + ".." if len(ds.name) > 25 else ds.name
        print(f"{ds.id:<40} {name:<25} {episodes:<12} {size:<12} {ds.upload_status:<10}")

    print("-" * 100)


if __name__ == "__main__":
    main()
