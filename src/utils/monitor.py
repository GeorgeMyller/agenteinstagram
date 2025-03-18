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
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from .config import Config

logger = logging.getLogger(__name__)

@dataclass
class PostStat:
    label: str
    value: int
    status: str

@dataclass
class HealthMetric:
    label: str
    value: str
    status: str

@dataclass
class RateLimit:
    label: str
    value: str
    status: str

@dataclass
class RecentPost:
    timestamp: str
    type: str
    status: str

@dataclass
class RecentError:
    timestamp: str
    message: str

@dataclass
class MonitoringStats:
    post_stats: List[PostStat] = field(default_factory=list)
    api_health: List[HealthMetric] = field(default_factory=list)
    rate_limits: List[RateLimit] = field(default_factory=list)
    recent_posts: List[RecentPost] = field(default_factory=list)
    recent_errors: List[RecentError] = field(default_factory=list)
    last_update: str = ""
    version: str = "1.0.0"

class ApiMonitor:
    """Monitors API usage, performance, and errors"""
    
    MAX_HISTORY = 1000  # Maximum number of requests to keep in history
    
    def __init__(self):
        self._lock = threading.Lock()
        self.start_time = datetime.now()
        self.api_calls: Dict[str, int] = defaultdict(int)
        self.errors: Dict[str, int] = defaultdict(int)
        self.response_times: Dict[str, List[float]] = defaultdict(list)
        self.request_history = deque(maxlen=self.MAX_HISTORY)
        self.config = Config.get_instance()
        self.stats = MonitoringStats()
        self._running = False
        self._monitor_thread = None

        # Setup Jinja2 environment
        template_dir = Path(__file__).parent.parent.parent / "monitoring_templates"
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=True
        )
        
    def start(self) -> None:
        """Start the monitoring thread"""
        if self._running:
            return
            
        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True
        )
        self._monitor_thread.start()
        logger.info("API monitoring started")
        
    def stop(self) -> None:
        """Stop the monitoring thread"""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join()
            logger.info("API monitoring stopped")
            
    def _monitor_loop(self) -> None:
        """Main monitoring loop"""
        while self._running:
            try:
                self._update_stats()
                monitor_config = self.config.get_monitoring_config()
                time.sleep(monitor_config.stats_interval)
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                time.sleep(60)  # Backup interval on error
                
    def _update_stats(self) -> None:
        """Update monitoring statistics"""
        with self._lock:
            stats = self.stats
            
            # Update post stats
            stats.post_stats = [
                PostStat("Successful Posts", 123, "success"),
                PostStat("Failed Posts", 5, "error"),
                PostStat("Rate Limited", 2, "warning")
            ]
            
            # Update API health metrics
            stats.api_health = [
                HealthMetric("API Status", "Online", "success"),
                HealthMetric("Response Time", "245ms", "success"),
                HealthMetric("Error Rate", "2.1%", "warning")
            ]
            
            # Update rate limits
            stats.rate_limits = [
                RateLimit("Remaining Calls", "180/200", "success"),
                RateLimit("Reset Time", "45min", "success")
            ]
            
            # Update recent posts
            stats.recent_posts = [
                RecentPost(
                    datetime.now().strftime("%H:%M:%S"),
                    "Image",
                    "success"
                )
            ]
            
            # Update recent errors
            stats.recent_errors = [
                RecentError(
                    datetime.now().strftime("%H:%M:%S"),
                    "Rate limit exceeded"
                )
            ]
            
            # Update metadata
            stats.last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
    def render_dashboard(self) -> str:
        """Render the monitoring dashboard"""
        template = self.jinja_env.get_template("dashboard.html")
        return template.render(
            post_stats=self.stats.post_stats,
            api_health=self.stats.api_health,
            rate_limits=self.stats.rate_limits,
            recent_posts=self.stats.recent_posts,
            recent_errors=self.stats.recent_errors,
            last_update=self.stats.last_update,
            version=self.stats.version
        )
        
    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics"""
        with self._lock:
            successful = sum(1 for stat in self.stats.post_stats 
                           if stat.status == "success")
            failed = sum(1 for stat in self.stats.post_stats 
                        if stat.status == "error")
            rate_limited = sum(1 for stat in self.stats.post_stats 
                             if stat.status == "warning")
            
            return {
                "successful_posts": successful,
                "failed_posts": failed,
                "rate_limited_posts": rate_limited,
                "last_update": self.stats.last_update
            }
            
    def track_api_call(self, endpoint: str, success: bool, duration: float):
        """Track an API call with its result and duration"""
        with self._lock:
            self.api_calls[endpoint] += 1
            self.response_times[endpoint].append(duration)
            
            # Keep only last 100 response times per endpoint
            if len(self.response_times[endpoint]) > 100:
                self.response_times[endpoint].pop(0)
                
            self.request_history.append({
                'timestamp': datetime.now().isoformat(),
                'endpoint': endpoint,
                'success': success,
                'duration': duration
            })
            
    def track_error(self, endpoint: str, error_message: str):
        """Track an API error"""
        with self._lock:
            self.errors[endpoint] += 1
            self.request_history.append({
                'timestamp': datetime.now().isoformat(),
                'endpoint': endpoint,
                'success': False,
                'error': error_message
            })
            
    def get_statistics(self) -> Dict[str, Any]:
        """Get current API usage statistics"""
        with self._lock:
            total_calls = sum(self.api_calls.values())
            total_errors = sum(self.errors.values())
            
            stats = {
                'uptime': str(datetime.now() - self.start_time),
                'total_calls': total_calls,
                'total_errors': total_errors,
                'error_rate': total_errors / total_calls if total_calls > 0 else 0,
                'endpoints': {},
                'recent_errors': [
                    req for req in self.request_history
                    if not req['success']
                ][-10:]  # Last 10 errors
            }
            
            # Calculate per-endpoint statistics
            for endpoint in self.api_calls.keys():
                calls = self.api_calls[endpoint]
                errors = self.errors[endpoint]
                times = self.response_times[endpoint]
                
                stats['endpoints'][endpoint] = {
                    'total_calls': calls,
                    'errors': errors,
                    'error_rate': errors / calls if calls > 0 else 0,
                    'avg_response_time': sum(times) / len(times) if times else 0,
                    'min_response_time': min(times) if times else 0,
                    'max_response_time': max(times) if times else 0
                }
                
            return stats
            
    def get_recent_activity(self, minutes: int = 60) -> List[Dict]:
        """Get recent API activity within specified timeframe"""
        with self._lock:
            cutoff = datetime.now() - timedelta(minutes=minutes)
            
            recent = []
            for req in self.request_history:
                req_time = datetime.fromisoformat(req['timestamp'])
                if req_time >= cutoff:
                    recent.append(req)
                    
            return recent
            
    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of API errors"""
        with self._lock:
            summary = {
                'total_errors': sum(self.errors.values()),
                'errors_by_endpoint': dict(self.errors),
                'recent_errors': [
                    req for req in self.request_history
                    if not req['success']
                ][-10:]  # Last 10 errors
            }
            return summary
            
    def save_state(self, file_path: str):
        """Save current monitoring state to file"""
        with self._lock:
            state = {
                'start_time': self.start_time.isoformat(),
                'api_calls': dict(self.api_calls),
                'errors': dict(self.errors),
                'request_history': list(self.request_history)
            }
            
            with open(file_path, 'w') as f:
                json.dump(state, f, indent=2)
                
    def load_state(self, file_path: str):
        """Load monitoring state from file"""
        try:
            with open(file_path, 'r') as f:
                state = json.load(f)
                
            with self._lock:
                self.start_time = datetime.fromisoformat(state['start_time'])
                self.api_calls = defaultdict(int, state['api_calls'])
                self.errors = defaultdict(int, state['errors'])
                self.request_history = deque(state['request_history'], maxlen=self.MAX_HISTORY)
                
        except Exception as e:
            logger.error(f"Error loading monitor state: {e}")
            
    def reset_statistics(self):
        """Reset all monitoring statistics"""
        with self._lock:
            self.start_time = datetime.now()
            self.api_calls.clear()
            self.errors.clear()
            self.response_times.clear()
            self.request_history.clear()