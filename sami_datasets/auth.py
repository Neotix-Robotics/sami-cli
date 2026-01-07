"""Authentication for SAMI API."""

import base64
import json
import time
import requests
from typing import Optional
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

    def refresh(self) -> None:
        """Refresh the access token."""
        if not self.refresh_token:
            raise AuthenticationError("No refresh token available")

        response = requests.post(
            f"{self.api_url}/auth/refresh",
            json={"refreshToken": self.refresh_token},
        )

        if response.status_code != 200:
            raise AuthenticationError("Token refresh failed")

        data = response.json().get("data", {})
        self.access_token = data.get("accessToken")

    def get_headers(self) -> dict:
        """Get authorization headers."""
        if not self.access_token:
            raise AuthenticationError("Not authenticated. Call login() first.")
        return {"Authorization": f"Bearer {self.access_token}"}

    def is_authenticated(self) -> bool:
        """Check if currently authenticated."""
        return self.access_token is not None
