"""
Instagram API Error Handling Module

Provides specialized exception classes and error handling utilities for Instagram API interactions.
Each exception type corresponds to specific API error codes and scenarios, with proper error
recovery strategies and debugging information.

Error Categories:
- Authentication & Authorization
- Rate Limiting & Quotas
- Media Processing
- Network & Communication
- Business Rules & Validation

Usage Example:
    try:
        result = instagram.post_image(image_path)
    except RateLimitError as e:
        logger.warning(f"Rate limited. Retry after {e.retry_after} seconds")
        time.sleep(e.retry_after)
    except MediaError as e:
        logger.error(f"Media processing failed: {e.details}")
"""

from typing import Optional, Dict, Any
import logging
import json

logger = logging.getLogger(__name__)

class InstagramAPIError(Exception):
    """
    Base exception class for Instagram API errors.
    
    Attributes:
        message: Error description
        code: Instagram API error code
        subcode: Detailed error subcode
        fbtrace_id: Facebook trace ID for debugging
        details: Additional error context
        
    Example:
        >>> try:
        ...     raise InstagramAPIError("API Error", code=190)
        ... except InstagramAPIError as e:
        ...     print(f"Error {e.code}: {e.message}")
    """
    
    def __init__(self, 
                 message: str, 
                 code: Optional[int] = None,
                 subcode: Optional[int] = None,
                 fbtrace_id: Optional[str] = None,
                 details: Optional[Dict[str, Any]] = None):
        """
        Initialize Instagram API error.
        
        Args:
            message: Human-readable error description
            code: Instagram API error code
            subcode: Specific error subcode
            fbtrace_id: Facebook debugging trace ID
            details: Additional error context
            
        Error Response Example:
            {
                "error": {
                    "message": "Invalid OAuth access token",
                    "type": "OAuthException",
                    "code": 190,
                    "error_subcode": 460,
                    "fbtrace_id": "AXLVf5yZGZt"
                }
            }
        """
        self.message = message
        self.code = code
        self.subcode = subcode
        self.fbtrace_id = fbtrace_id
        self.details = details or {}
        
        super().__init__(self.message)
        
    def __str__(self) -> str:
        """Format error message with code and trace ID."""
        parts = [self.message]
        if self.code:
            parts.append(f"(Code: {self.code})")
        if self.subcode:
            parts.append(f"(Subcode: {self.subcode})")
        if self.fbtrace_id:
            parts.append(f"[Trace: {self.fbtrace_id}]")
        return " ".join(parts)

class AuthenticationError(InstagramAPIError):
    """
    Raised for authentication and authorization failures.
    
    Common scenarios:
    - Invalid or expired access token
    - Missing required permissions
    - Invalid app secret proof
    - Account status issues
    
    Example:
        >>> try:
        ...     api.verify_token()
        ... except AuthenticationError as e:
        ...     if e.code == 190:  # Invalid token
        ...         refresh_token()
        ...     elif e.code == 200:  # Permission error
        ...         request_permissions()
    """
    
    ERROR_CODES = {
        190: "Invalid access token",
        200: "Permission error",
        104: "Requires valid signature",
        803: "Business account required"
    }
    
    def __init__(self, message: str, **kwargs):
        """Initialize authentication error with specific code mapping."""
        super().__init__(message, **kwargs)
        
        # Log authentication failures
        logger.error(f"Authentication failed: {self}")
        
        # Add helpful resolution hints
        if self.code in self.ERROR_CODES:
            self.details["resolution"] = {
                190: "Generate new access token",
                200: "Request missing permissions",
                104: "Check app secret and signature",
                803: "Convert to business account"
            }.get(self.code)

class RateLimitError(InstagramAPIError):
    """
    Raised when API rate limits are exceeded.
    
    Features:
    - Automatic retry-after calculation
    - Rate limit window tracking
    - Usage quota monitoring
    - Backoff strategy hints
    
    Example:
        >>> try:
        ...     api.post_media()
        ... except RateLimitError as e:
        ...     if e.is_temporary():
        ...         time.sleep(e.retry_after)
        ...         retry_request()
        ...     else:
        ...         notify_quota_exceeded()
    """
    
    def __init__(self, 
                 message: str,
                 retry_after: Optional[int] = None,
                 **kwargs):
        """
        Initialize rate limit error.
        
        Args:
            message: Error description
            retry_after: Seconds until limit resets
            **kwargs: Additional Instagram API error details
            
        Rate Limit Response Example:
            {
                "error": {
                    "message": "Application request limit reached",
                    "code": 4,
                    "error_subcode": 2207051,
                    "fbtrace_id": "ABC123",
                    "retry_after": 3600
                }
            }
        """
        super().__init__(message, **kwargs)
        self.retry_after = retry_after or 3600  # Default 1 hour
        
        # Track rate limit state
        self.limit_type = self._determine_limit_type()
        self.is_app_limit = self.subcode == 2207051
        
        # Log rate limit hit
        logger.warning(
            f"Rate limit hit: {self.limit_type}. "
            f"Retry after {self.retry_after} seconds"
        )
        
    def _determine_limit_type(self) -> str:
        """Determine type of rate limit from error details."""
        if self.subcode == 2207051:
            return "application"
        elif self.code == 613:
            return "per-user"
        elif self.code == 4:
            return "general"
        return "unknown"
        
    def is_temporary(self) -> bool:
        """Check if rate limit is temporary or quota exceeded."""
        return not self.is_app_limit

