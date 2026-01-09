#!/usr/bin/env python3
"""SAMI CLI - Command line interface for SAMI Dataset Distribution Platform.

Usage:
    sami login              # Authenticate and save credentials
    sami logout             # Clear saved credentials
    sami whoami             # Show current user info
    sami config             # View/set configuration
    sami list               # List accessible datasets
    sami upload <path>      # Upload a dataset
    sami download <id>      # Download a dataset
    sami info <id>          # Show dataset details
    sami delete <id>        # Delete a dataset
"""

import argparse
import getpass
import os
import sys
from typing import Optional

from .config import SamiConfig, DEFAULT_API_URL
from .exceptions import AuthenticationError, SamiError, NotFoundError


def get_client():
    """Get an authenticated SamiClient.

    Loads credentials from disk or environment variables.
    Automatically refreshes expired tokens and saves them back to disk.

    Returns:
        Authenticated SamiClient instance

    Raises:
        AuthenticationError: If not logged in
    """
    # Import here to avoid circular imports
    from .client import SamiClient

    config = SamiConfig()

    # Check for token in environment (for CI/CD)
    env_token = os.environ.get("SAMI_ACCESS_TOKEN")
    if env_token:
        client = SamiClient(api_url=config.get_api_url())
        client.auth.access_token = env_token
        return client

    # Load from saved credentials
    credentials = config.load_credentials()
    if not credentials or not credentials.get("access_token"):
        print("Error: Not logged in. Run 'sami login' first.", file=sys.stderr)
        sys.exit(1)

    client = SamiClient(api_url=config.get_api_url())
    client.auth.access_token = credentials["access_token"]
    client.auth.refresh_token = credentials.get("refresh_token")

    # Check if token is expired and try to refresh
    if client.auth.is_token_expired() and client.auth.refresh_token:
        try:
            client.auth.refresh()
            # Save refreshed tokens back to disk
            config.save_credentials(
                access_token=client.auth.access_token,
                refresh_token=client.auth.refresh_token,
                user_email=credentials.get("user_email"),
                organization_name=credentials.get("organization_name"),
            )
        except AuthenticationError:
            print("Error: Session expired. Run 'sami login' to authenticate.", file=sys.stderr)
            sys.exit(1)

    return client


def format_size(size_bytes: int) -> str:
    """Format bytes as human readable size."""
    if size_bytes is None:
        return "N/A"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(size_bytes) < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


# =============================================================================
# Login Command
# =============================================================================


