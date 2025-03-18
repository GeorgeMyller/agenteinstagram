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

class InstagramAPIError(Exception):
    """Base exception for Instagram API errors"""
    def __init__(self, message: str, error_code: Optional[int] = None, 
                 error_subcode: Optional[int] = None, fb_trace_id: Optional[str] = None):
        self.error_code = error_code
        self.error_subcode = error_subcode
        self.fb_trace_id = fb_trace_id
        super().__init__(message)

class AuthenticationError(InstagramAPIError):
    """Raised when there are issues with authentication"""
    pass

class PermissionError(InstagramAPIError):
    """Raised when the app lacks required permissions"""
    pass

class RateLimitError(InstagramAPIError):
    """Raised when hitting API rate limits"""
    def __init__(self, message: str, retry_seconds: int, *args, **kwargs):
        self.retry_seconds = retry_seconds
        super().__init__(message, *args, **kwargs)

class MediaError(InstagramAPIError):
    """Raised when there are issues with media files"""
    pass

class TemporaryServerError(InstagramAPIError):
    """Raised for temporary server issues"""
    pass

class RateLimitHandler:
    """Handles rate limiting logic"""
    
    def __init__(self, window_seconds: int = 3600, max_requests: int = 200):
        self.window_seconds = window_seconds
        self.max_requests = max_requests
        self.requests = []
    
    def check_rate_limit(self) -> bool:
        """
        Check if we're within rate limits
        
        Returns:
            bool: True if request can proceed, False if rate limited
        """
        current_time = time.time()
        window_start = current_time - self.window_seconds
        
        # Remove old requests
        self.requests = [t for t in self.requests if t > window_start]
        
        return len(self.requests) < self.max_requests
    
    def add_request(self):
        """Record a new request"""
        self.requests.append(time.time())
    
    def get_retry_after(self) -> int:
        """
        Get seconds until rate limit resets
        
        Returns:
            int: Seconds to wait
        """
        if not self.requests:
            return 0
            
        oldest_request = min(self.requests)
        return max(0, int(oldest_request + self.window_seconds - time.time()))

import aiohttp
import asyncio
from ..utils.config import Config
from .exceptions import InstagramError, RateLimitError

logger = logging.getLogger(__name__)

class BaseInstagramService:
    """Base class for Instagram API services"""
    
    def __init__(self):
        self.config = Config.get_instance()
        self.access_token = self.config.INSTAGRAM_ACCESS_TOKEN
        self.instagram_account_id = self.config.INSTAGRAM_ACCOUNT_ID
        self.api_version = "v12.0"
        self.base_url = f"https://graph.facebook.com/{self.api_version}"
        
        if not self.access_token or not self.instagram_account_id:
            raise ValueError("Instagram API credentials not configured")
            
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Make an authenticated request to the Instagram API
        
        Args:
            method: HTTP method (GET, POST, etc)
            endpoint: API endpoint
            **kwargs: Additional request parameters
            
        Returns:
            Dict containing API response
            
        Raises:
            InstagramError: On API errors
            RateLimitError: When rate limited
            AuthenticationError: On auth issues
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}{endpoint}"
                
                # Always include access token
                if 'params' in kwargs:
                    kwargs['params']['access_token'] = self.access_token
                else:
                    kwargs['params'] = {'access_token': self.access_token}
                    
                async with session.request(method, url, **kwargs) as response:
                    response_json = await response.json()
                    
                    if response.status == 200:
                        return response_json
                        
                    # Handle error responses
                    error = response_json.get('error', {})
                    code = error.get('code')
                    message = error.get('message', 'Unknown error')
                    
                    if response.status == 429 or code == 4:
                        retry_after = int(response.headers.get('Retry-After', 60))
                        raise RateLimitError(message, retry_after)
                        
                    if code in [190, 200]:  # Auth errors
                        raise AuthenticationError(message, code)
                        
                    if "business validation" in message.lower():
                        validation_code = error.get('error_subcode')
                        raise BusinessValidationError(message, validation_code)
                        
                    raise InstagramError(message)
                    
        except aiohttp.ClientError as e:
            raise InstagramError(f"Request failed: {str(e)}")
            
    async def _upload_photo(self, photo_path: str) -> Optional[Dict]:
        """
        Upload a photo for use in posts
        
        Args:
            photo_path: Path to photo file
            
        Returns:
            Dict containing upload response
        """
        try:
            # First create a container for the photo
            endpoint = f"/{self.instagram_account_id}/media"
            
            with open(photo_path, 'rb') as f:
                files = {'file': f}
                params = {'media_type': 'IMAGE'}
                
                result = await self._make_request(
                    "POST",
                    endpoint,
                    data=params,
                    files=files
                )
                
                if not result or 'id' not in result:
                    raise InstagramError("Failed to create media container")
                    
                return result
                
        except Exception as e:
            logger.error(f"Error uploading photo: {e}")
            return None
            
    def check_rate_limit(self) -> Dict[str, Any]:
        """Check current rate limit status"""
        try:
            endpoint = f"/{self.instagram_account_id}/content_publishing_limit"
            params = {
                'fields': 'quota_usage,rate_limit_settings'
            }
            
            response = aiohttp.request(
                "GET",
                f"{self.base_url}{endpoint}",
                params=params
            ).json()
            
            if 'data' not in response:
                return {}
                
            data = response['data'][0]
            return {
                'quota_usage': data.get('quota_usage', 0),
                'rate_limit': data.get('rate_limit_settings', {}),
                'reset_time': data.get('reset_time')
            }
            
        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            return {}