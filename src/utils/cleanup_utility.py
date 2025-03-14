import os
import time
import logging
import shutil
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from .config import Config

logger = logging.getLogger(__name__)

class CleanupUtility:
    """
    Utility class for managing temporary files and directories.
    Implements aggressive cleanup strategies and disk usage monitoring.
    """
    
    def __init__(self):
        """Initialize cleanup utility with configuration."""
        self.config = Config.get_instance()
    
    @staticmethod
    def cleanup_temp_files(base_dir: str, pattern: str = "temp-*", max_age_hours: int = 24) -> int:
        """
        Remove temporary files matching a pattern and older than max_age_hours.
        Now includes size-based cleanup and handles locked files.
        
        Args:
            base_dir: Base directory to clean
            pattern: File pattern to match (glob pattern)
            max_age_hours: Maximum age in hours before deletion
            
        Returns:
            int: Number of files removed
        """
        try:
            if not os.path.exists(base_dir):
                logger.warning(f"Directory does not exist: {base_dir}")
                return 0

            path = Path(base_dir)
            current_time = time.time()
            max_age = max_age_hours * 3600
            removed = 0
            
            # Get files sorted by age (oldest first)
            files = []
            for file_path in path.glob(pattern):
                if not file_path.is_file():
                    continue
                    
                try:
                    stat = file_path.stat()
                    files.append((file_path, stat.st_mtime, stat.st_size))
                except OSError:
                    continue
            
            files.sort(key=lambda x: x[1])  # Sort by modification time
            
            # First pass: Remove files by age
            for file_path, mtime, _ in files:
                file_age = current_time - mtime
                if file_age > max_age:
                    try:
                        file_path.unlink(missing_ok=True)
                        removed += 1
                        logger.info(f"Removed old file: {file_path}")
                    except OSError as e:
                        logger.warning(f"Failed to remove {file_path}: {e}")
            
            # Second pass: If directory is still too full, remove more files
            if removed == 0:  # Only if no files were removed by age
                total_size = sum(f[2] for f in files)
                max_size = Config.get_instance().MAX_STORAGE_MB * 1024 * 1024
                
                if total_size > max_size:
                    size_to_remove = total_size - max_size
                    current_removed = 0
                    
                    for file_path, _, size in files:
                        try:
                            file_path.unlink(missing_ok=True)
                            current_removed += size
                            removed += 1
                            logger.info(f"Removed file due to space constraints: {file_path}")
                            
                            if current_removed >= size_to_remove:
                                break
                        except OSError as e:
                            logger.warning(f"Failed to remove {file_path}: {e}")

            return removed
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return 0

    @staticmethod
    def cleanup_empty_dirs(base_dir: str, min_age_hours: int = 24) -> int:
        """
        Remove empty directories older than min_age_hours.
        Now includes recursive cleanup and handles permissions.
        
        Args:
            base_dir: Base directory to clean
            min_age_hours: Minimum age in hours before deletion
            
        Returns:
            int: Number of directories removed
        """
        try:
            if not os.path.exists(base_dir):
                logger.warning(f"Directory does not exist: {base_dir}")
                return 0

            path = Path(base_dir)
            current_time = time.time()
            min_age = min_age_hours * 3600
            removed = 0

            # Walk directory tree bottom-up
            for dirpath, dirnames, filenames in os.walk(str(path), topdown=False):
                if not filenames and not dirnames:  # Empty directory
                    dir_path = Path(dirpath)
                    if dir_path == path:  # Don't remove base directory
                        continue
                        
                    try:
                        dir_age = current_time - dir_path.stat().st_mtime
                        if dir_age > min_age:
                            dir_path.rmdir()
                            removed += 1
                            logger.info(f"Removed empty directory: {dir_path}")
                    except OSError as e:
                        logger.warning(f"Failed to remove {dir_path}: {e}")

            return removed

        except Exception as e:
            logger.error(f"Error during directory cleanup: {e}")
            return 0

    @staticmethod
    def get_disk_usage(path: str) -> Optional[Dict]:
        """
        Get detailed disk usage information for a path.
        Now includes file counts and age statistics.
        
        Args:
            path: Path to analyze
            
        Returns:
            Optional[Dict]: Dictionary with usage statistics
        """
        try:
            if not os.path.exists(path):
                return None

            total_size = 0
            file_count = 0
            dir_count = 0
            oldest_file = (None, float('inf'))
            newest_file = (None, 0)

            for root, dirs, files in os.walk(path):
                dir_count += len(dirs)
                for file in files:
                    file_path = Path(root) / file
                    try:
                        stats = file_path.stat()
                        size = stats.st_size
                        mtime = stats.st_mtime
                        
                        total_size += size
                        file_count += 1
                        
                        if mtime < oldest_file[1]:
                            oldest_file = (file_path, mtime)
                        if mtime > newest_file[1]:
                            newest_file = (file_path, mtime)
                    except OSError:
                        continue

            return {
                'total_size_mb': total_size / (1024 * 1024),
                'file_count': file_count,
                'directory_count': dir_count,
                'oldest_file': str(oldest_file[0]) if oldest_file[0] else None,
                'newest_file': str(newest_file[0]) if newest_file[0] else None,
                'oldest_file_age_hours': (time.time() - oldest_file[1]) / 3600 if oldest_file[0] else None,
                'newest_file_age_hours': (time.time() - newest_file[1]) / 3600 if newest_file[0] else None
            }

        except Exception as e:
            logger.error(f"Error getting disk usage: {e}")
            return None

    @staticmethod
    def enforce_storage_limit(path: str, max_size_mb: int = 1000, remove_oldest: bool = True) -> bool:
        """
        Enforce storage limit on a directory.
        Now includes smarter file selection and error handling.
        
        Args:
            path: Path to manage
            max_size_mb: Maximum allowed size in MB
            remove_oldest: If True, remove oldest files first; otherwise largest
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not os.path.exists(path):
                return False

            usage = CleanupUtility.get_disk_usage(path)
            if not usage:
                return False

            current_size_mb = usage['total_size_mb']
            if current_size_mb <= max_size_mb:
                return True

            to_remove_mb = current_size_mb - max_size_mb
            
            # Get all files with their stats
            files = []
            for root, _, filenames in os.walk(path):
                for filename in filenames:
                    file_path = Path(root) / filename
                    try:
                        stats = file_path.stat()
                        files.append((file_path, stats.st_mtime, stats.st_size))
                    except OSError:
                        continue

            if remove_oldest:
                # Sort by modification time (oldest first)
                files.sort(key=lambda x: x[1])
            else:
                # Sort by size (largest first)
                files.sort(key=lambda x: x[2], reverse=True)

            removed_size = 0
            for file_path, _, size in files:
                size_mb = size / (1024 * 1024)
                try:
                    file_path.unlink()
                    removed_size += size_mb
                    logger.info(f"Removed {file_path} ({size_mb:.1f} MB)")
                    if removed_size >= to_remove_mb:
                        break
                except OSError as e:
                    logger.warning(f"Failed to remove {file_path}: {e}")

            return True

        except Exception as e:
            logger.error(f"Error enforcing storage limit: {e}")
            return False