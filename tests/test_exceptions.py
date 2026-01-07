"""Unit tests for sami_cli.exceptions module."""

import pytest

from sami_cli.exceptions import (
    SamiError,
    AuthenticationError,
    NotFoundError,
    PermissionDeniedError,
    UploadError,
    DownloadError,
    ValidationError,
)


class TestExceptionHierarchy:
    """Tests for exception class hierarchy."""

    @pytest.mark.unit
    def test_sami_error_is_base(self):
        """Test SamiError is the base exception."""
        assert issubclass(AuthenticationError, SamiError)
        assert issubclass(NotFoundError, SamiError)
        assert issubclass(PermissionDeniedError, SamiError)
        assert issubclass(UploadError, SamiError)
        assert issubclass(DownloadError, SamiError)
        assert issubclass(ValidationError, SamiError)

    @pytest.mark.unit
    def test_exceptions_inherit_from_exception(self):
        """Test all exceptions inherit from Exception."""
        exceptions = [
            SamiError,
            AuthenticationError,
            NotFoundError,
            PermissionDeniedError,
            UploadError,
            DownloadError,
            ValidationError,
        ]
        for exc_class in exceptions:
            assert issubclass(exc_class, Exception)

    @pytest.mark.unit
    def test_exception_messages(self):
        """Test exceptions can be raised with messages."""
        msg = "Test error message"

        exceptions = [
            SamiError(msg),
            AuthenticationError(msg),
            NotFoundError(msg),
            PermissionDeniedError(msg),
            UploadError(msg),
            DownloadError(msg),
            ValidationError(msg),
        ]

        for exc in exceptions:
            assert str(exc) == msg

    @pytest.mark.unit
    def test_catch_by_base_class(self):
        """Test catching specific exceptions by base class."""
        with pytest.raises(SamiError):
            raise AuthenticationError("Auth failed")

        with pytest.raises(SamiError):
            raise UploadError("Upload failed")

    @pytest.mark.unit
    def test_exception_in_except_block(self):
        """Test exceptions work correctly in try-except blocks."""
        def raise_auth_error():
            raise AuthenticationError("Invalid credentials")

        try:
            raise_auth_error()
            assert False, "Should have raised"
        except AuthenticationError as e:
            assert "Invalid credentials" in str(e)
        except SamiError:
            assert False, "Should have been caught by AuthenticationError"
