"""
Configuration Manager

Handles loading and validating configuration settings.
Supports environment variables and config files.
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class ConfigManager:
    """Manages application configuration"""
    
    _instance = None
    
    def __new__(cls):
        """Singleton pattern"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize config manager"""
        if not hasattr(self, 'config'):
            self.config = {}
            self.load_defaults()
    
    def load_defaults(self):
        """Load default configuration"""
        self.config = {
            'instagram': {
                'api': {
                    'base_url': 'https://graph.instagram.com/v12.0',
                    'timeout': 30,
                    'retries': 3
                },
                'rate_limits': {
                    'per_second': 2,
                    'per_minute': 30,
                    'per_hour': 200,
                    'per_day': 1000
                },
                'media': {
                    'max_size_mb': 8,
                    'allowed_types': [
                        'image/jpeg',
                        'image/png',
                        'video/mp4'
                    ],
                    'max_caption_length': 2200,
                    'max_hashtags': 30
                }
            },
            'monitoring': {
                'enabled': True,
                'state_file': 'monitor_state.json',
                'max_age_hours': 24
            },
            'rate_limiting': {
                'state_file': 'rate_limit_state.json',
                'backoff_multiplier': 2,
                'max_backoff': 3600
            }
        }
    
    def load_env(self):
        """Load configuration from environment variables"""
        env_mappings = {
            'INSTAGRAM_ACCESS_TOKEN': ('instagram.auth.access_token', str),
            'INSTAGRAM_CLIENT_ID': ('instagram.auth.client_id', str),
            'INSTAGRAM_CLIENT_SECRET': ('instagram.auth.client_secret', str),
            'INSTAGRAM_BUSINESS_ACCOUNT_ID': (
                'instagram.auth.business_account_id',
                str
            ),
            'API_BASE_URL': ('instagram.api.base_url', str),
            'API_TIMEOUT': ('instagram.api.timeout', int),
            'API_RETRIES': ('instagram.api.retries', int),
            'MONITORING_ENABLED': ('monitoring.enabled', bool),
            'MONITORING_STATE_FILE': ('monitoring.state_file', str),
            'RATE_LIMIT_STATE_FILE': ('rate_limiting.state_file', str)
        }
        
        for env_var, (config_path, type_cast) in env_mappings.items():
            value = os.environ.get(env_var)
            if value is not None:
                try:
                    if type_cast == bool:
                        value = value.lower() in ('true', '1', 'yes')
                    else:
                        value = type_cast(value)
                    self.set_value(config_path, value)
                except ValueError as e:
                    logger.warning(
                        f"Failed to parse {env_var}: {e}"
                    )
    
    def load_file(self, path: str):
        """
        Load configuration from JSON file
        
        Args:
            path: Path to config file
        """
        try:
            with open(path) as f:
                file_config = json.load(f)
            
            self.merge_config(file_config)
            
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to load config file: {e}")
    
    def merge_config(self, new_config: Dict[str, Any]):
        """
        Merge new configuration with existing
        
        Args:
            new_config: New config to merge
        """
        def merge_dict(base: dict, update: dict) -> dict:
            for key, value in update.items():
                if (
                    key in base
                    and isinstance(base[key], dict)
                    and isinstance(value, dict)
                ):
                    merge_dict(base[key], value)
                else:
                    base[key] = value
            return base
        
        self.config = merge_dict(self.config, new_config)
    
    def get_value(
        self,
        path: str,
        default: Any = None
    ) -> Any:
        """
        Get configuration value by path
        
        Args:
            path: Dot-notation path to config value
            default: Default value if not found
            
        Returns:
            Config value or default
        """
        try:
            value = self.config
            for key in path.split('.'):
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def set_value(self, path: str, value: Any):
        """
        Set configuration value by path
        
        Args:
            path: Dot-notation path to config value
            value: Value to set
        """
        keys = path.split('.')
        current = self.config
        
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        current[keys[-1]] = value
    
    def validate(self) -> bool:
        """
        Validate configuration
        
        Returns:
            bool: True if valid
        """
        required = [
            'instagram.auth.access_token',
            'instagram.auth.business_account_id'
        ]
        
        missing = [
            path for path in required
            if not self.get_value(path)
        ]
        
        if missing:
            logger.error(
                f"Missing required config values: {missing}"
            )
            return False
        
        return True
    
    def save_file(self, path: str):
        """
        Save configuration to file
        
        Args:
            path: Path to save config file
        """
        try:
            with open(path, 'w') as f:
                json.dump(self.config, f, indent=2)
        except IOError as e:
            logger.error(f"Failed to save config file: {e}")
    
    def get_all(self) -> Dict[str, Any]:
        """
        Get complete configuration
        
        Returns:
            Dict with all config values
        """
        return self.config.copy()