def cmd_login(args):
    """Handle 'sami login' command."""
    from .client import SamiClient
    from .auth import SamiAuth

    config = SamiConfig()
    api_url = config.get_api_url()

    # Device flow is default, use --password for email/password flow
    use_password_flow = getattr(args, "password_flow", False)

    if not use_password_flow:
        # Device code flow - authenticate via browser
        try:
            auth = SamiAuth(api_url)

            print("Starting device authentication...")
            print("")

            # Get device code
            device_data = auth.start_device_flow()

            user_code = device_data.get("user_code", "")
            verification_uri = device_data.get("verification_uri", "")
            verification_uri_complete = device_data.get("verification_uri_complete", "")
            device_code = device_data.get("device_code", "")
            interval = device_data.get("interval", 5)

            print("=" * 50)
            print("To authorize this device:")
            print("")
            print(f"  1. Open: {verification_uri}")
            print(f"  2. Enter code: {user_code}")
            print("")
            print(f"Or open: {verification_uri_complete}")
            print("=" * 50)
            print("")
            print("Opening browser...")
            print("Waiting for authorization...")

            # Poll for token (this also opens the browser)
            auth.poll_device_token(
                device_code=device_code,
                interval=interval,
                open_browser=True,
                verification_uri_complete=verification_uri_complete,
            )

            # Create client with authenticated auth
            client = SamiClient(api_url=api_url)
            client.auth = auth

            # Get user info
            try:
                user_info = client.get_current_user()
                user_email = user_info.get("email", "Unknown")
                org_name = user_info.get("organization", {}).get("name", "Unknown")
            except Exception:
                user_email = "Unknown"
                org_name = "Unknown"

            # Save credentials
            config.save_credentials(
                access_token=auth.access_token,
                refresh_token=auth.refresh_token,
                user_email=user_email,
                organization_name=org_name,
            )

            print("")
            print("=" * 50)
            print("Device authorized successfully!")
            print("=" * 50)
            print(f"Logged in as {user_email}")
            print(f"  Organization: {org_name}")

        except AuthenticationError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    else:
        # Traditional email/password flow
        # Get email
        email = args.email or os.environ.get("SAMI_EMAIL")
        if not email:
            email = input("Email: ")

        # Get password (always prompt or use env var)
        password = os.environ.get("SAMI_PASSWORD")
        if not password:
            password = getpass.getpass("Password: ")

        try:
            # Authenticate
            client = SamiClient(api_url=api_url, email=email, password=password)

            # Get user info
            try:
                user_info = client.get_current_user()
                user_email = user_info.get("email", email)
                org_name = user_info.get("organization", {}).get("name", "Unknown")
            except Exception:
                user_email = email
                org_name = "Unknown"

            # Save credentials
            config.save_credentials(
                access_token=client.auth.access_token,
                refresh_token=client.auth.refresh_token,
                user_email=user_email,
                organization_name=org_name,
            )

            print(f"Logged in as {user_email}")
            print(f"  Organization: {org_name}")

        except AuthenticationError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)


# =============================================================================
# Logout Command
# =============================================================================


def cmd_logout(args):
    """Handle 'sami logout' command."""
    config = SamiConfig()

    if not config.has_credentials():
        print("Not logged in.")
        return

    config.clear_credentials()
    print("Logged out.")


# =============================================================================
# Whoami Command
# =============================================================================


def cmd_whoami(args):
    """Handle 'sami whoami' command."""
    from .client import SamiClient

    config = SamiConfig()
    credentials = config.load_credentials()

    if not credentials or not credentials.get("access_token"):
        print("Not logged in. Run 'sami login' first.", file=sys.stderr)
        sys.exit(1)

    api_url = config.get_api_url()
    client = SamiClient(api_url=api_url)
    client.auth.access_token = credentials["access_token"]
    client.auth.refresh_token = credentials.get("refresh_token")

    # Check token status
    token_was_expired = client.auth.is_token_expired()
    session_refreshed = False

    # If token is expired, try to refresh
    if token_was_expired and client.auth.refresh_token:
        try:
            client.auth.refresh()
            session_refreshed = True
            # Save refreshed tokens
            config.save_credentials(
                access_token=client.auth.access_token,
                refresh_token=client.auth.refresh_token,
                user_email=credentials.get("user_email"),
                organization_name=credentials.get("organization_name"),
            )
        except AuthenticationError:
            print("Session expired. Run 'sami login' to authenticate.", file=sys.stderr)
            sys.exit(1)

    # Try to get fresh user info from API
    try:
        user_info = client.get_current_user()

        print(f"Email: {user_info.get('email', 'Unknown')}")
        print(f"Name: {user_info.get('firstName', '')} {user_info.get('lastName', '')}")

        org = user_info.get("organization", {})
        print(f"Organization: {org.get('name', 'Unknown')}")
        print(f"Role: {user_info.get('globalRole', 'Unknown')}")
        print(f"Session: Valid" + (" (refreshed)" if session_refreshed else ""))

    except AuthenticationError:
        print("Session expired. Run 'sami login' to authenticate.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: Failed to verify session - {e}", file=sys.stderr)
        sys.exit(1)


# =============================================================================
# Config Command
# =============================================================================


