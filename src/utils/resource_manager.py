from typing import Optional, Union, List, Generator, Any
import os
import logging
from pathlib import Path
from contextlib import contextmanager
from .config import Config
from .cleanup_utility import CleanupUtility

logger = logging.getLogger(__name__)

class ResourceManager:
    """
    Resource manager for handling temporary files and cleanup operations.
    Provides context managers for automatic resource cleanup.
    """
    
    def __init__(self):
        """Initialize the resource manager with configuration."""
        self.config = Config.get_instance()
        self.cleanup_util = CleanupUtility()
        
    @contextmanager
    def temp_file(self, prefix: str = "temp-", suffix: str = "") -> Generator[Path, None, None]:
        """
        Context manager for temporary file handling.
        Automatically removes the file after use.
        
        Args:
            prefix: Prefix for temporary file name
            suffix: Suffix for temporary file name (e.g., '.jpg')
            
        Yields:
            Path: Path object for the temporary file
            
        Example:
            with resource_manager.temp_file(suffix='.jpg') as temp_path:
                # Use temp_path...
            # File is automatically cleaned up after the block
        """
        import tempfile
        
        try:
            # Create temporary file
            temp_fd, temp_path = tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=self.get_temp_dir())
            os.close(temp_fd)
            temp_path = Path(temp_path)
            
            yield temp_path
            
        finally:
            # Cleanup on exit
            try:
                if temp_path.exists():
                    temp_path.unlink()
                    logger.debug(f"Cleaned up temporary file: {temp_path}")
            except Exception as e:
                logger.warning(f"Failed to cleanup temporary file {temp_path}: {e}")
    
    @contextmanager
    def temp_directory(self, prefix: str = "temp-") -> Generator[Path, None, None]:
        """
        Context manager for temporary directory handling.
        Automatically removes the directory and its contents after use.
        
        Args:
            prefix: Prefix for temporary directory name
            
        Yields:
            Path: Path object for the temporary directory
            
        Example:
            with resource_manager.temp_directory() as temp_dir:
                # Use temp_dir...
            # Directory and contents are automatically cleaned up
        """
        import tempfile
        import shutil
        
        temp_dir = None
        try:
            temp_dir = Path(tempfile.mkdtemp(prefix=prefix, dir=self.get_temp_dir()))
            yield temp_dir
            
        finally:
            # Cleanup on exit
            if temp_dir and temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir)
                    logger.debug(f"Cleaned up temporary directory: {temp_dir}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup temporary directory {temp_dir}: {e}")
    
    def get_temp_dir(self) -> Path:
        """Get the application's temporary directory, creating if needed."""
        temp_dir = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))) / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        return temp_dir
    
    def cleanup(self, aggressive: bool = True) -> None:
        """
        Perform cleanup of temporary resources.
        
        Args:
            aggressive: If True, uses more aggressive cleanup parameters
        """
        config = self.config.get_cleanup_config()
        temp_dir = self.get_temp_dir()
        
        # Adjust cleanup parameters based on aggressive mode
        max_age = config['max_file_age_hours'] // 2 if aggressive else config['max_file_age_hours']
        
        # Clean temporary files
        for pattern in config['patterns']['temp_patterns']:
            self.cleanup_util.cleanup_temp_files(str(temp_dir), pattern, max_age)
            
        # Clean empty directories
        self.cleanup_util.cleanup_empty_dirs(str(temp_dir), max_age)
        
        # Enforce storage limits
        self.cleanup_util.enforce_storage_limit(
            str(temp_dir), 
            max_size_mb=config['max_storage_mb'],
            remove_oldest=True
        )
    
    def register_resource(self, path: Union[str, Path], lifetime_hours: Optional[float] = None) -> None:
        """
        Register a resource for tracking and automatic cleanup.
        
        Args:
            path: Path to the resource
            lifetime_hours: Optional maximum lifetime in hours
        """
        path = Path(path)
        if not path.exists():
            return
            
        # Set cleanup timestamp if lifetime specified
        if lifetime_hours is not None:
            cleanup_time = Path(str(path) + '.cleanup')
            import time
            cleanup_time.write_text(str(time.time() + lifetime_hours * 3600))
            
        logger.debug(f"Registered resource for cleanup: {path}")
    
    def monitor_disk_usage(self) -> dict:
        """
        Monitor disk usage of temporary directory.
        
        Returns:
            dict: Dictionary containing disk usage statistics
        """
        return self.cleanup_util.get_disk_usage(str(self.get_temp_dir()))