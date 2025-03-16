from typing import Optional, Union, List, Generator, Any, Dict
import os
import logging
import psutil
from pathlib import Path
from contextlib import contextmanager
from .config import Config
from .cleanup_utility import CleanupUtility

logger = logging.getLogger(__name__)

class ResourceManager:
    """
    Resource manager for handling temporary files and cleanup operations.
    Provides context managers for automatic resource cleanup.
    Manages and monitors system resources like disk space and memory.
    """
    
    def __init__(self):
        """Initialize the resource manager with configuration."""
        self.config = Config.get_instance()
        self.cleanup_util = CleanupUtility()
        self.temp_dirs = ['temp', 'temp_videos']
        
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
    
    def monitor_disk_usage(self) -> Dict[str, Any]:
        """
        Monitor disk usage in temporary directories
        
        Returns:
            Dict containing:
            - total_size_mb: Total size of all files in MB
            - file_count: Total number of files
            - details: Per-directory breakdown
        """
        try:
            total_size = 0
            total_files = 0
            details = {}
            
            for temp_dir in self.temp_dirs:
                if not os.path.exists(temp_dir):
                    continue
                    
                dir_size = 0
                file_count = 0
                
                for root, _, files in os.walk(temp_dir):
                    for file in files:
                        try:
                            file_path = os.path.join(root, file)
                            file_size = os.path.getsize(file_path)
                            dir_size += file_size
                            file_count += 1
                        except OSError as e:
                            logger.warning(f"Error getting size for {file}: {e}")
                
                total_size += dir_size
                total_files += file_count
                details[temp_dir] = {
                    'size_mb': dir_size / (1024 * 1024),
                    'file_count': file_count
                }
            
            return {
                'total_size_mb': total_size / (1024 * 1024),
                'file_count': total_files,
                'details': details
            }
            
        except Exception as e:
            logger.error(f"Error monitoring disk usage: {e}")
            return {
                'total_size_mb': 0,
                'file_count': 0,
                'details': {},
                'error': str(e)
            }
            
    def check_system_health(self) -> Dict[str, Any]:
        """
        Check overall system health including memory and CPU usage
        
        Returns:
            Dict containing system health metrics
        """
        try:
            memory = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent(interval=1)
            disk = psutil.disk_usage('/')
            
            return {
                'memory': {
                    'total_gb': memory.total / (1024**3),
                    'available_gb': memory.available / (1024**3),
                    'percent': memory.percent
                },
                'cpu': {
                    'percent': cpu_percent
                },
                'disk': {
                    'total_gb': disk.total / (1024**3),
                    'free_gb': disk.free / (1024**3),
                    'percent': disk.percent
                }
            }
        except Exception as e:
            logger.error(f"Error checking system health: {e}")
            return {'error': str(e)}
            
    def cleanup_old_files(self, max_age_hours: int = 24) -> Dict[str, Any]:
        """
        Clean up files older than specified age
        
        Args:
            max_age_hours: Maximum age of files in hours
            
        Returns:
            Dict containing cleanup results
        """
        try:
            import time
            
            now = time.time()
            max_age_seconds = max_age_hours * 3600
            removed_files = []
            errors = []
            
            for temp_dir in self.temp_dirs:
                if not os.path.exists(temp_dir):
                    continue
                    
                for root, _, files in os.walk(temp_dir):
                    for file in files:
                        try:
                            file_path = os.path.join(root, file)
                            if now - os.path.getmtime(file_path) > max_age_seconds:
                                os.remove(file_path)
                                removed_files.append(file_path)
                        except OSError as e:
                            errors.append(f"Error removing {file}: {e}")
            
            return {
                'files_removed': len(removed_files),
                'removed_files': removed_files,
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return {
                'files_removed': 0,
                'removed_files': [],
                'errors': [str(e)]
            }
    
    def get_resource_limits(self) -> Dict[str, Any]:
        """
        Get resource limits and thresholds
        
        Returns:
            Dict containing resource limits
        """
        return {
            'max_file_size_mb': 100,  # Maximum size for any single file
            'max_total_size_gb': 10,  # Maximum total storage
            'max_files': 1000,        # Maximum number of files
            'cleanup_age_hours': 24   # Age at which files are cleaned up
        }