def cmd_config(args):
    """Handle 'sami config' command."""
    config = SamiConfig()

    if args.api_url:
        # Set API URL
        config.set_api_url(args.api_url)
        print(f"API URL set to: {args.api_url}")
    elif args.reset:
        # Reset to default
        config.reset_api_url()
        print(f"API URL reset to default: {DEFAULT_API_URL}")
    else:
        # Show current config
        cfg = config.get_config()
        print(f"API URL: {cfg['api_url']}")
        print(f"Config directory: {cfg['config_dir']}")
        print(f"Logged in: {'Yes' if cfg['has_credentials'] else 'No'}")

        # Show if using env var
        if os.environ.get("SAMI_API_URL"):
            print("  (using SAMI_API_URL environment variable)")


# =============================================================================
# List Command
# =============================================================================


def cmd_list(args):
    """Handle 'sami list' command."""
    client = get_client()

    try:
        datasets = client.list_datasets(
            limit=args.limit,
            status=args.status,
        )

        if not datasets:
            print("No datasets found.")
            return

        # Print header
        print(f"{'ID':<36}  {'NAME':<30}  {'EPISODES':>8}  {'SIZE':>10}  {'STATUS':<10}")
        print("-" * 100)

        for ds in datasets:
            dataset_id = ds.id[:36] if ds.id else "N/A"
            name = (ds.name[:28] + "..") if len(ds.name or "") > 30 else (ds.name or "N/A")
            episodes = str(ds.episode_count) if ds.episode_count else "N/A"
            size = format_size(ds.file_size_bytes)
            status = ds.upload_status or "N/A"

            print(f"{dataset_id:<36}  {name:<30}  {episodes:>8}  {size:>10}  {status:<10}")

    except SamiError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


# =============================================================================
# Upload Command
# =============================================================================


def cmd_upload(args):
    """Handle 'sami upload' command."""
    import os.path

    # Validate path exists
    if not os.path.isdir(args.path):
        print(f"Error: Path does not exist or is not a directory: {args.path}", file=sys.stderr)
        sys.exit(1)

    client = get_client()

    try:
        print(f"Uploading dataset from {args.path}...")

        dataset = client.upload_dataset(
            name=args.name,
            path=args.path,
            description=args.description,
            task_category=args.task_category,
            max_workers=args.workers,
            strict=not args.no_strict,
        )

        print("")
        print("=" * 50)
        print("Upload Complete!")
        print("=" * 50)
        print(f"  Dataset ID:    {dataset.id}")
        print(f"  Name:          {dataset.name}")
        if dataset.episode_count:
            print(f"  Episodes:      {dataset.episode_count:,}")
        if dataset.total_frames:
            print(f"  Total Frames:  {int(dataset.total_frames):,}")
        if dataset.fps:
            print(f"  FPS:           {dataset.fps}")
        if dataset.robot_type:
            print(f"  Robot Type:    {dataset.robot_type}")
        print(f"  Status:        {dataset.upload_status}")
        print("=" * 50)

    except SamiError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


# =============================================================================
# Download Command
# =============================================================================


