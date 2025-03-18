"""
Este módulo contém todas as exceções personalizadas usadas na integração com o Instagram.
Todas as exceções herdam da classe base InstagramError.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime

@dataclass
class ErrorDetails:
    code: Optional[int] = None
    subcode: Optional[int] = None
    type: Optional[str] = None
    message: str = "Unknown error"
    fbtrace_id: Optional[str] = None
    timestamp: datetime = datetime.now()

class InstagramError(Exception):
    """Base exception for Instagram API errors"""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

class AuthenticationError(InstagramError):
    """Raised when there are authentication issues"""
    def __init__(self, message: str, code: int = None):
        self.code = code
        super().__init__(message)
        
    def is_expired_token(self) -> bool:
        """Check if error is due to expired token"""
        return self.code == 190
        
    def is_permission_error(self) -> bool:
        """Check if error is due to insufficient permissions"""
        return self.code == 200

class RateLimitError(InstagramError):
    """Raised when Instagram API rate limit is exceeded"""
    def __init__(self, message: str, retry_after: int = None):
        self.retry_after = retry_after
        super().__init__(message)
        
    def is_temporary(self) -> bool:
        """Check if rate limit is temporary"""
        return self.retry_after is not None and self.retry_after < 3600

class MediaError(InstagramError):
    """Raised when there are issues with media files"""
    def __init__(self, message: str, media_type: str = None):
        self.media_type = media_type
        super().__init__(message)
        
    def is_size_error(self) -> bool:
        """Check if error is related to file size"""
        return "size" in self.message.lower()
        
    def is_format_error(self) -> bool:
        """Check if error is related to file format"""
        return "format" in self.message.lower()

class MediaValidationError(InstagramError):
    """Raised when media validation fails"""
    def __init__(self, message: str, validation_details: Dict[str, Any] = None):
        self.validation_details = validation_details or {}
        super().__init__(message)
        
    def is_dimension_error(self) -> bool:
        """Check if error is related to media dimensions"""
        return "dimension" in self.message.lower()
        
    def is_aspect_ratio_error(self) -> bool:
        """Check if error is related to aspect ratio"""
        return "aspect ratio" in self.message.lower()

class ContentPolicyViolation(InstagramError):
    """Raised when content violates Instagram policies"""
    def __init__(self, message: str, policy_code: str = None):
        self.policy_code = policy_code
        super().__init__(message)

class BusinessValidationError(InstagramError):
    """Raised when business validation fails"""
    def __init__(self, message: str, validation_code: str = None):
        self.validation_code = validation_code
        super().__init__(message)
        
    def requires_business_account(self) -> bool:
        """Check if error requires business account"""
        return self.validation_code == "NOT_BUSINESS_ACCOUNT"
        
    def is_policy_violation(self) -> bool:
        """Check if error is policy violation"""
        return self.validation_code == "POLICY_VIOLATION"

class CarouselError(InstagramError):
    """Raised when there are issues with carousel posts"""
    def __init__(self, message: str, carousel_id: str = None):
        self.carousel_id = carousel_id
        super().__init__(message)

class VideoError(InstagramError):
    """Raised when there are issues with video posts"""
    def __init__(self, message: str, video_id: str = None):
        self.video_id = video_id
        super().__init__(message)