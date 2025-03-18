import threading
import time
import logging
from typing import Optional
from .config import Config
from .resource_manager import ResourceManager

logger = logging.getLogger(__name__)

class CleanupScheduler:
    """
    Scheduler for periodic cleanup of temporary resources.
    Implements a singleton pattern.
    """
    
    _instance: Optional['CleanupScheduler'] = None
    _lock = threading.Lock()
    
    def __init__(self):
        """Initialize the cleanup scheduler."""
        self.config = Config.get_instance()
        self.resource_manager = ResourceManager()
        self.cleanup_thread: Optional[threading.Thread] = None
        self.is_running = False
        self.cleanup_interval = 3600  # 1 hour
        
    @classmethod
    def get_instance(cls) -> 'CleanupScheduler':
        """Get the singleton instance of the cleanup scheduler."""
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = cls()
        return cls._instance
    
    def start(self, interval: Optional[int] = None) -> None:
        """
        Start the cleanup scheduler.
        
        Args:
            interval: Optional interval in seconds between cleanups
        """
        if interval:
            self.cleanup_interval = interval
            
        if self.is_running:
            logger.warning("Cleanup scheduler is already running")
            return
            
        self.is_running = True
        self.cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True,
            name="CleanupThread"
        )
        self.cleanup_thread.start()
        logger.info("Cleanup scheduler started")
    
    def stop(self) -> None:
        """Stop the cleanup scheduler."""
        self.is_running = False
        if self.cleanup_thread and self.cleanup_thread.is_alive():
            self.cleanup_thread.join(timeout=5.0)
        logger.info("Cleanup scheduler stopped")
    
    def _cleanup_loop(self) -> None:
        """Main cleanup loop."""
        while self.is_running:
            try:
                # Perform cleanup
                cleanup_result = self.resource_manager.cleanup_old_files()
                
                if cleanup_result['files_removed'] > 0:
                    logger.info(
                        f"Cleaned up {cleanup_result['files_removed']} files. "
                        f"Errors: {len(cleanup_result['errors'])}"
                    )
                
                # Check system health
                health = self.resource_manager.check_system_health()
                if 'error' not in health:
                    disk_usage = health['disk']['percent']
                    if disk_usage > 90:
                        logger.warning(f"High disk usage: {disk_usage}%")
                        # Perform aggressive cleanup if disk usage is high
                        self.resource_manager.cleanup(aggressive=True)
                
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}", exc_info=True)
            
            # Sleep until next cleanup
            for _ in range(self.cleanup_interval):
                if not self.is_running:
                    break
                time.sleep(1)  # Sleep in small intervals to allow clean shutdown
    
    def force_cleanup(self) -> None:
        """Force an immediate cleanup."""
        try:
            logger.info("Forcing immediate cleanup")
            self.resource_manager.cleanup(aggressive=True)
        except Exception as e:
            logger.error(f"Error during forced cleanup: {e}", exc_info=True)