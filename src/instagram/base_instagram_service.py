"""
Instagram API Client Service Base Class

Provides core functionality for interacting with the Instagram Graph API including:
- Authentication and credential management 
- Rate limit handling with exponential backoff
- Error classification and recovery
- Request retries with circuit breaking
- Media upload and validation
- Response parsing and error handling

Usage Examples:
    Basic usage:
    >>> service = BaseInstagramService(api_key="key", account_id="123")
    >>> result = service.post_image("photo.jpg", "My caption")
    
    Error handling:
    >>> try:
    ...     service.post_carousel(["img1.jpg", "img2.jpg"])
    ... except RateLimitError as e:
    ...     # Wait and retry after rate limit expires
    ...     time.sleep(e.retry_after)
    ...     service.post_carousel(["img1.jpg", "img2.jpg"])
    
    With monitoring:
    >>> with ApiMonitor() as monitor:
    ...     try:
    ...         result = service.post_video("video.mp4")
    ...         monitor.track_api_call("post_video", success=True)
    ...     except Exception as e:
    ...         monitor.track_error("post_video", str(e))
"""

import os
import time
import json
import logging
import requests
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from pathlib import Path

from ..utils.monitor import ApiMonitor
from .errors import (
    AuthenticationError,
    RateLimitError, 
    MediaError,
    BusinessValidationError
)

logger = logging.getLogger(__name__)

