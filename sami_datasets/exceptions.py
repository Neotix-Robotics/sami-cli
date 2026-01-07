"""Custom exceptions for SAMI Datasets SDK."""


class SamiError(Exception):
    """Base exception for SAMI SDK."""
    pass


class AuthenticationError(SamiError):
    """Raised when authentication fails."""
    pass


class NotFoundError(SamiError):
    """Raised when a resource is not found."""
    pass


class PermissionDeniedError(SamiError):
    """Raised when user lacks permission."""
    pass


class UploadError(SamiError):
    """Raised when upload fails."""
    pass


class DownloadError(SamiError):
    """Raised when download fails."""
    pass


class ValidationError(SamiError):
    """Raised when dataset validation fails."""
    pass
