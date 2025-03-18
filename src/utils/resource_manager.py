import os
import logging
import tempfile
import shutil
import time
import glob
from typing import Dict, List, Any, Generator, Optional, Tuple
from pathlib import Path
from datetime import datetime, timedelta
from contextlib import contextmanager
from .config import Config
import json  # Added missing import for json module

logger = logging.getLogger(__name__)

class ResourceManager:
    """
    ResourceManager handles temporary files, resource tracking,
    and storage management.
    """
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self, temp_dir: Optional[str] = None):
        """
        Initialize resource manager
        
        Args:
            temp_dir: Directory to use for temporary files, defaults to system temp
        """
        # Use provided temp directory or system default
        self.temp_dir = temp_dir or os.path.join(os.getcwd(), "temp")
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # Track resources with their creation time and expiration
        self.tracked_resources = {}
        
        # Load tracked resources from storage if available
        self._load_tracked_resources()
        
        logger.info(f"ResourceManager initialized with temp directory: {self.temp_dir}")
        
    @contextmanager
    def temp_file(self, prefix: str = "", suffix: str = "", delete: bool = True) -> Generator[str, None, None]:
        """
        Create a temporary file and clean up after use
        
        Args:
            prefix: Prefix for the temporary file name
            suffix: Suffix for the temporary file name (e.g., '.jpg')
            delete: Whether to delete the file after use
            
        Yields:
            Path to the temporary file
        """
        fd, temp_path = tempfile.mkstemp(suffix=suffix, prefix=prefix, dir=self.temp_dir)
        os.close(fd)
        
        try:
            logger.debug(f"Created temporary file: {temp_path}")
            yield temp_path
        finally:
            if delete and os.path.exists(temp_path):
                os.unlink(temp_path)
                logger.debug(f"Deleted temporary file: {temp_path}")
                
    @contextmanager
    def temp_directory(self, prefix: str = "", delete: bool = True) -> Generator[str, None, None]:
        """
        Create a temporary directory and clean up after use
        
        Args:
            prefix: Prefix for the temporary directory name
            delete: Whether to delete the directory after use
            
        Yields:
            Path to the temporary directory
        """
        temp_dir = tempfile.mkdtemp(prefix=prefix, dir=self.temp_dir)
        
        try:
            logger.debug(f"Created temporary directory: {temp_dir}")
            yield temp_dir
        finally:
            if delete and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                logger.debug(f"Deleted temporary directory: {temp_dir}")
    
    def register_resource(self, path: str, lifetime_hours: float = 24.0) -> bool:
        """
        Register a resource for tracking and automatic cleanup
        
        Args:
            path: Path to the resource
            lifetime_hours: Number of hours before the resource can be deleted
            
        Returns:
            True if registered successfully, False otherwise
        """
        if not os.path.exists(path):
            logger.warning(f"Cannot register non-existent resource: {path}")
            return False
            
        now = datetime.now()
        expiration = now + timedelta(hours=lifetime_hours)
        
        self.tracked_resources[path] = {
            'created': now.timestamp(),
            'expires': expiration.timestamp(),
        }
        
        # Save tracked resources to storage
        self._save_tracked_resources()
        
        logger.debug(f"Registered resource: {path}, expires: {expiration.isoformat()}")
        return True
    
    def unregister_resource(self, path: str) -> bool:
        """
        Remove a resource from tracking
        
        Args:
            path: Path to the resource
            
        Returns:
            True if unregistered successfully, False otherwise
        """
        if path in self.tracked_resources:
            del self.tracked_resources[path]
            self._save_tracked_resources()
            logger.debug(f"Unregistered resource: {path}")
            return True
            
        return False
    
    def cleanup_expired_resources(self, force: bool = False) -> Tuple[int, int]:
        """
        Delete expired resources
        
        Args:
            force: If True, delete all tracked resources regardless of expiration
            
        Returns:
            Tuple of (deleted count, failed count)
        """
        now = datetime.now().timestamp()
        to_delete = []
        
        # Find expired resources
        for path, metadata in self.tracked_resources.items():
            if force or metadata['expires'] < now:
                to_delete.append(path)
        
        # Delete expired resources
        deleted = 0
        failed = 0
        
        for path in to_delete:
            try:
                if os.path.isdir(path):
                    if os.path.exists(path):
                        shutil.rmtree(path)
                else:
                    if os.path.exists(path):
                        os.unlink(path)
                        
                del self.tracked_resources[path]
                deleted += 1
                logger.debug(f"Deleted expired resource: {path}")
            except Exception as e:
                failed += 1
                logger.warning(f"Failed to delete resource {path}: {str(e)}")
        
        # Save updated tracking data
        if deleted > 0 or failed > 0:
            self._save_tracked_resources()
            
        if deleted > 0:
            logger.info(f"Cleaned up {deleted} expired resources ({failed} failed)")
            
        return deleted, failed
    
    def monitor_disk_usage(self) -> Dict[str, Any]:
        """
        Monitor disk usage of temp directory and tracked resources
        
        Returns:
            Dictionary with usage statistics
        """
        # Get total size of temp directory
        temp_size = self._get_directory_size(self.temp_dir)
        
        # Count files by type
        file_counts = {
            "images": 0,
            "videos": 0,
            "other": 0
        }
        
        # Get information about tracked resources
        tracked_info = {
            "count": len(self.tracked_resources),
            "oldest_resource": None,
            "newest_resource": None,
            "expiring_soon": 0,
        }
        
        # Scan temp directory for files
        for root, dirs, files in os.walk(self.temp_dir):
            for file in files:
                path = os.path.join(root, file)
                ext = os.path.splitext(file)[1].lower()
                
                if ext in ('.jpg', '.jpeg', '.png', '.gif'):
                    file_counts["images"] += 1
                elif ext in ('.mp4', '.mov', '.avi'):
                    file_counts["videos"] += 1
                else:
                    file_counts["other"] += 1
        
        # Process tracked resources
        now = datetime.now().timestamp()
        oldest = now
        newest = 0
        
        for path, metadata in self.tracked_resources.items():
            created = metadata['created']
            expires = metadata['expires']
            
            # Track oldest and newest
            if created < oldest:
                oldest = created
                tracked_info["oldest_resource"] = path
            
            if created > newest:
                newest = created
                tracked_info["newest_resource"] = path
            
            # Count resources expiring in next hour
            if expires - now < 3600:
                tracked_info["expiring_soon"] += 1
        
        # Convert timestamps to human-readable format
        if tracked_info["oldest_resource"]:
            tracked_info["oldest_age_hours"] = (now - oldest) / 3600
        
        if tracked_info["newest_resource"]:
            tracked_info["newest_age_hours"] = (now - newest) / 3600
        
        # Build full result
        return {
            "total_size_mb": temp_size / (1024 * 1024),
            "file_counts": file_counts,
            "tracked_resources": tracked_info,
            "timestamp": datetime.now().isoformat()
        }
    
    def _get_directory_size(self, path: str) -> int:
        """
        Calculate total size of a directory in bytes
        
        Args:
            path: Directory path
            
        Returns:
            Size in bytes
        """
        total_size = 0
        
        for root, dirs, files in os.walk(path):
            for file in files:
                file_path = os.path.join(root, file)
                if os.path.exists(file_path):
                    total_size += os.path.getsize(file_path)
        
        return total_size
    
    def _save_tracked_resources(self) -> None:
        """Save tracked resources to storage file"""
        storage_path = os.path.join(self.temp_dir, '.resource_tracking.json')
        
        try:
            with open(storage_path, 'w') as f:
                json.dump(self.tracked_resources, f)
        except Exception as e:
            logger.warning(f"Failed to save resource tracking data: {str(e)}")
    
    def _load_tracked_resources(self) -> None:
        """Load tracked resources from storage file"""
        storage_path = os.path.join(self.temp_dir, '.resource_tracking.json')
        
        if os.path.exists(storage_path):
            try:
                with open(storage_path, 'r') as f:
                    self.tracked_resources = json.load(f)
                logger.debug(f"Loaded {len(self.tracked_resources)} tracked resources")
            except Exception as e:
                logger.warning(f"Failed to load resource tracking data: {str(e)}")
                self.tracked_resources = {}
        else:
            self.tracked_resources = {}