"""
Configuration Manager

Handles loading and validating configuration settings.
Supports environment variables and config files.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

@dataclass
class InstagramApiConfig:
    version: str = "v22.0"
    max_retries: int = 3
    retry_delay: float = 1.0
    request_timeout: int = 30

@dataclass
class StorageConfig:
    max_storage_mb: int = 1000
    cleanup_interval_minutes: int = 30
    max_temp_file_age_hours: int = 24
    aggressive_cleanup_threshold_mb: int = 800

@dataclass
class CleanupPatterns:
    temp_patterns: List[str] = field(default_factory=lambda: ["temp-*", "*.tmp"])
    video_patterns: List[str] = field(default_factory=lambda: ["*.mp4", "*.mov", "*.avi"])
    image_patterns: List[str] = field(default_factory=lambda: ["*.jpg", "*.png", "*.jpeg"])

@dataclass
class PathsConfig:
    temp_dir: str = "temp"
    temp_videos_dir: str = "temp_videos"
    assets_dir: str = "assets"

@dataclass
class MonitoringConfig:
    enabled: bool = True
    stats_interval: int = 300
    port: int = 5002

@dataclass
class RateLimitsConfig:
    window: int = 3600
    max_requests: int = 200
    min_interval: float = 1.0

@dataclass
class CarouselConfig:
    enabled: bool = True
    max_images: int = 10

@dataclass
class VideoConfig:
    enabled: bool = True
    max_size_mb: int = 100

@dataclass
class FeaturesConfig:
    carousel: CarouselConfig = field(default_factory=CarouselConfig)
    video: VideoConfig = field(default_factory=VideoConfig)

@dataclass
class Config:
    api: Dict[str, InstagramApiConfig] = field(default_factory=lambda: {"instagram": InstagramApiConfig()})
    storage: StorageConfig = field(default_factory=StorageConfig)
    cleanup_patterns: CleanupPatterns = field(default_factory=CleanupPatterns)
    paths: PathsConfig = field(default_factory=PathsConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    rate_limits: RateLimitsConfig = field(default_factory=RateLimitsConfig)
    features: FeaturesConfig = field(default_factory=FeaturesConfig)

    _instance = None

    @classmethod
    def get_instance(cls) -> 'Config':
        if cls._instance is None:
            cls._instance = cls()
            cls._instance.load_env()
        return cls._instance

    def load_env(self) -> None:
        """Load configuration from environment variables"""
        env_vars = {
            'INSTAGRAM_API_KEY': lambda x: setattr(self.api['instagram'], 'api_key', x),
            'INSTAGRAM_ACCOUNT_ID': lambda x: setattr(self.api['instagram'], 'account_id', x),
            'AUTHORIZED_GROUP_ID': lambda x: setattr(self, 'authorized_group_id', x),  # Adding handler for AUTHORIZED_GROUP_ID
            'MAX_RETRIES': lambda x: setattr(self.api['instagram'], 'max_retries', int(x)),
            'REQUEST_TIMEOUT': lambda x: setattr(self.api['instagram'], 'request_timeout', int(x)),
            'CLEANUP_INTERVAL': lambda x: setattr(self.storage, 'cleanup_interval_minutes', int(x)),
            'MAX_STORAGE_MB': lambda x: setattr(self.storage, 'max_storage_mb', int(x)),
            'MONITOR_STATS_INTERVAL': lambda x: setattr(self.monitoring, 'stats_interval', int(x)),
            'RATE_LIMIT_WINDOW': lambda x: setattr(self.rate_limits, 'window', int(x)),
            'RATE_LIMIT_MAX_REQUESTS': lambda x: setattr(self.rate_limits, 'max_requests', int(x))
        }

        for var, setter in env_vars.items():
            value = os.getenv(var)
            if value is not None:
                try:
                    setter(value)
                except (ValueError, TypeError) as e:
                    logger.warning(f"Failed to set {var}: {e}")
            elif var in self.REQUIRED_VARS:
                logger.error(f"Required environment variable {var} is not set")

    def get_api_config(self) -> InstagramApiConfig:
        return self.api['instagram']

    def get_storage_config(self) -> StorageConfig:
        return self.storage

    def get_monitoring_config(self) -> MonitoringConfig:
        return self.monitoring

    def get_rate_limits_config(self) -> RateLimitsConfig:
        return self.rate_limits

    def get_carousel_config(self) -> CarouselConfig:
        return self.features.carousel

    def get_video_config(self) -> VideoConfig:
        return self.features.video

import os
import json
import logging
from typing import Any, Dict, List, Optional, Union
from dotenv import load_dotenv
from pathlib import Path

logger = logging.getLogger(__name__)

class Config:
    """
    Configuration management system
    
    Loads configuration from:
    1. Environment variables
    2. Config file (config.json)
    3. Default values
    """
    
    _instance = None
    CONFIG_FILE = "config.json"
    
    # Required environment variables
    REQUIRED_VARS = [
        "INSTAGRAM_API_KEY",
        "INSTAGRAM_ACCOUNT_ID",
        "AUTHORIZED_GROUP_ID"  # Adding AUTHORIZED_GROUP_ID as required
    ]
    
    # Optional environment variables with defaults
    OPTIONAL_VARS = {
        "CLEANUP_INTERVAL_MINUTES": 30,
        "MAX_CAROUSEL_IMAGES": 10,
        "MAX_TEMP_FILE_AGE_HOURS": 24,
        "MAX_STORAGE_MB": 1000,
        "LOG_LEVEL": "INFO",
        "TEMP_DIR": "temp",
        "PORT": 5001,
    }
    
    @classmethod
    def get_instance(cls) -> 'Config':
        """Get singleton instance of Config"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        """Initialize configuration"""
        # Load environment variables
        load_dotenv()
        
        # Initialize config dict
        self._config = {}
        
        # Load from environment
        self._load_from_env()
        
        # Load from config file
        self._load_from_file()
        
        # Validate configuration
        self._validate_config()
        
        # Make common config values available as attributes
        self.INSTAGRAM_API_KEY = self.get_value('INSTAGRAM_API_KEY')
        self.INSTAGRAM_ACCOUNT_ID = self.get_value('INSTAGRAM_ACCOUNT_ID')
        self.INSTAGRAM_ACCESS_TOKEN = self.get_value('INSTAGRAM_ACCESS_TOKEN')
        self.AUTHORIZED_GROUP_ID = self.get_value('AUTHORIZED_GROUP_ID')
        self.max_carousel_images = self.get_value('MAX_CAROUSEL_IMAGES', 10)
        self.cleanup_interval_minutes = self.get_value('CLEANUP_INTERVAL_MINUTES', 30)
        
        logger.info("Configuration loaded and validated")
    
    def _load_from_env(self) -> None:
        """Load configuration from environment variables"""
        # Load required variables
        for var in self.REQUIRED_VARS:
            value = os.environ.get(var)
            if value:
                self._config[var] = value
                
        # Load optional variables with defaults
        for var, default in self.OPTIONAL_VARS.items():
            value = os.environ.get(var)
            if value:
                # Convert to appropriate type based on default
                if isinstance(default, int):
                    try:
                        value = int(value)
                    except ValueError:
                        logger.warning(f"Invalid integer value for {var}: {value}, using default {default}")
                        value = default
                elif isinstance(default, float):
                    try:
                        value = float(value)
                    except ValueError:
                        logger.warning(f"Invalid float value for {var}: {value}, using default {default}")
                        value = default
                elif isinstance(default, bool):
                    value = value.lower() in ('true', 'yes', '1', 't', 'y')
            else:
                value = default
                
            self._config[var] = value
    
    def _load_from_file(self) -> None:
        """Load configuration from config file"""
        if os.path.exists(self.CONFIG_FILE):
            try:
                with open(self.CONFIG_FILE, 'r') as f:
                    file_config = json.load(f)
                
                # Update config with values from file
                self._merge_config(file_config)
                logger.info(f"Loaded configuration from {self.CONFIG_FILE}")
            except Exception as e:
                logger.warning(f"Failed to load configuration from file: {e}")
    
    def _merge_config(self, file_config: Dict[str, Any]) -> None:
        """
        Merge configuration from file into current config
        
        Args:
            file_config: Configuration from file
        """
        if not isinstance(file_config, dict):
            logger.warning("Invalid configuration file format")
            return
            
        # Flatten nested config if needed
        flat_config = {}
        
        for key, value in file_config.items():
            if isinstance(value, dict):
                # Flatten one level of nesting with underscores
                for nested_key, nested_value in value.items():
                    flat_key = f"{key}_{nested_key}".upper()
                    flat_config[flat_key] = nested_value
            else:
                flat_config[key.upper()] = value
                
        # Update config with flattened values
        for key, value in flat_config.items():
            # Only override if not already set by environment variable
            if key not in self._config:
                self._config[key] = value
    
    def _validate_config(self) -> None:
        """Validate required configuration values"""
        missing = []
        
        for var in self.REQUIRED_VARS:
            if var not in self._config or self._config[var] is None:
                missing.append(var)
                
        if missing:
            logger.warning(f"Missing required configuration: {', '.join(missing)}")
    
    def get_value(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        return self._config.get(key, default)
    
    def set_value(self, key: str, value: Any) -> None:
        """
        Set configuration value
        
        Args:
            key: Configuration key
            value: Configuration value
        """
        self._config[key] = value
        
        # If this is a common attribute, update it
        if key in ('INSTAGRAM_API_KEY', 'INSTAGRAM_ACCOUNT_ID', 'INSTAGRAM_ACCESS_TOKEN', 
                  'AUTHORIZED_GROUP_ID', 'MAX_CAROUSEL_IMAGES', 'CLEANUP_INTERVAL_MINUTES'):
            setattr(self, key.lower() if key == key.upper() else key, value)
    
    def update_settings(self, settings: Dict[str, Any]) -> None:
        """
        Update multiple settings at once
        
        Args:
            settings: Dictionary of settings to update
        """
        for key, value in settings.items():
            self.set_value(key, value)
    
    def save_to_file(self) -> bool:
        """
        Save current configuration to file
        
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            # Convert flat config to nested for better readability
            nested_config = {}
            
            for key, value in self._config.items():
                if "_" in key:
                    # Convert snake_case to nested dictionary
                    parts = key.lower().split("_")
                    current = nested_config
                    
                    for part in parts[:-1]:
                        if part not in current:
                            current[part] = {}
                        current = current[part]
                        
                    current[parts[-1]] = value
                else:
                    # Keep non-nested keys as is
                    nested_config[key.lower()] = value
            
            # Save to file
            with open(self.CONFIG_FILE, 'w') as f:
                json.dump(nested_config, f, indent=2)
                
            logger.info(f"Configuration saved to {self.CONFIG_FILE}")
            return True
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            return False
    
    def is_valid(self) -> bool:
        """
        Check if configuration is valid
        
        Returns:
            True if all required values are present, False otherwise
        """
        for var in self.REQUIRED_VARS:
            if var not in self._config or self._config[var] is None:
                return False
        return True
    
    def get_all(self) -> Dict[str, Any]:
        """
        Get all configuration values
        
        Returns:
            Dictionary of all configuration values
        """
        # Return a copy to prevent modification
        return dict(self._config)
    
    def validate_environment(self) -> Dict[str, Any]:
        """
        Validate the environment and return status
        
        Returns:
            Status dictionary with validation results
        """
        status = {
            'valid': True,
            'missing': [],
            'instagram_api': False,
            'storage': {
                'temp_dir_exists': False,
                'temp_dir_writable': False
            }
        }
        
        # Check required variables
        for var in self.REQUIRED_VARS:
            if var not in self._config or self._config[var] is None:
                status['valid'] = False
                status['missing'].append(var)
                
        # Check Instagram API credentials specifically
        if ('INSTAGRAM_API_KEY' in self._config and 
            'INSTAGRAM_ACCOUNT_ID' in self._config and
            self._config['INSTAGRAM_API_KEY'] and 
            self._config['INSTAGRAM_ACCOUNT_ID']):
            status['instagram_api'] = True
            
        # Check temp directory
        temp_dir = self.get_value('TEMP_DIR', 'temp')
        if os.path.exists(temp_dir):
            status['storage']['temp_dir_exists'] = True
            
            # Check if directory is writable
            try:
                test_file = os.path.join(temp_dir, '.write_test')
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
                status['storage']['temp_dir_writable'] = True
            except Exception:
                pass
                
        return status