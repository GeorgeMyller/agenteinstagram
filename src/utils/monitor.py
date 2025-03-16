"""
API Monitor

Tracks API health metrics, errors, and performance.
Provides insights into API usage patterns and potential issues.
"""

import time
import logging
import threading
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import json
from collections import defaultdict

logger = logging.getLogger(__name__)

class ApiMonitor:
    """Monitors API health and performance"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize monitor"""
        if not hasattr(self, 'initialized'):
            self.calls = defaultdict(list)
            self.errors = defaultdict(list)
            self.running = False
            self.initialized = True
    
    def start(self):
        """Start monitoring"""
        self.running = True
        self._start_cleanup_thread()
    
    def stop(self):
        """Stop monitoring"""
        self.running = False
    
    def track_api_call(
        self,
        endpoint: str,
        success: bool = True,
        duration: float = None
    ):
        """
        Track an API call
        
        Args:
            endpoint: API endpoint called
            success: Whether call succeeded
            duration: Call duration in seconds
        """
        now = time.time()
        self.calls[endpoint].append({
            'timestamp': now,
            'success': success,
            'duration': duration
        })
    
    def track_error(self, endpoint: str, error: str):
        """
        Track an API error
        
        Args:
            endpoint: API endpoint that failed
            error: Error message
        """
        now = time.time()
        self.errors[endpoint].append({
            'timestamp': now,
            'error': error
        })
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get monitoring statistics
        
        Returns:
            Dict with API stats
        """
        stats = {}
        now = time.time()
        window = 3600  # Last hour
        
        for endpoint in self.calls:
            # Filter to window
            recent_calls = [
                c for c in self.calls[endpoint]
                if c['timestamp'] > now - window
            ]
            
            # Calculate success rate
            if recent_calls:
                success_rate = len([
                    c for c in recent_calls
                    if c['success']
                ]) / len(recent_calls)
            else:
                success_rate = 1.0
            
            # Calculate average duration
            durations = [
                c['duration'] for c in recent_calls
                if c['duration'] is not None
            ]
            avg_duration = (
                sum(durations) / len(durations)
                if durations else None
            )
            
            # Get recent errors
            recent_errors = [
                e for e in self.errors[endpoint]
                if e['timestamp'] > now - window
            ]
            
            stats[endpoint] = {
                'total_calls': len(recent_calls),
                'success_rate': success_rate,
                'avg_duration': avg_duration,
                'error_count': len(recent_errors),
                'last_error': (
                    recent_errors[-1]['error']
                    if recent_errors else None
                )
            }
        
        return stats
    
    def check_health(self) -> Dict[str, Any]:
        """
        Check API health status
        
        Returns:
            Dict with health status
        """
        stats = self.get_stats()
        
        # Overall health metrics
        total_calls = sum(
            s['total_calls']
            for s in stats.values()
        )
        total_errors = sum(
            s['error_count']
            for s in stats.values()
        )
        
        # Calculate error rate
        error_rate = (
            total_errors / total_calls
            if total_calls > 0 else 0
        )
        
        # Health status thresholds
        status = 'healthy'
        if error_rate > 0.1:  # More than 10% errors
            status = 'degraded'
        if error_rate > 0.25:  # More than 25% errors
            status = 'critical'
        
        return {
            'status': status,
            'error_rate': error_rate,
            'total_calls': total_calls,
            'total_errors': total_errors,
            'endpoints': stats
        }
    
    def save_state(self, path: str):
        """
        Save monitoring state to file
        
        Args:
            path: Path to state file
        """
        state = {
            'calls': dict(self.calls),
            'errors': dict(self.errors)
        }
        
        with open(path, 'w') as f:
            json.dump(state, f)
    
    def load_state(self, path: str):
        """
        Load monitoring state from file
        
        Args:
            path: Path to state file
        """
        try:
            with open(path) as f:
                state = json.load(f)
                
            self.calls = defaultdict(list, state['calls'])
            self.errors = defaultdict(list, state['errors'])
            
        except (FileNotFoundError, json.JSONDecodeError):
            logger.warning(
                f"Could not load monitoring state from {path}"
            )
    
    def _start_cleanup_thread(self):
        """Start background cleanup thread"""
        def cleanup():
            while self.running:
                self._cleanup_old_data()
                time.sleep(3600)  # Run hourly
        
        thread = threading.Thread(target=cleanup)
        thread.daemon = True
        thread.start()
    
    def _cleanup_old_data(self):
        """Remove old monitoring data"""
        now = time.time()
        max_age = 86400  # 24 hours
        
        for endpoint in self.calls:
            self.calls[endpoint] = [
                c for c in self.calls[endpoint]
                if c['timestamp'] > now - max_age
            ]
        
        for endpoint in self.errors:
            self.errors[endpoint] = [
                e for e in self.errors[endpoint]
                if e['timestamp'] > now - max_age
            ]