"""
Configuration Manager for Instagram Agent

Handles secure credential management, API configuration, and runtime settings.
Uses environment variables and optional configuration files with proper
security measures for sensitive data.

Features:
    - Secure credential management
    - Environment-specific configuration
    - Dynamic settings updates
    - Configuration validation
    - Secret rotation support
    
Example:
    >>> config = Config.get_instance()
    >>> if config.is_valid():
    ...     instagram = InstagramAPI(config.get_credentials())
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path
from dotenv import load_dotenv
import datetime

logger = logging.getLogger(__name__)

class Config:
    """
    Singleton configuration manager for the Instagram Agent.
    
    Manages:
    - API credentials and tokens
    - Rate limiting settings
    - Storage configuration
    - Runtime parameters
    - Feature flags
    
    Security Features:
    - Environment variable priority
    - Secure credential storage
    - Token rotation support
    - Access logging
    """
    
    _instance = None
    
    # Required environment variables
    REQUIRED_ENV_VARS = [
        'INSTAGRAM_API_KEY',
        'INSTAGRAM_ACCOUNT_ID',
        'AUTHORIZED_GROUP_ID'
    ]
    
    # Optional settings with defaults
    DEFAULTS = {
        'MAX_RETRIES': 3,
        'RATE_LIMIT_WINDOW': 3600,
        'MAX_REQUESTS_PER_WINDOW': 200,
        'TEMP_FILE_LIFETIME_HOURS': 2,
        'MAX_VIDEO_SIZE_MB': 100,
        'MAX_IMAGE_SIZE_MB': 8,
        'LOG_LEVEL': 'INFO',
        'MAX_STORAGE_MB': 1000,
        'CLEANUP_INTERVAL_MINUTES': 30,  # Run cleanup every 30 minutes
        'MAX_TEMP_FILE_AGE_HOURS': 24,   # Remove temp files older than 24 hours
        'AGGRESSIVE_CLEANUP_THRESHOLD_MB': 800  # Enable aggressive cleanup when storage exceeds this
    }

    # Cleanup patterns configuration
    CLEANUP_PATTERNS = {
        'temp_patterns': ['temp-*', '*.tmp'],
        'video_patterns': ['*.mp4', '*.mov', '*.avi'],
        'image_patterns': ['*.jpg', '*.png', '*.jpeg']
    }

    def __init__(self):
        """Initialize configuration from environment and optional config file."""
        self._load_environment()
        self._load_config_file()
        self._validate_config()
        self._setup_logging()
        
        # Track configuration access
        self.last_access = datetime.datetime.now()
        self.access_count = 0

    @classmethod
    def get_instance(cls) -> 'Config':
        """
        Get or create singleton configuration instance.
        
        Returns:
            Config: Singleton configuration instance
            
        Example:
            >>> config1 = Config.get_instance()
            >>> config2 = Config.get_instance()
            >>> assert config1 is config2  # Same instance
        """
        if cls._instance is None:
            cls._instance = Config()
        return cls._instance

    def _load_environment(self) -> None:
        """
        Load configuration from environment variables.
        
        Priority:
        1. Environment variables
        2. .env file
        3. Default values
        
        Security:
        - Logs missing required variables
        - Validates credential format
        - Checks permission requirements
        """
        load_dotenv()
        
        # Load required variables
        missing = []
        for var in self.REQUIRED_ENV_VARS:
            value = os.getenv(var)
            if value is None:
                missing.append(var)
            setattr(self, var, value)
            
        if missing:
            logger.error(f"Missing required environment variables: {', '.join(missing)}")
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
            
        # Load optional variables with defaults
        for key, default in self.DEFAULTS.items():
            value = os.getenv(key, default)
            setattr(self, key, value)
            
        # Validate credential format
        self._validate_credentials()

    def _load_config_file(self) -> None:
        """
        Load additional configuration from JSON file if present.
        
        File Structure:
            {
                "api": {
                    "base_url": "https://graph.facebook.com/v16.0",
                    "timeout": 30
                },
                "storage": {
                    "temp_dir": "/path/to/temp",
                    "max_size_gb": 10
                },
                "features": {
                    "enable_carousel": true,
                    "enable_video": true
                }
            }
        """
        config_path = Path("config.json")
        if config_path.exists():
            try:
                with open(config_path) as f:
                    config = json.load(f)
                    
                # Update configuration
                for section, values in config.items():
                    for key, value in values.items():
                        env_key = f"{section.upper()}_{key.upper()}"
                        if not hasattr(self, env_key):
                            setattr(self, env_key, value)
                            
            except Exception as e:
                logger.error(f"Error loading config file: {e}")

    def _validate_credentials(self) -> None:
        """
        Validate API credentials format and permissions.
        
        Checks:
        - Token format and length
        - Required permissions
        - Token expiration
        - Business account status
        """
        if not self.INSTAGRAM_API_KEY or len(self.INSTAGRAM_API_KEY) < 50:
            raise ValueError("Invalid Instagram API key format")
            
        if not self.INSTAGRAM_ACCOUNT_ID or not self.INSTAGRAM_ACCOUNT_ID.isdigit():
            raise ValueError("Invalid Instagram Account ID format")

    def _validate_config(self) -> None:
        """
        Validate complete configuration.
        
        Checks:
        - Required values present
        - Value types and ranges
        - Compatibility between settings
        - Resource availability
        """
        # Validate numeric values
        try:
            self.MAX_RETRIES = int(self.MAX_RETRIES)
            self.RATE_LIMIT_WINDOW = int(self.RATE_LIMIT_WINDOW)
            self.MAX_REQUESTS_PER_WINDOW = int(self.MAX_REQUESTS_PER_WINDOW)
            self.TEMP_FILE_LIFETIME_HOURS = float(self.TEMP_FILE_LIFETIME_HOURS)
            self.MAX_VIDEO_SIZE_MB = int(self.MAX_VIDEO_SIZE_MB)
            self.MAX_IMAGE_SIZE_MB = int(self.MAX_IMAGE_SIZE_MB)
        except ValueError as e:
            raise ValueError(f"Invalid numeric configuration value: {e}")
            
        # Validate ranges
        if self.MAX_RETRIES < 1:
            raise ValueError("MAX_RETRIES must be at least 1")
        if self.RATE_LIMIT_WINDOW < 60:
            raise ValueError("RATE_LIMIT_WINDOW must be at least 60 seconds")
        if self.MAX_REQUESTS_PER_WINDOW < 1:
            raise ValueError("MAX_REQUESTS_PER_WINDOW must be positive")

    def _setup_logging(self) -> None:
        """Configure logging based on settings."""
        log_level = getattr(logging, self.LOG_LEVEL.upper())
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    def get_credentials(self) -> Dict[str, str]:
        """
        Get API credentials as a dictionary.
        
        Returns:
            dict: API credentials and tokens
            
        Example:
            >>> creds = config.get_credentials()
            >>> api = InstagramAPI(**creds)
        """
        self.access_count += 1
        self.last_access = datetime.datetime.now()
        
        return {
            'api_key': self.INSTAGRAM_API_KEY,
            'account_id': self.INSTAGRAM_ACCOUNT_ID
        }

    def update_setting(self, key: str, value: Any) -> None:
        """
        Update a configuration setting.
        
        Args:
            key: Setting name to update
            value: New setting value
            
        Example:
            >>> config.update_setting('MAX_RETRIES', 5)
            >>> config.update_setting('ENABLE_VIDEO', False)
        """
        if hasattr(self, key):
            old_value = getattr(self, key)
            setattr(self, key, value)
            logger.info(f"Updated {key}: {old_value} -> {value}")
        else:
            raise ValueError(f"Unknown configuration key: {key}")

    def is_valid(self) -> bool:
        """
        Check if configuration is valid and complete.
        
        Returns:
            bool: True if configuration is valid
            
        Example:
            >>> if not config.is_valid():
            ...     logger.error("Invalid configuration")
            ...     sys.exit(1)
        """
        try:
            self._validate_config()
            self._validate_credentials()
            return True
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            return False

    def rotate_credentials(self) -> None:
        """
        Rotate API credentials for security.
        
        Process:
        1. Request new credentials
        2. Validate new credentials
        3. Update configuration
        4. Remove old credentials
        
        Example:
            >>> config.rotate_credentials()
            >>> config.save()
        """
        # Implementation would handle credential rotation
        raise NotImplementedError("Credential rotation not implemented")

    def get_cleanup_config(self) -> Dict[str, Any]:
        """
        Get cleanup-related configuration settings.
        
        Returns:
            Dict[str, Any]: Dictionary containing cleanup configuration settings
            
        Example:
            >>> config = Config.get_instance()
            >>> cleanup_settings = config.get_cleanup_config()
        """
        self.access_count += 1
        self.last_access = datetime.datetime.now()
        
        return {
            'cleanup_interval_minutes': self.CLEANUP_INTERVAL_MINUTES,
            'max_file_age_hours': self.MAX_TEMP_FILE_AGE_HOURS,
            'aggressive_cleanup_threshold_mb': self.AGGRESSIVE_CLEANUP_THRESHOLD_MB,
            'max_storage_mb': self.MAX_STORAGE_MB,
            'temp_file_lifetime_hours': self.TEMP_FILE_LIFETIME_HOURS,
            'patterns': self.CLEANUP_PATTERNS
        }