import logging
import time
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from threading import Lock
from collections import defaultdict, deque

logger = logging.getLogger(__name__)

class ApiMonitor:
    """
    Monitor Instagram API usage and performance
    
    Tracks:
    - API call volume and success rates
    - Response times
    - Rate limiting status
    - Error patterns
    """
    
    _instance = None
    _lock = Lock()
    
    API_STATE_FILE = "api_state.json"
    MAX_HISTORY_SIZE = 1000  # Max number of calls to keep in history
    
    @classmethod
    def get_instance(cls) -> 'ApiMonitor':
        """Get singleton instance of ApiMonitor"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
        
    def __init__(self):
        """Initialize API monitor"""
        # Basic stats
        self.call_count = 0
        self.error_count = 0
        self.rate_limited_count = 0
        self.successful_count = 0
        
        # Response time tracking
        self.total_duration = 0
        self.min_duration = float('inf')
        self.max_duration = 0
        
        # Endpoint-specific stats
        self.endpoint_stats = defaultdict(lambda: {
            'calls': 0, 
            'errors': 0, 
            'rate_limited': 0,
            'total_duration': 0
        })
        
        # Call history for detailed analysis
        self.call_history = deque(maxlen=self.MAX_HISTORY_SIZE)
        
        # Rate limit tracking
        self.rate_limit_info = {
            'window_start': datetime.now().timestamp(),
            'calls_in_window': 0,
            'max_calls_per_window': 200,  # Default Instagram value
            'window_seconds': 3600,       # Default 1 hour window
            'is_rate_limited': False,
            'rate_limited_until': None
        }
        
        # Load previous state if available
        self._load_state()
        
        logger.info("ApiMonitor initialized")
        
    def _load_state(self) -> None:
        """Load API state from file if available"""
        try:
            if os.path.exists(self.API_STATE_FILE):
                with open(self.API_STATE_FILE, 'r') as f:
                    state = json.load(f)
                
                # Restore basic stats
                self.call_count = state.get('stats', {}).get('call_count', 0)
                self.error_count = state.get('stats', {}).get('error_count', 0) 
                self.rate_limited_count = state.get('stats', {}).get('rate_limited_count', 0)
                self.successful_count = state.get('stats', {}).get('successful_posts', 0)
                
                # Restore rate limit info
                if 'rate_limit_info' in state:
                    rate_info = state['rate_limit_info']
                    self.rate_limit_info = {
                        'window_start': rate_info.get('window_start', datetime.now().timestamp()),
                        'calls_in_window': rate_info.get('calls_in_window', 0),
                        'max_calls_per_window': rate_info.get('max_calls_per_window', 200),
                        'window_seconds': rate_info.get('window_seconds', 3600),
                        'is_rate_limited': rate_info.get('is_rate_limited', False),
                        'rate_limited_until': rate_info.get('rate_limited_until')
                    }
                
                logger.info(f"Loaded API state from {self.API_STATE_FILE}")
        except Exception as e:
            logger.warning(f"Failed to load API state: {e}")
            
    def _save_state(self) -> None:
        """Save current API state to file"""
        try:
            state = {
                'stats': {
                    'call_count': self.call_count,
                    'error_count': self.error_count,
                    'rate_limited_count': self.rate_limited_count,
                    'successful_posts': self.successful_count
                },
                'rate_limit_info': self.rate_limit_info,
                'last_updated': datetime.now().isoformat()
            }
            
            with open(self.API_STATE_FILE, 'w') as f:
                json.dump(state, f, indent=2)
                
        except Exception as e:
            logger.warning(f"Failed to save API state: {e}")
            
    def track_api_call(self, endpoint: str, success: bool = True, 
                      duration: float = None, is_rate_limited: bool = False,
                      error_type: str = None, response_code: int = None) -> None:
        """
        Track a single API call
        
        Args:
            endpoint: API endpoint called
            success: Whether call was successful
            duration: Call duration in seconds
            is_rate_limited: Whether call hit rate limit
            error_type: Type of error if any
            response_code: HTTP status code
        """
        with self._lock:
            # Update basic stats
            self.call_count += 1
            
            if is_rate_limited:
                self.rate_limited_count += 1
            elif not success:
                self.error_count += 1
            else:
                self.successful_count += 1
                
            # Update response time stats
            if duration is not None:
                self.total_duration += duration
                self.min_duration = min(self.min_duration, duration)
                self.max_duration = max(self.max_duration, duration)
                
            # Update endpoint stats
            self.endpoint_stats[endpoint]['calls'] += 1
            if is_rate_limited:
                self.endpoint_stats[endpoint]['rate_limited'] += 1
            elif not success:
                self.endpoint_stats[endpoint]['errors'] += 1
                
            if duration is not None:
                self.endpoint_stats[endpoint]['total_duration'] += duration
                
            # Add to call history
            self.call_history.append({
                'time': datetime.now().timestamp(),
                'endpoint': endpoint,
                'success': success,
                'duration': duration,
                'is_rate_limited': is_rate_limited,
                'error_type': error_type,
                'response_code': response_code
            })
            
            # Update rate limit tracking
            now = datetime.now().timestamp()
            window_end = self.rate_limit_info['window_start'] + self.rate_limit_info['window_seconds']
            
            if now > window_end:
                # Start a new window
                self.rate_limit_info['window_start'] = now
                self.rate_limit_info['calls_in_window'] = 1
                self.rate_limit_info['is_rate_limited'] = False
                self.rate_limit_info['rate_limited_until'] = None
            else:
                # Add to current window
                self.rate_limit_info['calls_in_window'] += 1
                
                # Check if we might be rate-limited
                if (self.rate_limit_info['calls_in_window'] >= 
                    self.rate_limit_info['max_calls_per_window']):
                    self.rate_limit_info['is_rate_limited'] = True
                    self.rate_limit_info['rate_limited_until'] = window_end
                    
            # Save state periodically (every 10 calls)
            if self.call_count % 10 == 0:
                self._save_state()
                
    def update_rate_limits(self, max_calls: int = None, window_seconds: int = None,
                          is_rate_limited: bool = None, rate_limited_until: float = None) -> None:
        """
        Update rate limit parameters based on API responses
        
        Args:
            max_calls: Maximum calls allowed per window
            window_seconds: Window size in seconds
            is_rate_limited: Whether account is currently rate limited
            rate_limited_until: Timestamp when rate limit will expire
        """
        with self._lock:
            if max_calls is not None:
                self.rate_limit_info['max_calls_per_window'] = max_calls
                
            if window_seconds is not None:
                self.rate_limit_info['window_seconds'] = window_seconds
                
            if is_rate_limited is not None:
                self.rate_limit_info['is_rate_limited'] = is_rate_limited
                
            if rate_limited_until is not None:
                self.rate_limit_info['rate_limited_until'] = rate_limited_until
                
            # Save state after any rate limit update
            self._save_state()
            
    def track_error(self, endpoint: str, error_type: str, 
                   response_code: int = None, duration: float = None) -> None:
        """
        Track an API error
        
        Args:
            endpoint: API endpoint that had the error
            error_type: Type of error
            response_code: HTTP status code if applicable
            duration: Call duration in seconds
        """
        is_rate_limited = error_type.lower() in ['rate_limit', 'ratelimit', 'rate_limited', 'throttled']
        
        self.track_api_call(
            endpoint=endpoint,
            success=False,
            duration=duration,
            is_rate_limited=is_rate_limited,
            error_type=error_type,
            response_code=response_code
        )
        
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get current API statistics
        
        Returns:
            Dict with aggregated statistics
        """
        with self._lock:
            stats = {
                'total_calls': self.call_count,
                'successful_calls': self.successful_count,
                'error_count': self.error_count,
                'rate_limited_count': self.rate_limited_count,
                'error_rate': self.error_count / self.call_count if self.call_count > 0 else 0
            }
            
            # Add response time stats if we have them
            if self.call_count > 0:
                stats['avg_duration'] = self.total_duration / self.call_count
                stats['min_duration'] = self.min_duration if self.min_duration != float('inf') else None
                stats['max_duration'] = self.max_duration
                
            # Add rate limit info
            stats['rate_limits'] = {
                'is_rate_limited': self.rate_limit_info['is_rate_limited'],
                'calls_in_window': self.rate_limit_info['calls_in_window'],
                'max_calls_per_window': self.rate_limit_info['max_calls_per_window'],
                'window_seconds': self.rate_limit_info['window_seconds']
            }
            
            if self.rate_limit_info['is_rate_limited'] and self.rate_limit_info['rate_limited_until']:
                now = datetime.now().timestamp()
                time_left = max(0, self.rate_limit_info['rate_limited_until'] - now)
                stats['rate_limits']['seconds_until_reset'] = time_left
                
            # Add endpoint stats
            stats['endpoints'] = {}
            for endpoint, endpoint_stats in self.endpoint_stats.items():
                stats['endpoints'][endpoint] = {
                    'calls': endpoint_stats['calls'],
                    'errors': endpoint_stats['errors'],
                    'rate_limited': endpoint_stats['rate_limited'],
                    'success_rate': (endpoint_stats['calls'] - endpoint_stats['errors'] - 
                                   endpoint_stats['rate_limited']) / endpoint_stats['calls']
                    if endpoint_stats['calls'] > 0 else 0
                }
                
                if endpoint_stats['calls'] > 0 and endpoint_stats['total_duration'] > 0:
                    stats['endpoints'][endpoint]['avg_duration'] = (
                        endpoint_stats['total_duration'] / endpoint_stats['calls']
                    )
                    
            return stats
            
    def get_recent_calls(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get most recent API calls
        
        Args:
            limit: Maximum number of calls to return
            
        Returns:
            List of recent API calls
        """
        with self._lock:
            # Convert deque to list and get the last 'limit' items
            recent = list(self.call_history)[-limit:]
            
            # Format timestamps for better readability
            for call in recent:
                if 'time' in call:
                    call['timestamp'] = datetime.fromtimestamp(call['time']).isoformat()
                    
            return recent
            
    def check_rate_limit_status(self) -> Dict[str, Any]:
        """
        Check current rate limit status
        
        Returns:
            Dict with rate limit information
        """
        with self._lock:
            now = datetime.now().timestamp()
            window_end = self.rate_limit_info['window_start'] + self.rate_limit_info['window_seconds']
            
            # If we're past the window, reset
            if now > window_end:
                self.rate_limit_info['window_start'] = now
                self.rate_limit_info['calls_in_window'] = 0
                self.rate_limit_info['is_rate_limited'] = False
                self.rate_limit_info['rate_limited_until'] = None
                
            # Calculate remaining calls
            remaining = self.rate_limit_info['max_calls_per_window'] - self.rate_limit_info['calls_in_window']
            remaining = max(0, remaining)
            
            # Calculate reset time
            seconds_until_reset = max(0, window_end - now)
            
            return {
                'is_rate_limited': self.rate_limit_info['is_rate_limited'],
                'rate_limited_until': self.rate_limit_info['rate_limited_until'],
                'remaining_calls': remaining,
                'max_calls': self.rate_limit_info['max_calls_per_window'],
                'seconds_until_reset': seconds_until_reset,
                'calls_in_current_window': self.rate_limit_info['calls_in_window']
            }
            
    def reset_statistics(self) -> None:
        """Reset all statistics (for testing or maintenance)"""
        with self._lock:
            # Basic stats
            self.call_count = 0
            self.error_count = 0
            self.rate_limited_count = 0
            self.successful_count = 0
            
            # Response time tracking
            self.total_duration = 0
            self.min_duration = float('inf')
            self.max_duration = 0
            
            # Endpoint-specific stats
            self.endpoint_stats = defaultdict(lambda: {
                'calls': 0, 
                'errors': 0, 
                'rate_limited': 0,
                'total_duration': 0
            })
            
            # Call history
            self.call_history.clear()
            
            # Rate limit tracking (preserve window parameters)
            window_size = self.rate_limit_info['window_seconds']
            max_calls = self.rate_limit_info['max_calls_per_window']
            
            self.rate_limit_info = {
                'window_start': datetime.now().timestamp(),
                'calls_in_window': 0,
                'max_calls_per_window': max_calls,
                'window_seconds': window_size,
                'is_rate_limited': False,
                'rate_limited_until': None
            }
            
            # Save reset state
            self._save_state()
            
    def __enter__(self):
        """Context manager entry"""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - save state"""
        self._save_state()