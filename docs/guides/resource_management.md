# Resource Management Guide

## Overview

This guide explains how to use the resource management and configuration features to handle temporary files, manage disk space, and configure the application.

## Configuration Management

The `Config` class provides centralized configuration management:

```python
from src.utils.config import Config

# Get configuration instance
config = Config.get_instance()

# Access configuration values
max_images = config.max_carousel_images
cleanup_interval = config.cleanup_interval_minutes
```

## Resource Management

The `ResourceManager` provides context managers for safe resource handling:

```python
from src.utils.resource_manager import ResourceManager

resource_manager = ResourceManager()

# Using temporary file context manager
with resource_manager.temp_file(suffix='.jpg') as temp_path:
    # File will be automatically cleaned up after the block
    process_image(temp_path)

# Using temporary directory context manager
with resource_manager.temp_directory() as temp_dir:
    # Directory and contents will be automatically cleaned up
    process_files_in_directory(temp_dir)
```

## Automatic Cleanup

The `CleanupScheduler` manages automatic resource cleanup:

```python
from src.utils.cleanup_scheduler import CleanupScheduler

# Start automatic cleanup
scheduler = CleanupScheduler.get_instance()
scheduler.start()

# Stop cleanup when done
scheduler.stop()
```

## Best Practices

1. Always use context managers for temporary resources:
```python
# Good
with resource_manager.temp_file() as path:
    process_file(path)

# Avoid
temp_path = create_temp_file()
try:
    process_file(temp_path)
finally:
    cleanup_file(temp_path)
```

2. Register resources for tracking:
```python
resource_manager.register_resource(file_path, lifetime_hours=2)
```

3. Monitor disk usage:
```python
usage = resource_manager.monitor_disk_usage()
print(f"Current storage usage: {usage['total_size_mb']:.1f}MB")
```

4. Use configuration values instead of hard-coding:
```python
# Good
max_size = config.max_storage_mb

# Avoid
max_size = 1000  # Hard-coded value
```

## Common Issues and Solutions

### High Memory Usage
If the application is using too much memory:
1. Reduce `MAX_STORAGE_MB` in configuration
2. Lower `MAX_TEMP_FILE_AGE_HOURS`
3. Enable aggressive cleanup mode

### Missing Files
If temporary files are being cleaned up too aggressively:
1. Increase `CLEANUP_INTERVAL_MINUTES`
2. Use `register_resource()` with appropriate lifetime
3. Use context managers to ensure proper cleanup

### Configuration Issues
If configuration values are not being recognized:
1. Verify `.env` file exists and contains required variables
2. Check `Config.REQUIRED_VARS` for necessary settings
3. Use `validate_environment()` to check configuration

## Configuration Reference

### Required Variables
- `INSTAGRAM_API_KEY`
- `INSTAGRAM_ACCOUNT_ID`
- `INSTAGRAM_ACCESS_TOKEN`

### Optional Variables
- `CLEANUP_INTERVAL_MINUTES` (default: 30)
- `MAX_CAROUSEL_IMAGES` (default: 10)
- `MAX_TEMP_FILE_AGE_HOURS` (default: 24)
- `MAX_STORAGE_MB` (default: 1000)