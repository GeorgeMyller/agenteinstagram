from dataclasses import dataclass, field
from typing import Dict, List, Optional
from pathlib import Path
import os
import tempfile
import logging

logger = logging.getLogger(__name__)

@dataclass
class ApplicationPaths:
    """Centralized management of application paths"""
    
    # Base paths
    base_dir: Path = field(default_factory=lambda: Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
    assets_dir: Path = field(default_factory=lambda: Path("assets"))
    temp_dir: Path = field(default_factory=lambda: Path("temp"))
    temp_videos_dir: Path = field(default_factory=lambda: Path("temp_videos"))
    
    # Additional paths
    config_file: Path = field(default_factory=lambda: Path("config.json"))
    templates_dir: Path = field(default_factory=lambda: Path("monitoring_templates"))
    
    def __post_init__(self):
        """Initialize and validate paths after creation"""
        # Make paths absolute if they're relative
        if not self.assets_dir.is_absolute():
            self.assets_dir = self.base_dir / self.assets_dir
        
        if not self.temp_dir.is_absolute():
            self.temp_dir = self.base_dir / self.temp_dir
            
        if not self.temp_videos_dir.is_absolute():
            self.temp_videos_dir = self.base_dir / self.temp_videos_dir
            
        if not self.config_file.is_absolute():
            self.config_file = self.base_dir / self.config_file
            
        if not self.templates_dir.is_absolute():
            self.templates_dir = self.base_dir / self.templates_dir
        
        # Ensure critical directories exist
        self._ensure_dirs()
    
    def _ensure_dirs(self) -> None:
        """Ensure all required directories exist"""
        dirs_to_check = [
            self.assets_dir,
            self.temp_dir,
            self.temp_videos_dir,
            self.templates_dir
        ]
        
        for directory in dirs_to_check:
            try:
                if not directory.exists():
                    directory.mkdir(parents=True)
                    logger.info(f"Created directory: {directory}")
            except Exception as e:
                logger.error(f"Error creating directory {directory}: {e}")
    
    def create_temp_file(
        self,
        suffix: str = None,
        prefix: str = None,
        directory: str = None
    ) -> Path:
        """
        Create a temporary file path
        
        Args:
            suffix: File suffix (e.g. '.jpg')
            prefix: File prefix
            directory: Directory name (defaults to temp_dir)
            
        Returns:
            Path object for the temporary file
        """
        if directory == "videos":
            target_dir = self.temp_videos_dir
        else:
            target_dir = self.temp_dir
        
        # Ensure directory exists
        if not target_dir.exists():
            target_dir.mkdir(parents=True)
        
        # Create a unique filename
        temp_file = tempfile.NamedTemporaryFile(
            suffix=suffix,
            prefix=prefix,
            dir=target_dir,
            delete=False
        )
        
        # Return the path
        return Path(temp_file.name)
        
    def get_asset_path(self, filename: str) -> Path:
        """
        Get path to an asset file
        
        Args:
            filename: Asset filename
            
        Returns:
            Path to the asset file
        """
        return self.assets_dir / filename
        
    def get_paths_dict(self) -> Dict[str, str]:
        """
        Get dictionary of paths (for compatibility with code that expects dict)
        
        Returns:
            Dictionary of path names and their string representations
        """
        return {
            "base_dir": str(self.base_dir),
            "assets_dir": str(self.assets_dir),
            "temp_dir": str(self.temp_dir),
            "temp_videos_dir": str(self.temp_videos_dir),
            "config_file": str(self.config_file),
            "templates_dir": str(self.templates_dir)
        }

# Create a singleton instance
Paths = ApplicationPaths()
