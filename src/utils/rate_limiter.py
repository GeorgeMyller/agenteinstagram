"""
Rate Limiting Handler

Manages API rate limits using a token bucket algorithm
with persistent state and adaptive backoff.
"""

import time
import json
import logging
from pathlib import Path
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
from .config import Config

logger = logging.getLogger(__name__)

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import time
import threading
from collections import deque
import logging
from .config import Config

logger = logging.getLogger(__name__)

@dataclass
class RateLimitWindow:
    window_start: float
    request_count: int = 0
    
@dataclass
class RateLimitState:
    windows: Dict[str, RateLimitWindow] = field(default_factory=dict)
    last_request_time: Dict[str, float] = field(default_factory=dict)

class RateLimiter:
    """
    Thread-safe rate limiter for Instagram API calls
    Uses a sliding window algorithm to track request rates
    """
    
    def __init__(self, window_size: int = 3600, max_requests: int = 200):
        self.window_size = window_size  # Window size in seconds
        self.max_requests = max_requests  # Maximum requests per window
        self.requests = deque()  # Queue of request timestamps
        self._lock = threading.Lock()
        
    def _cleanup_old_requests(self):
        """Remove requests outside the current window"""
        now = time.time()
        window_start = now - self.window_size
        
        while self.requests and self.requests[0] < window_start:
            self.requests.popleft()
            
    def check_rate_limit(self) -> tuple[bool, Optional[float]]:
        """
        Check if we can make a new request
        
        Returns:
            tuple[bool, Optional[float]]: (can_request, wait_time)
        """
        with self._lock:
            self._cleanup_old_requests()
            
            if len(self.requests) < self.max_requests:
                return True, None
                
            # Calculate time until oldest request expires
            now = time.time()
            wait_time = self.requests[0] + self.window_size - now
            return False, max(0, wait_time)
            
    def add_request(self):
        """Record a new request"""
        with self._lock:
            now = time.time()
            self.requests.append(now)
            self._cleanup_old_requests()
            
    def get_remaining_requests(self) -> int:
        """Get number of remaining requests in current window"""
        with self._lock:
            self._cleanup_old_requests()
            return max(0, self.max_requests - len(self.requests))
            
    def get_reset_time(self) -> Optional[float]:
        """Get time until rate limit resets"""
        with self._lock:
            self._cleanup_old_requests()
            
            if not self.requests:
                return None
                
            oldest_request = self.requests[0]
            return max(0, oldest_request + self.window_size - time.time())
            
class EndpointRateLimiter:
    """
    Rate limiter that tracks limits per endpoint
    """
    
    def __init__(self):
        self.limiters: Dict[str, RateLimiter] = {}
        self._lock = threading.Lock()
        
        # Default limits for different endpoints
        self.default_limits = {
            "post_image": (3600, 25),      # 25 requests per hour
            "post_carousel": (3600, 25),    # 25 requests per hour
            "post_video": (3600, 25),       # 25 requests per hour
            "post_reel": (3600, 25),        # 25 requests per hour
            "query": (60, 200)              # 200 requests per minute
        }
        
    def _get_limiter(self, endpoint: str) -> RateLimiter:
        """Get or create rate limiter for endpoint"""
        with self._lock:
            if endpoint not in self.limiters:
                window_size, max_requests = self.default_limits.get(
                    endpoint, (3600, 200)  # Default: 200 requests per hour
                )
                self.limiters[endpoint] = RateLimiter(window_size, max_requests)
            return self.limiters[endpoint]
            
    def check_rate_limit(self, endpoint: str) -> tuple[bool, Optional[float]]:
        """Check rate limit for specific endpoint"""
        return self._get_limiter(endpoint).check_rate_limit()
        
    def add_request(self, endpoint: str):
        """Record request for specific endpoint"""
        self._get_limiter(endpoint).add_request()
        
    def get_remaining_requests(self, endpoint: str) -> int:
        """Get remaining requests for endpoint"""
        return self._get_limiter(endpoint).get_remaining_requests()
        
    def get_reset_time(self, endpoint: str) -> Optional[float]:
        """Get reset time for endpoint"""
        return self._get_limiter(endpoint).get_reset_time()
        
    def get_status(self) -> Dict:
        """Get current rate limit status for all endpoints"""
        status = {}
        with self._lock:
            for endpoint, limiter in self.limiters.items():
                status[endpoint] = {
                    "remaining": limiter.get_remaining_requests(),
                    "reset_in": limiter.get_reset_time()
                }
        return status