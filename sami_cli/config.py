"""Configuration and credentials management for SAMI CLI.

Handles reading/writing config and credentials from ~/.sami/ directory.
"""

import json
import os
import stat
from pathlib import Path
from typing import Optional


# Default API URL
DEFAULT_API_URL = "https://api.dextero.co/api/v1"


class SamiConfig:
    """Manages SAMI configuration and credentials storage.

    Files are stored in ~/.sami/:
    - config.json: API URL and other preferences
    - credentials.json: Access and refresh tokens (chmod 600)
    """

    CONFIG_DIR = Path.home() / ".sami"
    CONFIG_FILE = CONFIG_DIR / "config.json"
    CREDENTIALS_FILE = CONFIG_DIR / "credentials.json"

    def __init__(self):
        """Initialize config manager."""
        self._ensure_config_dir()

    def _ensure_config_dir(self) -> None:
        """Create config directory if it doesn't exist."""
        self.CONFIG_DIR.mkdir(mode=0o700, exist_ok=True)

    def _set_secure_permissions(self, filepath: Path) -> None:
        """Set file permissions to 600 (owner read/write only)."""
        os.chmod(filepath, stat.S_IRUSR | stat.S_IWUSR)

    # =========================================================================
    # Credentials Management
    # =========================================================================

    def save_credentials(
        self,
        access_token: str,
        refresh_token: Optional[str] = None,
        user_email: Optional[str] = None,
        organization_name: Optional[str] = None,
    ) -> None:
        """Save authentication credentials to disk.

        Args:
            access_token: JWT access token
            refresh_token: JWT refresh token (optional)
            user_email: User's email for display purposes
            organization_name: Organization name for display purposes
        """
        credentials = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user_email": user_email,
            "organization_name": organization_name,
        }

        with open(self.CREDENTIALS_FILE, "w") as f:
            json.dump(credentials, f, indent=2)

        # Set secure permissions (owner read/write only)
        self._set_secure_permissions(self.CREDENTIALS_FILE)

    def load_credentials(self) -> Optional[dict]:
        """Load credentials from disk.

        Returns:
            Dictionary with access_token, refresh_token, user_email,
            organization_name, or None if not logged in.
        """
        if not self.CREDENTIALS_FILE.exists():
            return None

        try:
            with open(self.CREDENTIALS_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    def clear_credentials(self) -> None:
        """Remove saved credentials (logout)."""
        if self.CREDENTIALS_FILE.exists():
            self.CREDENTIALS_FILE.unlink()

    def has_credentials(self) -> bool:
        """Check if credentials file exists."""
        return self.CREDENTIALS_FILE.exists()

    # =========================================================================
    # Configuration Management
    # =========================================================================

    def _load_config(self) -> dict:
        """Load config file or return empty dict."""
        if not self.CONFIG_FILE.exists():
            return {}

        try:
            with open(self.CONFIG_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _save_config(self, config: dict) -> None:
        """Save config to disk."""
        with open(self.CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)

    def get_api_url(self) -> str:
        """Get the API URL.

        Priority: SAMI_API_URL env var > saved config > default

        Returns:
            API URL string
        """
        # Environment variable takes priority
        env_url = os.environ.get("SAMI_API_URL")
        if env_url:
            return env_url.rstrip("/")

        # Check saved config
        config = self._load_config()
        saved_url = config.get("api_url")
        if saved_url:
            return saved_url.rstrip("/")

        # Fall back to default
        return DEFAULT_API_URL

    def set_api_url(self, url: str) -> None:
        """Save API URL to config.

        Args:
            url: API URL to save
        """
        config = self._load_config()
        config["api_url"] = url.rstrip("/")
        self._save_config(config)

    def get_config(self) -> dict:
        """Get all configuration values.

        Returns:
            Dictionary with all config values including computed ones.
        """
        config = self._load_config()
        return {
            "api_url": self.get_api_url(),
            "config_dir": str(self.CONFIG_DIR),
            "has_credentials": self.has_credentials(),
            **config,
        }

    def reset_api_url(self) -> None:
        """Reset API URL to default."""
        config = self._load_config()
        config.pop("api_url", None)
        self._save_config(config)
