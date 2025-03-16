import os
import glob
import logging
from pathlib import Path
from typing import List, Dict, Any
import time

logger = logging.getLogger(__name__)

class CleanupUtility:
    """Utility class for file cleanup operations"""
    
    def cleanup_temp_files(self, directory: str, pattern: str, max_age_hours: int) -> Dict[str, Any]:
        """
        Clean up temporary files matching pattern and older than max_age_hours.
        
        Args:
            directory: Directory to clean
            pattern: File pattern to match (glob style)
            max_age_hours: Maximum file age in hours
            
        Returns:
            Dict with cleanup results
        """
        try:
            now = time.time()
            max_age_seconds = max_age_hours * 3600
            removed = []
            errors = []
            
            search_pattern = os.path.join(directory, pattern)
            for file_path in glob.glob(search_pattern):
                try:
                    if now - os.path.getmtime(file_path) > max_age_seconds:
                        os.remove(file_path)
                        removed.append(file_path)
                        logger.debug(f"Removed old file: {file_path}")
                except OSError as e:
                    errors.append(f"Error removing {file_path}: {e}")
                    logger.warning(f"Failed to remove {file_path}: {e}")
            
            return {
                'removed': removed,
                'count': len(removed),
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"Error during temp file cleanup: {e}")
            return {
                'removed': [],
                'count': 0,
                'errors': [str(e)]
            }
    
    def cleanup_empty_dirs(self, directory: str, max_age_hours: int) -> Dict[str, Any]:
        """
        Remove empty directories older than max_age_hours.
        
        Args:
            directory: Root directory to clean
            max_age_hours: Maximum directory age in hours
            
        Returns:
            Dict with cleanup results
        """
        try:
            now = time.time()
            max_age_seconds = max_age_hours * 3600
            removed = []
            errors = []
            
            for root, dirs, _ in os.walk(directory, topdown=False):
                for dir_name in dirs:
                    dir_path = os.path.join(root, dir_name)
                    try:
                        # Check if directory is empty and old enough
                        if not os.listdir(dir_path) and \
                           now - os.path.getmtime(dir_path) > max_age_seconds:
                            os.rmdir(dir_path)
                            removed.append(dir_path)
                            logger.debug(f"Removed empty directory: {dir_path}")
                    except OSError as e:
                        errors.append(f"Error removing directory {dir_path}: {e}")
                        logger.warning(f"Failed to remove directory {dir_path}: {e}")
            
            return {
                'removed': removed,
                'count': len(removed),
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"Error during empty directory cleanup: {e}")
            return {
                'removed': [],
                'count': 0,
                'errors': [str(e)]
            }
    
    def enforce_storage_limit(self, directory: str, max_size_mb: int, remove_oldest: bool = True) -> Dict[str, Any]:
        """
        Enforce storage limit by removing files when total size exceeds limit.
        
        Args:
            directory: Directory to monitor
            max_size_mb: Maximum allowed size in MB
            remove_oldest: If True, remove oldest files first; if False, largest
            
        Returns:
            Dict with enforcement results
        """
        try:
            # Get all files with their sizes and timestamps
            files_info = []
            total_size = 0
            
            for root, _, files in os.walk(directory):
                for file in files:
                    try:
                        file_path = os.path.join(root, file)
                        size = os.path.getsize(file_path)
                        mtime = os.path.getmtime(file_path)
                        total_size += size
                        files_info.append((file_path, size, mtime))
                    except OSError as e:
                        logger.warning(f"Error getting file info for {file}: {e}")
            
            # Convert max_size_mb to bytes
            max_size = max_size_mb * 1024 * 1024
            removed = []
            errors = []
            
            # If we're over limit, start removing files
            if total_size > max_size:
                # Sort files by age or size
                if remove_oldest:
                    files_info.sort(key=lambda x: x[2])  # Sort by mtime
                else:
                    files_info.sort(key=lambda x: x[1], reverse=True)  # Sort by size
                
                # Remove files until we're under limit
                for file_path, size, _ in files_info:
                    try:
                        os.remove(file_path)
                        removed.append(file_path)
                        total_size -= size
                        logger.debug(f"Removed file to enforce storage limit: {file_path}")
                        
                        if total_size <= max_size:
                            break
                    except OSError as e:
                        errors.append(f"Error removing {file_path}: {e}")
                        logger.warning(f"Failed to remove {file_path}: {e}")
            
            return {
                'removed': removed,
                'count': len(removed),
                'errors': errors,
                'final_size_mb': total_size / (1024 * 1024)
            }
            
        except Exception as e:
            logger.error(f"Error enforcing storage limit: {e}")
            return {
                'removed': [],
                'count': 0,
                'errors': [str(e)],
                'final_size_mb': 0
            }
            
    def get_directory_size(self, directory: str) -> Dict[str, Any]:
        """
        Get total size and file count for a directory.
        
        Args:
            directory: Directory to analyze
            
        Returns:
            Dict with size information
        """
        try:
            total_size = 0
            file_count = 0
            
            for root, _, files in os.walk(directory):
                for file in files:
                    try:
                        file_path = os.path.join(root, file)
                        total_size += os.path.getsize(file_path)
                        file_count += 1
                    except OSError as e:
                        logger.warning(f"Error getting size for {file}: {e}")
            
            return {
                'size_bytes': total_size,
                'size_mb': total_size / (1024 * 1024),
                'file_count': file_count
            }
            
        except Exception as e:
            logger.error(f"Error getting directory size: {e}")
            return {
                'size_bytes': 0,
                'size_mb': 0,
                'file_count': 0,
                'error': str(e)
            }