import os
import time
import logging
import shutil
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class CleanupUtility:
    """
    Utility class for managing temporary files and directories.
    """
    
    @staticmethod
    def cleanup_temp_files(base_dir: str, pattern: str = "temp-*", max_age_hours: int = 24) -> int:
        """
        Remove temporary files matching a pattern and older than max_age_hours.
        
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

            for file_path in path.glob(pattern):
                if not file_path.is_file():
                    continue

                file_age = current_time - file_path.stat().st_mtime
                if file_age > max_age:
                    try:
                        file_path.unlink()
                        removed += 1
                        logger.info(f"Removed old file: {file_path}")
                    except Exception as e:
                        logger.error(f"Failed to remove {file_path}: {e}")

            return removed

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return 0

    @staticmethod
    def cleanup_empty_dirs(base_dir: str, min_age_hours: int = 24) -> int:
        """
        Remove empty directories older than min_age_hours.
        
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

            for dir_path in path.glob("**"):
                if not dir_path.is_dir():
                    continue

                # Check if directory is empty
                if not any(dir_path.iterdir()):
                    dir_age = current_time - dir_path.stat().st_mtime
                    if dir_age > min_age:
                        try:
                            dir_path.rmdir()
                            removed += 1
                            logger.info(f"Removed empty directory: {dir_path}")
                        except Exception as e:
                            logger.error(f"Failed to remove {dir_path}: {e}")

            return removed

        except Exception as e:
            logger.error(f"Error during directory cleanup: {e}")
            return 0

    @staticmethod
    def get_disk_usage(path: str) -> Optional[dict]:
        """
        Get disk usage statistics for a path.
        
        Args:
            path: Path to check
            
        Returns:
            Optional[dict]: Dictionary with usage statistics or None on error
        """
        try:
            total_size = 0
            num_files = 0
            oldest_file = None
            newest_file = None

            for entry in Path(path).rglob("*"):
                if entry.is_file():
                    size = entry.stat().st_size
                    mtime = entry.stat().st_mtime
                    num_files += 1
                    total_size += size

                    if not oldest_file or mtime < oldest_file[1]:
                        oldest_file = (entry, mtime)
                    if not newest_file or mtime > newest_file[1]:
                        newest_file = (entry, mtime)

            return {
                'total_size_mb': total_size / (1024 * 1024),
                'num_files': num_files,
                'oldest_file': str(oldest_file[0]) if oldest_file else None,
                'newest_file': str(newest_file[0]) if newest_file else None
            }

        except Exception as e:
            logger.error(f"Error getting disk usage: {e}")
            return None

    @staticmethod
    def enforce_storage_limit(path: str, max_size_mb: int = 1000, remove_oldest: bool = True) -> bool:
        """
        Enforce a maximum storage limit for a directory.
        
        Args:
            path: Path to manage
            max_size_mb: Maximum allowed size in MB
            remove_oldest: If True, remove oldest files first
            
        Returns:
            bool: True if successfully enforced limit
        """
        try:
            usage = CleanupUtility.get_disk_usage(path)
            if not usage:
                return False

            if usage['total_size_mb'] <= max_size_mb:
                return True

            # Calculate how much we need to remove
            to_remove_mb = usage['total_size_mb'] - max_size_mb

            files = []
            for entry in Path(path).rglob("*"):
                if entry.is_file():
                    files.append((entry, entry.stat().st_mtime))

            if remove_oldest:
                # Sort by modification time (oldest first)
                files.sort(key=lambda x: x[1])
            else:
                # Sort by size (largest first)
                files.sort(key=lambda x: x[0].stat().st_size, reverse=True)

            removed_size = 0
            for file_path, _ in files:
                size_mb = file_path.stat().st_size / (1024 * 1024)
                try:
                    file_path.unlink()
                    removed_size += size_mb
                    logger.info(f"Removed {file_path} ({size_mb:.1f} MB)")
                    if removed_size >= to_remove_mb:
                        break
                except Exception as e:
                    logger.error(f"Failed to remove {file_path}: {e}")

            return True

        except Exception as e:
            logger.error(f"Error enforcing storage limit: {e}")
            return False