def cmd_download(args):
    """Handle 'sami download' command."""
    import time

    client = get_client()
    dataset_format = getattr(args, "format", "lerobot")

    try:
        # If HDF5 format requested, check if conversion is needed
        if dataset_format == "hdf5":
            print(f"Checking {dataset_format.upper()} format availability...")
            formats = client.list_formats(args.id)

            hdf5_format = next((f for f in formats if f.get("format") == "hdf5"), None)

            if not hdf5_format or hdf5_format.get("status") not in ["available", "completed"]:
                # Need to request conversion
                if hdf5_format and hdf5_format.get("status") in ["pending", "queued", "converting"]:
                    print("Conversion already in progress...")
                else:
                    print("Requesting HDF5 conversion...")
                    client.request_conversion(args.id, "hdf5")

                # Poll for completion with progress bar
                print("Converting to HDF5 format (this may take a while)...")
                while True:
                    status = client.get_conversion_status(args.id, "hdf5")
                    progress = status.get("progress", 0)
                    status_str = status.get("status", "unknown")

                    # Print progress
                    bar_len = 40
                    filled = int(bar_len * progress / 100)
                    bar = "█" * filled + "░" * (bar_len - filled)
                    print(f"\r  [{bar}] {progress:.0f}% - {status_str}", end="", flush=True)

                    if status_str == "completed":
                        print("\n  Conversion complete!")
                        break
                    elif status_str == "failed":
                        error_msg = status.get("errorMessage", "Unknown error")
                        print(f"\n  Conversion failed: {error_msg}", file=sys.stderr)
                        sys.exit(1)

                    time.sleep(2)
            else:
                print(f"HDF5 format is available.")

        print(f"Downloading dataset {args.id} in {dataset_format.upper()} format...")

        output_path = client.download_dataset(
            dataset_id=args.id,
            output_path=args.output,
            max_workers=args.workers,
            dataset_format=dataset_format,
        )

        print("")
        print(f"Downloaded to: {output_path}")

    except NotFoundError:
        print(f"Error: Dataset not found: {args.id}", file=sys.stderr)
        sys.exit(1)
    except SamiError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


# =============================================================================
# Info Command
# =============================================================================


def cmd_info(args):
    """Handle 'sami info' command."""
    client = get_client()

    try:
        ds = client.get_dataset(args.id)

        print(f"Dataset: {ds.name}")
        print("-" * 50)
        print(f"  ID:            {ds.id}")
        print(f"  Description:   {ds.description or 'N/A'}")
        print(f"  Status:        {ds.upload_status}")
        print(f"  Organization:  {ds.organization_name or 'N/A'}")
        print("")
        print("Metadata:")
        if ds.episode_count:
            print(f"  Episodes:      {ds.episode_count:,}")
        if ds.total_frames:
            print(f"  Total Frames:  {ds.total_frames:,}")
        if ds.fps:
            print(f"  FPS:           {ds.fps}")
        if ds.robot_type:
            print(f"  Robot Type:    {ds.robot_type}")
        if ds.file_size_bytes:
            print(f"  Size:          {format_size(ds.file_size_bytes)}")
        if ds.created_at:
            print(f"  Created:       {ds.created_at}")

        if ds.features:
            print("")
            print("Features:")
            for feature_name, feature_info in ds.features.items():
                print(f"  - {feature_name}: {feature_info}")

    except NotFoundError:
        print(f"Error: Dataset not found: {args.id}", file=sys.stderr)
        sys.exit(1)
    except SamiError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


# =============================================================================
# Delete Command
# =============================================================================


def cmd_delete(args):
    """Handle 'sami delete' command."""
    client = get_client()

    # Confirm deletion unless --force
    if not args.force:
        try:
            ds = client.get_dataset(args.id)
            confirm = input(f"Delete dataset '{ds.name}'? [y/N]: ")
            if confirm.lower() != "y":
                print("Cancelled.")
                return
        except NotFoundError:
            print(f"Error: Dataset not found: {args.id}", file=sys.stderr)
            sys.exit(1)

    try:
        client.delete_dataset(args.id)
        print(f"Deleted dataset: {args.id}")

    except NotFoundError:
        print(f"Error: Dataset not found: {args.id}", file=sys.stderr)
        sys.exit(1)
    except SamiError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


# =============================================================================
# Main Entry Point
# =============================================================================


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="sami",
        description="SAMI Dataset Distribution Platform CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  sami login                              # Login via browser (default)
  sami login --password                   # Login with email/password
  sami list                               # List accessible datasets
  sami upload ./dataset --name "My Data"  # Upload a dataset
  sami download abc123 --output ./data    # Download a dataset
  sami info abc123                        # Show dataset details

Environment Variables:
  SAMI_API_URL        Override API URL
  SAMI_ACCESS_TOKEN   Use token directly (skip login)
  SAMI_EMAIL          Email for login
  SAMI_PASSWORD       Password for login