class BaseInstagramService:
    """
    Base class for Instagram API services.
    
    Handles:
    - API authentication
    - Request retries
    - Rate limiting
    - Error handling
    - Response parsing
    - Media validation
    
    Args:
        api_key: Instagram API key
        account_id: Instagram account ID
        max_retries: Maximum number of retries (default: 3)
        retry_delay: Base delay between retries in seconds (default: 1)
        timeout: Request timeout in seconds (default: 30)
    """
    
    def __init__(
        self,
        api_key: str,
        account_id: str,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        timeout: int = 30
    ):
        # API credentials and configuration
        self.api_key = api_key
        self.account_id = account_id
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout
        
        # Rate limit tracking
        self._rate_limit_remaining = None
        self._rate_limit_reset = None
        
        # Request statistics 
        self._request_count = 0
        self._error_count = 0
        self._last_request_time = None
        
        # Initialize monitoring
        self._monitor = ApiMonitor()
        
    def verify_credentials(self) -> bool:
        """
        Verify API credentials are valid.
        
        Returns:
            bool: True if credentials are valid
            
        Raises:
            AuthenticationError: If credentials are invalid
            
        Example:
            >>> service = BaseInstagramService("key", "123")
            >>> if service.verify_credentials():
            ...     print("Credentials valid")
        """
        try:
            # Try to get account info as credential test
            self._make_request(
                "GET",
                f"/{self.account_id}",
                params={"fields": "id,name"}
            )
            return True
        except AuthenticationError:
            return False
            
    def post_image(
        self,
        image_path: Union[str, Path],
        caption: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Post a single image to Instagram.
        
        Args:
            image_path: Path to image file
            caption: Image caption
            **kwargs: Additional post parameters:
                - location_id: Location ID to tag
                - user_tags: List of user tags
                - first_comment: First comment on post
        
        Returns:
            dict: API response with media ID and status
            
        Raises:
            MediaError: If image is invalid
            RateLimitError: If rate limit exceeded
            
        Example:
            >>> result = service.post_image(
            ...     "photo.jpg",
            ...     "My photo!",
            ...     location_id="123456789",
            ...     user_tags=[{
            ...         "username": "friend",
            ...         "x": 0.5,
            ...         "y": 0.5
            ...     }]
            ... )
            >>> print(f"Posted with ID: {result['id']}")
        """
        # Validate image
        self._validate_image(image_path)
        
        # Prepare request data
        data = {
            "image_url": self._get_image_url(image_path),
            "caption": caption,
            **kwargs
        }
        
        # Upload image
        try:
            response = self._make_request(
                "POST",
                f"/{self.account_id}/media",
                json=data
            )
            
            # Track successful upload
            self._monitor.track_api_call(
                "post_image",
                success=True,
                media_id=response["id"]
            )
            
            return response
            
        except Exception as e:
            # Track failed upload
            self._monitor.track_error("post_image", str(e))
            raise
            
    def _make_request(
        self,
        method: str,
        endpoint: str,
        retry_count: int = 0,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Make an API request with retries and error handling.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            retry_count: Current retry attempt
            **kwargs: Request parameters
            
        Returns:
            dict: Parsed API response
            
        Raises:
            AuthenticationError: Invalid credentials
            RateLimitError: Rate limit exceeded
            MediaError: Invalid media
            BusinessValidationError: Business validation failed
        """
        # Add authentication
        kwargs.setdefault("headers", {}).update({
            "Authorization": f"Bearer {self.api_key}"
        })
        
        # Track request timing
        start_time = time.time()
        self._last_request_time = datetime.now()
        
        try:
            # Make request
            response = requests.request(
                method,
                f"https://graph.facebook.com/v16.0{endpoint}",
                timeout=self.timeout,
                **kwargs
            )
            
            # Update rate limit info
            self._update_rate_limits(response.headers)
            
            # Parse response
            data = response.json()
            
            if "error" in data:
                # Handle different error types
                error = data["error"]
                if error["code"] in (190, 2203007):
                    raise AuthenticationError(error)
                elif error["code"] == 4:
                    raise RateLimitError(error)
                elif error["code"] in range(2208001, 2208999):
                    raise MediaError(error)
                elif error["code"] in range(2207001, 2207999):
                    raise BusinessValidationError(error)
                    
                # Generic error - maybe retry
                if retry_count < self.max_retries:
                    # Exponential backoff
                    delay = self.retry_delay * (2 ** retry_count)
                    time.sleep(delay)
                    return self._make_request(
                        method,
                        endpoint,
                        retry_count + 1,
                        **kwargs
                    )
                    
                raise Exception(f"API Error: {error}")
                
            # Track successful request
            duration = time.time() - start_time
            self._monitor.track_api_call(
                endpoint,
                success=True,
                duration=duration
            )
            
            return data
            
        except requests.RequestException as e:
            # Track failed request
            self._monitor.track_error(endpoint, str(e))
            
            # Retry on connection errors
            if retry_count < self.max_retries:
                delay = self.retry_delay * (2 ** retry_count)
                time.sleep(delay)
                return self._make_request(
                    method,
                    endpoint,
                    retry_count + 1,
                    **kwargs
                )
                
            raise
            
    def _validate_image(self, image_path: Union[str, Path]):
        """
        Validate image file meets Instagram requirements.
        
        Args:
            image_path: Path to image file
            
        Raises:
            MediaError: If image is invalid
            
        Checks:
        - File exists
        - Valid image format
        - Size limits
        - Aspect ratio
        - Color space
        """
        from PIL import Image
        
        # Convert to Path
        path = Path(image_path)
        
        # Check file exists
        if not path.exists():
            raise MediaError({
                "message": f"Image file not found: {path}"
            })
            
        try:
            # Open and validate image
            with Image.open(path) as img:
                # Check format
                if img.format not in ("JPEG", "PNG"):
                    raise MediaError({
                        "message": "Image must be JPEG or PNG"
                    })
                    
                # Check dimensions
                width, height = img.size
                aspect = width / height
                
                if width < 320 or height < 320:
                    raise MediaError({
                        "message": "Image too small (min 320x320)"
                    })
                    
                if aspect < 0.8 or aspect > 1.91:
                    raise MediaError({
                        "message": "Invalid aspect ratio (must be 0.8-1.91)"
                    })
                    
                # Check color mode
                if img.mode not in ("RGB", "RGBA"):
                    raise MediaError({
                        "message": "Image must be RGB or RGBA"
                    })
                    
        except Exception as e:
            if not isinstance(e, MediaError):
                raise MediaError({
                    "message": f"Invalid image: {str(e)}"
                })
            raise
            
    def _update_rate_limits(self, headers: Dict[str, str]):
        """
        Update rate limit tracking from response headers.
        
        Args:
            headers: Response headers
            
        Rate limit headers:
        - X-App-Usage: App-level rate limit info
        - X-Rate-Limit-Remaining: Remaining requests
        - X-Rate-Limit-Reset: Time until reset
        """
        # Parse rate limit headers
        if "X-Rate-Limit-Remaining" in headers:
            self._rate_limit_remaining = int(
                headers["X-Rate-Limit-Remaining"]
            )
            
        if "X-Rate-Limit-Reset" in headers:
            self._rate_limit_reset = datetime.now() + timedelta(
                seconds=int(headers["X-Rate-Limit-Reset"])
            )
            
        # Check app usage
        if "X-App-Usage" in headers:
            usage = json.loads(headers["X-App-Usage"])
            
            # Log if nearing limits
            if usage.get("call_count", 0) > 80:
                logger.warning(
                    "Approaching API rate limit: "
                    f"{usage['call_count']}% used"
                )
                
    def _get_image_url(self, image_path: Union[str, Path]) -> str:
        """
        Get publicly accessible URL for image file.
        
        For testing, returns the file path. In production,
        would upload to CDN/object storage first.
        
        Args:
            image_path: Path to image file
            
        Returns:
            str: Public URL for the image
        """
        # TODO: Upload to storage and return URL
        return str(image_path)
        
    def __enter__(self):
        """Start monitoring when used as context manager."""
        self._monitor.start()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop monitoring and log any errors."""
        self._monitor.stop()
        if exc_type is not None:
            logger.error(
                f"Error in Instagram service: {exc_type.__name__}"
                f"\n{str(exc_val)}"
            )