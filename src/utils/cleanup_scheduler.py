from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional
from pathlib import Path
import os
import logging
import threading
import time
from datetime import datetime, timedelta

from .resource_manager import ResourceManager
from .config import Config

logger = logging.getLogger(__name__)

@dataclass
class CleanupStats:
    last_run: Optional[datetime] = None
    files_deleted: int = 0
    bytes_recovered: int = 0
    errors: int = 0
    cleanup_count: int = 0
    aggressive_cleanups: int = 0

@dataclass
class CleanupPlan:
    pattern_groups: Dict[str, List[str]]
    directories: List[Path]
    max_age_hours: int
    is_aggressive: bool = False

class CleanupScheduler:
    """
    Scheduler for automatic cleanup of temporary resources
    
    Runs cleanup operations periodically in a background thread
    """
    
    _instance = None
    
    @classmethod
    def get_instance(cls) -> 'CleanupScheduler':
        """Get singleton instance of CleanupScheduler"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        """Initialize cleanup scheduler"""
        self.config = Config.get_instance()
        self.resource_manager = ResourceManager.get_instance()
        self.cleanup_interval = self.config.get_value('CLEANUP_INTERVAL_MINUTES', 30) * 60  # Convert to seconds
        self.running = False
        self.thread = None
        
        logger.info(f"CleanupScheduler initialized with interval: {self.cleanup_interval / 60} minutes")
    
    def start(self) -> bool:
        """
        Start the cleanup scheduler thread
        
        Returns:
            True if started successfully, False if already running
        """
        if self.running:
            logger.warning("CleanupScheduler already running")
            return False
            
        self.running = True
        self.thread = threading.Thread(
            target=self._cleanup_loop, 
            name="CleanupScheduler", 
            daemon=True
        )
        self.thread.start()
        
        logger.info("CleanupScheduler started")
        return True
    
    def stop(self) -> bool:
        """
        Stop the cleanup scheduler thread
        
        Returns:
            True if stopped successfully, False if not running
        """
        if not self.running:
            logger.warning("CleanupScheduler not running")
            return False
            
        self.running = False
        if self.thread:
            self.thread.join(timeout=5.0)
            
        logger.info("CleanupScheduler stopped")
        return True
    
    def _cleanup_loop(self) -> None:
        """Main cleanup thread loop"""
        while self.running:
            try:
                self._perform_cleanup()
                
                # Sleep for cleanup interval
                for _ in range(int(self.cleanup_interval)):
                    if not self.running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                # Sleep for a shorter interval on error
                time.sleep(60)
    
    def _perform_cleanup(self) -> None:
        """Perform cleanup operations"""
        logger.debug("Starting scheduled cleanup")
        
        try:
            # Monitor disk usage
            usage = self.resource_manager.monitor_disk_usage()
            
            # Log results
            if 'total_size_mb' in usage and 'usage_percent' in usage:
                logger.info(
                    f"Storage usage: {usage['total_size_mb']:.1f}MB "
                    f"({usage['usage_percent']:.1f}% of limit)"
                )
                
            if 'cleanup_action' in usage:
                action = usage['cleanup_action']
                files_cleaned = usage.get('files_cleaned', 0)
                logger.info(f"Performed {action} cleanup, removed {files_cleaned} files")
                
            # Clean up registered resources if not already done in monitor_disk_usage
            if 'cleanup_action' not in usage:
                deleted, failed = self.resource_manager.cleanup_expired_resources()
                if deleted > 0:
                    logger.info(f"Cleaned up {deleted} registered resources ({failed} failed)")
            
        except Exception as e:
            logger.error(f"Error during scheduled cleanup: {e}")

    def perform_immediate_cleanup(self) -> dict:
        """
        Force an immediate cleanup operation
        
        Returns:
            Dict with cleanup results
        """
        logger.info("Performing immediate cleanup")
        
        try:
            # Monitor disk usage and perform cleanup
            usage = self.resource_manager.monitor_disk_usage()
            
            # Clean up resources if not already done
            if 'cleanup_action' not in usage:
                deleted, failed = self.resource_manager.cleanup_expired_resources()
                usage['cleaned_resources'] = deleted
                usage['failed_cleanups'] = failed
                usage['cleanup_action'] = 'manual'
                
            return usage
            
        except Exception as e:
            logger.error(f"Error during immediate cleanup: {e}")
            return {'error': str(e)}
            
    def is_running(self) -> bool:
        """Check if scheduler is running"""
        return self.running and (self.thread is not None and self.thread.is_alive())
        
    def get_status(self) -> dict:
        """Get current status of scheduler"""
        return {
            'running': self.is_running(),
            'cleanup_interval_minutes': self.cleanup_interval / 60,
            'thread_alive': self.thread is not None and self.thread.is_alive() if self.thread else False
        }