""",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # -------------------------------------------------------------------------
    # sami login
    # -------------------------------------------------------------------------
    login_parser = subparsers.add_parser("login", help="Authenticate and save credentials")
    login_parser.add_argument(
        "--password", "-p",
        action="store_true",
        dest="password_flow",
        help="Use email/password login instead of browser authentication",
    )
    login_parser.add_argument("--email", help="Email for password login")
    login_parser.set_defaults(func=cmd_login)

    # -------------------------------------------------------------------------
    # sami logout
    # -------------------------------------------------------------------------
    logout_parser = subparsers.add_parser("logout", help="Clear saved credentials")
    logout_parser.set_defaults(func=cmd_logout)

    # -------------------------------------------------------------------------
    # sami whoami
    # -------------------------------------------------------------------------
    whoami_parser = subparsers.add_parser("whoami", help="Show current user info")
    whoami_parser.set_defaults(func=cmd_whoami)

    # -------------------------------------------------------------------------
    # sami config
    # -------------------------------------------------------------------------
    config_parser = subparsers.add_parser("config", help="View/set configuration")
    config_parser.add_argument("--api-url", help="Set API URL")
    config_parser.add_argument("--reset", action="store_true", help="Reset API URL to default")
    config_parser.set_defaults(func=cmd_config)

    # -------------------------------------------------------------------------
    # sami list
    # -------------------------------------------------------------------------
    list_parser = subparsers.add_parser("list", help="List accessible datasets")
    list_parser.add_argument(
        "--status",
        choices=["pending", "uploading", "processing", "ready", "failed"],
        help="Filter by status",
    )
    list_parser.add_argument("--limit", type=int, default=20, help="Number of results (default: 20)")
    list_parser.set_defaults(func=cmd_list)

    # -------------------------------------------------------------------------
    # sami upload
    # -------------------------------------------------------------------------
    upload_parser = subparsers.add_parser("upload", help="Upload a LeRobot dataset")
    upload_parser.add_argument("path", help="Path to LeRobot dataset directory")
    upload_parser.add_argument("--name", required=True, help="Dataset name")
    upload_parser.add_argument("--description", help="Dataset description")
    upload_parser.add_argument("--task-category", help="Task category (e.g., manipulation)")
    upload_parser.add_argument("--workers", type=int, default=4, help="Parallel upload workers (default: 4)")
    upload_parser.add_argument(
        "--no-strict",
        action="store_true",
        help="Allow partial datasets (missing videos/data)",
    )
    upload_parser.set_defaults(func=cmd_upload)

    # -------------------------------------------------------------------------
    # sami download
    # -------------------------------------------------------------------------
    download_parser = subparsers.add_parser("download", help="Download a dataset")
    download_parser.add_argument("id", help="Dataset ID")
    download_parser.add_argument("--output", default=".", help="Output directory (default: current)")
    download_parser.add_argument("--workers", type=int, default=4, help="Parallel download workers (default: 4)")
    download_parser.add_argument(
        "--format",
        choices=["lerobot", "hdf5"],
        default="lerobot",
        help="Download format: lerobot (default) or hdf5",
    )
    download_parser.set_defaults(func=cmd_download)

    # -------------------------------------------------------------------------
    # sami info
    # -------------------------------------------------------------------------
    info_parser = subparsers.add_parser("info", help="Show dataset details")
    info_parser.add_argument("id", help="Dataset ID")
    info_parser.set_defaults(func=cmd_info)

    # -------------------------------------------------------------------------
    # sami delete
    # -------------------------------------------------------------------------
    delete_parser = subparsers.add_parser("delete", help="Delete a dataset")
    delete_parser.add_argument("id", help="Dataset ID")
    delete_parser.add_argument("--force", action="store_true", help="Skip confirmation")
    delete_parser.set_defaults(func=cmd_delete)

    # -------------------------------------------------------------------------
    # Parse and execute
    # -------------------------------------------------------------------------
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
