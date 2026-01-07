#!/usr/bin/env python3
"""Create a minimal test dataset in LeRobot format for testing uploads."""

import json
import os
from pathlib import Path

def create_test_dataset(output_path: str = "/tmp/test-dataset"):
    """Create a minimal LeRobot-compatible test dataset."""

    output_dir = Path(output_path)
    meta_dir = output_dir / "meta"
    data_dir = output_dir / "data" / "chunk-000"

    # Create directories
    meta_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    # Create info.json (required for LeRobot format)
    info = {
        "codebase_version": "v3.0",
        "robot_type": "test_robot",
        "total_episodes": 10,
        "total_frames": 1000,
        "total_tasks": 5,
        "fps": 30,
        "chunks_size": 1000,
        "splits": {
            "train": "0:10"
        },
        "data_path": "data/chunk-{chunk_index:03d}/file-{file_index:03d}.parquet",
        "features": {
            "observation.state": {
                "dtype": "float32",
                "shape": [7],
                "names": {
                    "axes": ["joint_0", "joint_1", "joint_2", "joint_3", "joint_4", "joint_5", "joint_6"]
                }
            },
            "action": {
                "dtype": "float32",
                "shape": [7],
                "names": {
                    "axes": ["joint_0", "joint_1", "joint_2", "joint_3", "joint_4", "joint_5", "joint_6"]
                }
            },
            "episode_index": {
                "dtype": "int64",
                "shape": [1],
                "names": None
            },
            "frame_index": {
                "dtype": "int64",
                "shape": [1],
                "names": None
            },
            "is_first": {
                "dtype": "bool",
                "shape": [1],
                "names": None
            },
            "is_last": {
                "dtype": "bool",
                "shape": [1],
                "names": None
            }
        }
    }

    with open(meta_dir / "info.json", "w") as f:
        json.dump(info, f, indent=2)

    # Create stats.json
    stats = {
        "observation.state": {
            "mean": [0.0] * 7,
            "std": [1.0] * 7,
            "min": [-1.0] * 7,
            "max": [1.0] * 7
        },
        "action": {
            "mean": [0.0] * 7,
            "std": [1.0] * 7,
            "min": [-1.0] * 7,
            "max": [1.0] * 7
        }
    }

    with open(meta_dir / "stats.json", "w") as f:
        json.dump(stats, f, indent=2)

    # Create a dummy data file (just a small text file for testing)
    # In a real dataset, this would be a parquet file
    dummy_data = b"dummy parquet data for testing"
    with open(data_dir / "file-000.parquet", "wb") as f:
        f.write(dummy_data)

    print(f"Test dataset created at: {output_dir}")
    print(f"  - meta/info.json")
    print(f"  - meta/stats.json")
    print(f"  - data/chunk-000/file-000.parquet")

    return output_dir


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Create a test LeRobot dataset")
    parser.add_argument("--output", "-o", default="/tmp/test-dataset",
                        help="Output directory for the test dataset")

    args = parser.parse_args()
    create_test_dataset(args.output)
