"""Authentication for SAMI API."""

import base64
import json
import time
import webbrowser
import requests
from typing import Optional, Dict, Any, Tuple
from .exceptions import AuthenticationError


class SamiAuth:
    """Handles authentication with SAMI API."""

    def __init__(self, api_url: str):
        self.api_url = api_url.rstrip("/")
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None

    def is_token_expired(self) -> bool:
        """Check if the access token is expired.

        Returns:
            True if token is expired or invalid, False otherwise.
        """
        if not self.access_token:
            return True

        try:
            # JWT format: header.payload.signature
            parts = self.access_token.split(".")
            if len(parts) != 3:
                return True

            # Decode payload (add padding if needed)
            payload = parts[1]
            padding = 4 - len(payload) % 4
            if padding != 4:
                payload += "=" * padding

            decoded = base64.urlsafe_b64decode(payload)
            claims = json.loads(decoded)

            # Check expiration with 60 second buffer
            exp = claims.get("exp", 0)
            return time.time() >= (exp - 60)

        except Exception:
            # If we can't decode, assume expired
            return True

    def login(self, email: str, password: str) -> None:
        """Authenticate with email and password."""
        response = requests.post(
            f"{self.api_url}/auth/login",
            json={"email": email, "password": password},
        )

        if response.status_code != 200:
            try:
                error = response.json().get("error", {}).get("message", "Authentication failed")
            except Exception:
                error = f"Authentication failed with status {response.status_code}"
            raise AuthenticationError(error)

        data = response.json().get("data", {})

        # Handle nested token structure: data.tokens.access.token
        tokens = data.get("tokens", {})
        access_info = tokens.get("access", {})
        self.access_token = access_info.get("token")

        # Refresh token may be in cookies (httpOnly) or in response
        refresh_info = tokens.get("refresh", {})
        self.refresh_token = refresh_info.get("token")

        if not self.access_token:
            raise AuthenticationError("No access token received")

    def refresh(self) -> bool:
        """Refresh the access token using the refresh token.

        Returns:
            True if refresh succeeded, False otherwise.

        Raises:
            AuthenticationError: If no refresh token available or refresh fails.
        """
        if not self.refresh_token:
            raise AuthenticationError("No refresh token available. Please login again.")

        response = requests.post(
            f"{self.api_url}/auth/refresh-token",
            json={"refreshToken": self.refresh_token},
        )

        if response.status_code != 200:
            # Refresh failed - token may be expired or revoked
            raise AuthenticationError("Session expired. Please login again.")

        data = response.json().get("data", {})

        # Parse tokens from response: data.access.token and data.refresh.token
        access_info = data.get("access", {})
        refresh_info = data.get("refresh", {})

        new_access_token = access_info.get("token")
        new_refresh_token = refresh_info.get("token")

        if not new_access_token:
            raise AuthenticationError("Invalid refresh response. Please login again.")

        self.access_token = new_access_token
        if new_refresh_token:
            self.refresh_token = new_refresh_token

        return True

    def get_headers(self, auto_refresh: bool = True) -> dict:
        """Get authorization headers.

        Args:
            auto_refresh: If True, automatically refresh expired tokens.

        Returns:
            Dictionary with Authorization header.

        Raises:
            AuthenticationError: If not authenticated or refresh fails.
        """
        if not self.access_token:
            raise AuthenticationError("Not authenticated. Call login() first.")

        # Check if token is expired and try to refresh
        if auto_refresh and self.is_token_expired() and self.refresh_token:
            try:
                self.refresh()
            except AuthenticationError:
                # If refresh fails, continue with expired token
                # The server will return 401 and the caller can handle it
                pass

        return {"Authorization": f"Bearer {self.access_token}"}

    def is_authenticated(self) -> bool:
        """Check if currently authenticated."""
        return self.access_token is not None

    def start_device_flow(self) -> Dict[str, Any]:
        """Start device code flow for CLI authentication.

        Returns:
            Dict containing:
            - device_code: str - Code to use for polling
            - user_code: str - Code to display to user (XXXX-XXXX format)
            - verification_uri: str - URL for user to visit
            - verification_uri_complete: str - URL with code pre-filled
            - expires_in: int - Seconds until codes expire
            - interval: int - Polling interval in seconds

        Raises:
            AuthenticationError: If device code request fails
        """
        response = requests.post(
            f"{self.api_url}/auth/device/code",
            json={"client_id": "sami-cli"},
        )

        if response.status_code != 200:
            try:
                error = response.json().get("error", {}).get("message", "Failed to start device flow")
            except Exception:
                error = f"Failed to start device flow with status {response.status_code}"
            raise AuthenticationError(error)

        return response.json().get("data", {})

    def poll_device_token(
        self,
        device_code: str,
        interval: int = 5,
        timeout: int = 600,
        open_browser: bool = True,
        verification_uri_complete: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Poll for device token until authorized or timeout.

        Args:
            device_code: The device code from start_device_flow()
            interval: Initial polling interval in seconds
            timeout: Maximum time to wait in seconds
            open_browser: Whether to auto-open browser
            verification_uri_complete: URL with code pre-filled for browser

        Returns:
            Tuple of (access_token, refresh_token)

        Raises:
            AuthenticationError: If authorization fails, is denied, or times out
        """
        # Auto-open browser if requested
        if open_browser and verification_uri_complete:
            try:
                webbrowser.open(verification_uri_complete)
            except Exception:
                pass  # Browser open is optional, don't fail if it doesn't work

        start_time = time.time()
        current_interval = interval

        while time.time() - start_time < timeout:
            time.sleep(current_interval)

            response = requests.post(
                f"{self.api_url}/auth/device/token",
                json={
                    "client_id": "sami-cli",
                    "device_code": device_code,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                },
            )

            if response.status_code == 200:
                # Success - extract tokens
                data = response.json().get("data", {})
                self.access_token = data.get("access_token")
                self.refresh_token = data.get("refresh_token")

                if not self.access_token:
                    raise AuthenticationError("No access token in response")

                return (self.access_token, self.refresh_token or "")

            # Handle error responses
            try:
                error_data = response.json().get("error", {})
                error_code = error_data.get("code", "")
                error_message = error_data.get("message", "Unknown error")
            except Exception:
                error_code = ""
                error_message = f"Request failed with status {response.status_code}"

            if error_code == "authorization_pending":
                # User hasn't authorized yet, keep polling
                continue
            elif error_code == "slow_down":
                # Polling too fast, increase interval
                current_interval += 5
                continue
            elif error_code == "expired_token":
                raise AuthenticationError("Device code expired. Please try again.")
            elif error_code == "access_denied":
                raise AuthenticationError("Authorization was denied.")
            else:
                raise AuthenticationError(f"Device authorization failed: {error_message}")

        raise AuthenticationError("Device authorization timed out. Please try again.")
