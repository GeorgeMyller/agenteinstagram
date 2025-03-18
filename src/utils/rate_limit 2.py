"""
Rate Limit Handler

Manages API rate limits with exponential backoff strategy.
Tracks request quotas across multiple time windows.
"""

import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from threading import Lock
import json

logger = logging.getLogger(__name__)

class RateLimitHandler:
    """Handles rate limiting with exponential backoff"""
    
    def __init__(self):
        """Initialize rate limit handler"""
        # Rate limit windows in seconds
        self.windows = {
            'per_second': 1,
            'per_minute': 60,
            'per_hour': 3600,
            'per_day': 86400
        }
        
        # Request limits per window
        self.limits = {
            'per_second': 2,
            'per_minute': 30,
            'per_hour': 200,
            'per_day': 1000
        }
        
        # Request history
        self.requests = {}
        
        # Backoff state
        self.backoff = {}
        
        # Thread safety
        self.lock = Lock()
    
    def check_rate_limit(self, endpoint: str) -> bool:
        """
        Check if endpoint is rate limited
        
        Args:
            endpoint: API endpoint to check
            
        Returns:
            bool: True if request allowed, False if rate limited
        """
        with self.lock:
            now = time.time()
            
            # Initialize request history
            if endpoint not in self.requests:
                self.requests[endpoint] = []
            
            # Clean old requests
            self._clean_old_requests(endpoint)
            
            # Check each time window
            for window, duration in self.windows.items():
                window_start = now - duration
                window_requests = len([
                    r for r in self.requests[endpoint]
                    if r > window_start
                ])
                
                if window_requests >= self.limits[window]:
                    logger.warning(
                        f"Rate limit exceeded for {endpoint} "
                        f"({window}: {window_requests} requests)"
                    )
                    return False
            
            # Check backoff
            if endpoint in self.backoff:
                backoff_until = self.backoff[endpoint]['until']
                if now < backoff_until:
                    return False
                
                # Clear backoff if expired
                if self.backoff[endpoint]['count'] == 0:
                    del self.backoff[endpoint]
            
            return True
    
    def add_request(self, endpoint: str):
        """
        Record an API request
        
        Args:
            endpoint: API endpoint requested
        """
        with self.lock:
            now = time.time()
            self.requests[endpoint].append(now)
    
    def get_wait_time(self, endpoint: str) -> float:
        """
        Get time to wait before next request
        
        Args:
            endpoint: API endpoint to check
            
        Returns:
            float: Seconds to wait
        """
        with self.lock:
            now = time.time()
            wait_time = 0
            
            # Check time windows
            for window, duration in self.windows.items():
                window_start = now - duration
                window_requests = len([
                    r for r in self.requests.get(endpoint, [])
                    if r > window_start
                ])
                
                if window_requests >= self.limits[window]:
                    # Calculate time until oldest request expires
                    oldest = min(
                        r for r in self.requests[endpoint]
                        if r > window_start
                    )
                    expire_time = oldest + duration - now
                    wait_time = max(wait_time, expire_time)
            
            # Check backoff
            if endpoint in self.backoff:
                backoff_until = self.backoff[endpoint]['until']
                if now < backoff_until:
                    wait_time = max(wait_time, backoff_until - now)
            
            return wait_time
    
    def _clean_old_requests(self, endpoint: str):
        """
        Remove expired requests
        
        Args:
            endpoint: API endpoint to clean
        """
        now = time.time()
        max_age = max(self.windows.values())
        
        self.requests[endpoint] = [
            r for r in self.requests[endpoint]
            if r > now - max_age
        ]
    
    def add_error(self, endpoint: str):
        """
        Record an API error and update backoff
        
        Args:
            endpoint: API endpoint that failed
        """
        with self.lock:
            now = time.time()
            
            if endpoint not in self.backoff:
                # Initialize backoff
                self.backoff[endpoint] = {
                    'count': 1,
                    'until': now + 2  # Initial 2 second backoff
                }
            else:
                # Exponential backoff
                self.backoff[endpoint]['count'] += 1
                wait = min(
                    2 ** self.backoff[endpoint]['count'],
                    3600  # Max 1 hour backoff
                )
                self.backoff[endpoint]['until'] = now + wait
    
    def reset_backoff(self, endpoint: str):
        """
        Reset backoff after successful request
        
        Args:
            endpoint: API endpoint to reset
        """
        with self.lock:
            if endpoint in self.backoff:
                self.backoff[endpoint]['count'] = max(
                    0,
                    self.backoff[endpoint]['count'] - 1
                )
    
    def save_state(self, path: str):
        """
        Save rate limit state to file
        
        Args:
            path: Path to state file
        """
        with self.lock:
            state = {
                'requests': self.requests,
                'backoff': self.backoff
            }
            
            with open(path, 'w') as f:
                json.dump(state, f)
    
    def load_state(self, path: str):
        """
        Load rate limit state from file
        
        Args:
            path: Path to state file
        """
        with self.lock:
            try:
                with open(path) as f:
                    state = json.load(f)
                    
                self.requests = state['requests']
                self.backoff = state['backoff']
                
            except (FileNotFoundError, json.JSONDecodeError):
                logger.warning(f"Could not load rate limit state from {path}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get rate limiting statistics
        
        Returns:
            Dict with rate limit stats
        """
        with self.lock:
            now = time.time()
            stats = {}
            
            for endpoint in self.requests:
                window_stats = {}
                
                for window, duration in self.windows.items():
                    window_start = now - duration
                    window_requests = len([
                        r for r in self.requests[endpoint]
                        if r > window_start
                    ])
                    
                    window_stats[window] = {
                        'requests': window_requests,
                        'limit': self.limits[window],
                        'remaining': max(
                            0,
                            self.limits[window] - window_requests
                        )
                    }
                
                stats[endpoint] = {
                    'windows': window_stats,
                    'backoff': self.backoff.get(endpoint)
                }
            
            return stats