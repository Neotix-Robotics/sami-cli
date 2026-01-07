"""Tests for sami_cli.auth module."""

import pytest
from unittest.mock import Mock, patch

from sami_cli.auth import SamiAuth
from sami_cli.exceptions import AuthenticationError


class TestSamiAuthUnit:
    """Unit tests for SamiAuth (mocked)."""

    @pytest.mark.unit
    def test_init(self):
        """Test SamiAuth initialization."""
        auth = SamiAuth("http://localhost:5001/api/v1")

        assert auth.api_url == "http://localhost:5001/api/v1"
        assert auth.access_token is None
        assert auth.refresh_token is None

    @pytest.mark.unit
    def test_init_strips_trailing_slash(self):
        """Test that trailing slash is stripped from URL."""
        auth = SamiAuth("http://localhost:5001/api/v1/")

        assert auth.api_url == "http://localhost:5001/api/v1"

    @pytest.mark.unit
    def test_get_headers_without_auth(self):
        """Test get_headers raises error when not authenticated."""
        auth = SamiAuth("http://localhost:5001/api/v1")

        with pytest.raises(AuthenticationError) as exc_info:
            auth.get_headers()

        assert "Not authenticated" in str(exc_info.value)

    @pytest.mark.unit
    def test_get_headers_with_token(self):
        """Test get_headers returns correct headers when authenticated."""
        auth = SamiAuth("http://localhost:5001/api/v1")
        auth.access_token = "test-token-123"

        headers = auth.get_headers()

        assert headers == {"Authorization": "Bearer test-token-123"}

    @pytest.mark.unit
    def test_is_authenticated_false(self):
        """Test is_authenticated returns False when not logged in."""
        auth = SamiAuth("http://localhost:5001/api/v1")

        assert auth.is_authenticated() is False

    @pytest.mark.unit
    def test_is_authenticated_true(self):
        """Test is_authenticated returns True when logged in."""
        auth = SamiAuth("http://localhost:5001/api/v1")
        auth.access_token = "some-token"

        assert auth.is_authenticated() is True

    @pytest.mark.unit
    @patch("sami_cli.auth.requests.post")
    def test_login_success(self, mock_post):
        """Test successful login."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "tokens": {
                    "access": {"token": "access-token-123"},
                    "refresh": {"token": "refresh-token-456"}
                }
            }
        }
        mock_post.return_value = mock_response

        auth = SamiAuth("http://localhost:5001/api/v1")
        auth.login("test@example.com", "password123")

        assert auth.access_token == "access-token-123"
        assert auth.refresh_token == "refresh-token-456"
        mock_post.assert_called_once()

    @pytest.mark.unit
    @patch("sami_cli.auth.requests.post")
    def test_login_failure(self, mock_post):
        """Test login failure."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {
            "error": {"message": "Invalid credentials"}
        }
        mock_post.return_value = mock_response

        auth = SamiAuth("http://localhost:5001/api/v1")

        with pytest.raises(AuthenticationError) as exc_info:
            auth.login("test@example.com", "wrongpassword")

        assert "Invalid credentials" in str(exc_info.value)

    @pytest.mark.unit
    @patch("sami_cli.auth.requests.post")
    def test_login_no_token_in_response(self, mock_post):
        """Test login fails when no token in response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {}}
        mock_post.return_value = mock_response

        auth = SamiAuth("http://localhost:5001/api/v1")

        with pytest.raises(AuthenticationError) as exc_info:
            auth.login("test@example.com", "password")

        assert "No access token" in str(exc_info.value)


class TestSamiAuthIntegration:
    """Integration tests for SamiAuth (requires running backend)."""

    @pytest.mark.integration
    def test_login_with_valid_credentials(self, api_url: str, test_credentials: dict):
        """Test login with valid credentials."""
        auth = SamiAuth(api_url)
        auth.login(test_credentials["email"], test_credentials["password"])

        assert auth.access_token is not None
        assert auth.is_authenticated() is True

    @pytest.mark.integration
    def test_login_with_invalid_credentials(self, api_url: str):
        """Test login with invalid credentials."""
        auth = SamiAuth(api_url)

        with pytest.raises(AuthenticationError):
            auth.login("nonexistent@example.com", "wrongpassword")

    @pytest.mark.integration
    def test_get_headers_after_login(self, api_url: str, test_credentials: dict):
        """Test headers are correct after login."""
        auth = SamiAuth(api_url)
        auth.login(test_credentials["email"], test_credentials["password"])

        headers = auth.get_headers()

        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Bearer ")
