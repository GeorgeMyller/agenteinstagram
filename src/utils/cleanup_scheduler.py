import threading
import time
import logging
from typing import Optional
from .config import Config
from .resource_manager import ResourceManager

logger = logging.getLogger(__name__)

class CleanupScheduler:
    """
    Scheduler for running periodic cleanup tasks.
    Runs as a background thread to maintain system resources.
    """
    
    def __init__(self):
        """Initialize the cleanup scheduler."""
        self.config = Config.get_instance()
        self.resource_manager = ResourceManager()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        
    def start(self) -> None:
        """Start the cleanup scheduler in a background thread."""
        if self._thread and self._thread.is_alive():
            logger.warning("Cleanup scheduler is already running")
            return
            
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("Cleanup scheduler started")
        
    def stop(self) -> None:
        """Stop the cleanup scheduler."""
        if self._thread and self._thread.is_alive():
            self._stop_event.set()
            self._thread.join()
            logger.info("Cleanup scheduler stopped")
    
    def _run(self) -> None:
        """Main loop for the cleanup scheduler."""
        while not self._stop_event.is_set():
            try:
                # Get cleanup settings from config
                aggressive_threshold = getattr(self.config, 'AGGRESSIVE_CLEANUP_THRESHOLD_MB', 800)
                max_storage = getattr(self.config, 'MAX_STORAGE_MB', 1000)
                interval_minutes = getattr(self.config, 'CLEANUP_INTERVAL_MINUTES', 30)
                
                # Check storage and determine if aggressive cleanup needed
                usage = self.resource_manager.monitor_disk_usage()
                if usage:
                    total_mb = usage['total_size_mb']
                    if total_mb > aggressive_threshold:
                        logger.warning(f"Storage usage above threshold ({total_mb:.1f}MB), performing aggressive cleanup")
                        self.resource_manager.cleanup(aggressive=True)
                    else:
                        self.resource_manager.cleanup(aggressive=False)
                    
                    # Log warning if approaching limit
                    if total_mb > max_storage * 0.8:  # Warning at 80% capacity
                        logger.warning(f"Storage usage high: {total_mb:.1f}MB / {max_storage}MB")
                
                # Sleep for the configured interval
                self._stop_event.wait(interval_minutes * 60)
                
            except Exception as e:
                logger.error(f"Error in cleanup scheduler: {e}")
                # Sleep for a short time before retrying on error
                self._stop_event.wait(60)  # 1 minute retry delay
    
    @classmethod
    def get_instance(cls) -> 'CleanupScheduler':
        """Get or create singleton instance of CleanupScheduler."""
        if not hasattr(cls, '_instance'):
            cls._instance = cls()
        return cls._instance