class MediaError(InstagramAPIError):
    """
    Raised for media processing and validation errors.
    
    Handles:
    - Format validation failures
    - Size limit violations
    - Processing errors
    - Missing media errors
    
    Example:
        >>> try:
        ...     api.upload_video(video_path)
        ... except MediaError as e:
        ...     if e.is_format_error():
        ...         convert_video_format()
        ...     elif e.is_size_error():
        ...         compress_video()
    """
    
    ERROR_TYPES = {
        'format': ['invalid_format', 'unsupported_format'],
        'size': ['file_too_large', 'dimension_error'],
        'processing': ['transcoding_error', 'upload_error'],
        'missing': ['media_not_found', 'container_error']
    }
    
    def __init__(self, message: str, error_type: str = None, **kwargs):
        """
        Initialize media error with type classification.
        
        Args:
            message: Error description
            error_type: Category of media error
            **kwargs: Additional error details
        """
        super().__init__(message, **kwargs)
        self.error_type = error_type
        
        # Add resolution hints
        self.details['resolution'] = self._get_resolution_hint()
        
        # Log with appropriate level
        if self.is_recoverable():
            logger.warning(f"Recoverable media error: {self}")
        else:
            logger.error(f"Fatal media error: {self}")
            
    def _get_resolution_hint(self) -> str:
        """Get hint for resolving the media error."""
        if self.is_format_error():
            return "Convert to supported format (MP4/JPEG)"
        elif self.is_size_error():
            return "Reduce file size or dimensions"
        elif self.is_processing_error():
            return "Retry upload or check encoding"
        return "Verify media file exists and is valid"
        
    def is_format_error(self) -> bool:
        """Check if error is related to media format."""
        return self.error_type in self.ERROR_TYPES['format']
        
    def is_size_error(self) -> bool:
        """Check if error is related to media size."""
        return self.error_type in self.ERROR_TYPES['size']
        
    def is_processing_error(self) -> bool:
        """Check if error occurred during processing."""
        return self.error_type in self.ERROR_TYPES['processing']
        
    def is_recoverable(self) -> bool:
        """Check if error can be recovered from."""
        return self.is_format_error() or self.is_size_error()

class BusinessValidationError(InstagramAPIError):
    """
    Raised when business rule validations fail.
    
    Handles:
    - Account type requirements
    - Content policy violations
    - Geographic restrictions
    - Feature availability checks
    
    Example:
        >>> try:
        ...     api.create_carousel()
        ... except BusinessValidationError as e:
        ...     if e.requires_business_account():
        ...         convert_to_business()
        ...     elif e.is_policy_violation():
        ...         review_content_guidelines()
    """
    
    def __init__(self, message: str, violated_rules: Optional[List[str]] = None, **kwargs):
        """
        Initialize business validation error.
        
        Args:
            message: Error description
            violated_rules: List of violated business rules
            **kwargs: Additional error context
        """
        super().__init__(message, **kwargs)
        self.violated_rules = violated_rules or []
        
        # Log violation details
        logger.error(
            f"Business validation failed: {self.message}\n"
            f"Violated rules: {', '.join(self.violated_rules)}"
        )
        
    def requires_business_account(self) -> bool:
        """Check if error requires business account."""
        return self.code == 803
        
    def is_policy_violation(self) -> bool:
        """Check if error is content policy violation."""
        return any(rule.startswith('policy_') for rule in self.violated_rules)
        
    def get_resolution_steps(self) -> List[str]:
        """Get ordered list of resolution steps."""
        steps = []
        if self.requires_business_account():
            steps.append("Convert to business account")
        if self.is_policy_violation():
            steps.append("Review content guidelines")
            steps.append("Modify content to comply with policies")
        return steps