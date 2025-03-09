"""
This module contains all custom exceptions used throughout the Instagram integration.
All exceptions inherit from the base InstagramError class.
"""

class InstagramError(Exception):
    """Base exception class for all Instagram-related errors."""
    def __init__(self, message, error_code=None, error_subcode=None, fbtrace_id=None):
        self.error_code = error_code
        self.error_subcode = error_subcode
        self.fbtrace_id = fbtrace_id
        super().__init__(message)

    def __str__(self):
        base_message = super().__str__()
        if self.error_code or self.error_subcode or self.fbtrace_id:
            return f"{base_message} (Code: {self.error_code}, Subcode: {self.error_subcode}, Trace ID: {self.fbtrace_id})"
        return base_message

class AuthenticationError(InstagramError):
    """Raised for authentication failures (token expired, invalid, etc)."""
    pass

class PermissionError(InstagramError):
    """Raised for permission-related errors (missing scopes, etc)."""
    pass

class RateLimitError(InstagramError):
    """Raised when API rate limits are exceeded."""
    def __init__(self, message, retry_seconds=300, error_code=None, error_subcode=None, fbtrace_id=None):
        super().__init__(message, error_code, error_subcode, fbtrace_id)
        self.retry_seconds = retry_seconds

class MediaError(InstagramError):
    """Raised for media-related errors (format, size, upload failures)."""
    pass

class TemporaryServerError(InstagramError):
    """Raised for temporary Instagram server errors that may be retried."""
    pass

class CarouselError(InstagramError):
    """Base class for carousel-related errors."""
    def __init__(self, message, error_code=None, error_subcode=None, fbtrace_id=None, retriable=False):
        super().__init__(message, error_code, error_subcode, fbtrace_id)
        self.retriable = retriable

class ValidationError(InstagramError):
    """Raised when media or data validation fails."""
    pass

class ConfigurationError(InstagramError):
    """Raised for configuration-related errors (missing credentials, etc)."""
    pass