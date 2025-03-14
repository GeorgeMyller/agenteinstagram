"""
Instagram API Monitoring System

Collects and analyzes performance metrics, usage statistics, and system health data.
Provides real-time monitoring, alerting, and diagnostic tools for the Instagram API
integration.

Features:
    - API call tracking and rate limiting
    - Performance metrics collection
    - Error rate monitoring
    - Resource usage tracking
    - Automated alerting

Usage:
    >>> with ApiMonitor() as monitor:
    ...     result = instagram.post_image(image_path)
    ...     monitor.track_api_call("post_image", result)
"""

import time
import json
import logging
import threading
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
import psutil

logger = logging.getLogger(__name__)

class ApiMonitor:
    """
    Monitor and collect Instagram API usage statistics.
    
    Features:
    - Call volume tracking
    - Response time measurement
    - Error rate calculation
    - Rate limit monitoring
    - Resource usage tracking
    
    Example:
        Basic usage:
        >>> monitor = ApiMonitor()
        >>> monitor.start()
        >>> monitor.track_api_call("get_media", success=True, duration=0.5)
        >>> stats = monitor.get_statistics()
        
        Context manager:
        >>> with ApiMonitor() as m:
        ...     api.post_image(image)
        ...     m.track_resource_usage()
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize API monitor with optional configuration.
        
        Args:
            config_path: Path to monitor configuration file
            
        Configuration Example:
            {
                "alert_thresholds": {
                    "error_rate": 0.1,
                    "response_time": 5.0,
                    "rate_limit": 0.8
                },
                "collection_interval": 60,
                "retention_days": 7
            }
        """
        self.start_time = datetime.now()
        self.calls: Dict[str, List[Dict]] = defaultdict(list)
        self.errors: Dict[str, List[Dict]] = defaultdict(list)
        self.resources: List[Dict] = []
        
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Initialize counters
        self.total_calls = 0
        self.total_errors = 0
        self.running = False
        
        # Set up collection thread
        self.collection_thread = threading.Thread(
            target=self._collect_metrics,
            daemon=True
        )
        
    def __enter__(self):
        """Start monitoring when used as context manager."""
        self.start()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop monitoring and save data."""
        self.stop()
        if exc_type is not None:
            # Log any errors that occurred
            self.track_error(str(exc_type), str(exc_val))
            
    def start(self):
        """
        Start monitoring and metrics collection.
        
        Begins:
        - Periodic metric collection
        - Resource monitoring
        - Statistics aggregation
        """
        logger.info("Starting API monitoring")
        self.running = True
        self.collection_thread.start()
        
    def stop(self):
        """
        Stop monitoring and save final statistics.
        
        - Stops metric collection
        - Saves final statistics
        - Cleans up resources
        """
        logger.info("Stopping API monitoring")
        self.running = False
        if self.collection_thread.is_alive():
            self.collection_thread.join()
        self._save_statistics()
        
    def track_api_call(self, 
                      endpoint: str,
                      success: bool = True,
                      duration: Optional[float] = None,
                      **kwargs):
        """
        Track an API call with its result and metadata.
        
        Args:
            endpoint: API endpoint called
            success: Whether call succeeded
            duration: Call duration in seconds
            **kwargs: Additional call metadata
            
        Example:
            >>> monitor.track_api_call(
            ...     endpoint="upload_photo",
            ...     success=True,
            ...     duration=1.2,
            ...     size_mb=2.5
            ... )
        """
        timestamp = datetime.now()
        
        # Record call details
        call_data = {
            'timestamp': timestamp,
            'success': success,
            'duration': duration,
            **kwargs
        }
        
        self.calls[endpoint].append(call_data)
        self.total_calls += 1
        
        # Track errors
        if not success:
            self.track_error(endpoint, kwargs.get('error'))
            
        # Check thresholds
        self._check_alert_thresholds(endpoint, call_data)
        
    def track_error(self, error_type: str, details: Any):
        """
        Track an error occurrence with details.
        
        Args:
            error_type: Category of error
            details: Error details or exception
            
        Example:
            >>> try:
            ...     api.post_image(image)
            ... except Exception as e:
            ...     monitor.track_error("post_image", str(e))
        """
        timestamp = datetime.now()
        
        error_data = {
            'timestamp': timestamp,
            'details': str(details)
        }
        
        self.errors[error_type].append(error_data)
        self.total_errors += 1
        
        # Log error
        logger.error(
            f"API Error: {error_type}\n"
            f"Details: {details}\n"
            f"Total Errors: {self.total_errors}"
        )
        
    def track_resource_usage(self):
        """
        Record current system resource usage.
        
        Tracks:
        - CPU usage
        - Memory usage
        - Disk I/O
        - Network usage
        
        Example:
            >>> monitor.track_resource_usage()
            >>> stats = monitor.get_resource_stats()
            >>> print(f"CPU Usage: {stats['cpu_percent']}%")
        """
        timestamp = datetime.now()
        
        # Collect system metrics
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        metrics = {
            'timestamp': timestamp,
            'cpu_percent': cpu_percent,
            'memory_percent': memory.percent,
            'disk_percent': disk.percent,
            'swap_percent': psutil.swap_memory().percent
        }
        
        self.resources.append(metrics)
        
        # Check resource thresholds
        self._check_resource_thresholds(metrics)
        
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get current monitoring statistics.
        
        Returns:
            dict: Current statistics including:
                - Call volumes and rates
                - Error counts and rates
                - Response time averages
                - Resource usage
                
        Example:
            >>> stats = monitor.get_statistics()
            >>> print(f"Error Rate: {stats['error_rate']:.2%}")
            >>> print(f"Avg Response: {stats['avg_duration']:.2f}s")
        """
        now = datetime.now()
        window = timedelta(minutes=self.config['collection_interval'])
        
        # Calculate statistics
        stats = {
            'total_calls': self.total_calls,
            'total_errors': self.total_errors,
            'error_rate': self.total_errors / max(self.total_calls, 1),
            'uptime_seconds': (now - self.start_time).total_seconds(),
            'endpoints': {}
        }
        
        # Per-endpoint statistics
        for endpoint, calls in self.calls.items():
            recent_calls = [
                c for c in calls 
                if now - c['timestamp'] <= window
            ]
            
            if recent_calls:
                stats['endpoints'][endpoint] = {
                    'call_count': len(recent_calls),
                    'error_count': len([c for c in recent_calls if not c['success']]),
                    'avg_duration': sum(c['duration'] or 0 for c in recent_calls) / len(recent_calls)
                }
                
        return stats
        
    def _collect_metrics(self):
        """Periodically collect and save metrics."""
        while self.running:
            try:
                self.track_resource_usage()
                self._save_statistics()
                self._cleanup_old_data()
                
                # Wait for next collection interval
                time.sleep(self.config['collection_interval'])
                
            except Exception as e:
                logger.error(f"Error collecting metrics: {e}")
                
    def _check_alert_thresholds(self, endpoint: str, call_data: Dict):
        """Check if any alert thresholds are exceeded."""
        thresholds = self.config['alert_thresholds']
        
        # Check error rate
        stats = self.get_statistics()
        if stats['error_rate'] > thresholds['error_rate']:
            logger.warning(
                f"Error rate threshold exceeded: "
                f"{stats['error_rate']:.2%} > {thresholds['error_rate']:.2%}"
            )
            
        # Check response time
        if call_data.get('duration', 0) > thresholds['response_time']:
            logger.warning(
                f"Response time threshold exceeded for {endpoint}: "
                f"{call_data['duration']:.2f}s > {thresholds['response_time']:.2f}s"
            )
            
    def _check_resource_thresholds(self, metrics: Dict):
        """Check if resource usage thresholds are exceeded."""
        if metrics['cpu_percent'] > 80:
            logger.warning(f"High CPU usage: {metrics['cpu_percent']}%")
        if metrics['memory_percent'] > 80:
            logger.warning(f"High memory usage: {metrics['memory_percent']}%")
        if metrics['disk_percent'] > 80:
            logger.warning(f"High disk usage: {metrics['disk_percent']}%")
            
    def _save_statistics(self):
        """Save current statistics to file."""
        stats = self.get_statistics()
        
        # Save to JSON file
        stats_file = Path('monitoring/statistics.json')
        stats_file.parent.mkdir(exist_ok=True)
        
        try:
            with stats_file.open('w') as f:
                json.dump(stats, f, default=str)
        except Exception as e:
            logger.error(f"Error saving statistics: {e}")
            
    def _cleanup_old_data(self):
        """Remove data older than retention period."""
        retention = timedelta(days=self.config['retention_days'])
        threshold = datetime.now() - retention
        
        # Clean up old calls
        for endpoint in self.calls:
            self.calls[endpoint] = [
                c for c in self.calls[endpoint]
                if c['timestamp'] > threshold
            ]
            
        # Clean up old errors
        for error_type in self.errors:
            self.errors[error_type] = [
                e for e in self.errors[error_type]
                if e['timestamp'] > threshold
            ]
            
        # Clean up old resource metrics
        self.resources = [
            r for r in self.resources
            if r['timestamp'] > threshold
        ]
        
    def _load_config(self, config_path: Optional[str]) -> Dict:
        """Load monitor configuration with defaults."""
        defaults = {
            'alert_thresholds': {
                'error_rate': 0.1,
                'response_time': 5.0,
                'rate_limit': 0.8
            },
            'collection_interval': 60,
            'retention_days': 7
        }
        
        if not config_path:
            return defaults
            
        try:
            with open(config_path) as f:
                config = json.load(f)
                return {**defaults, **config}
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return defaults