import pytest
import os
import tempfile
from pathlib import Path
from src.utils.config import Config
from src.utils.resource_manager import ResourceManager
from src.utils.cleanup_utility import CleanupUtility
from src.utils.cleanup_scheduler import CleanupScheduler

@pytest.fixture
def test_env():
    """Set up test environment variables."""
    os.environ['INSTAGRAM_API_KEY'] = 'test_key'
    os.environ['INSTAGRAM_ACCOUNT_ID'] = 'test_account'
    os.environ['INSTAGRAM_ACCESS_TOKEN'] = 'test_token'
    os.environ['CLEANUP_INTERVAL_MINUTES'] = '5'
    yield
    # Clean up environment after tests
    for var in ['INSTAGRAM_API_KEY', 'INSTAGRAM_ACCOUNT_ID', 'INSTAGRAM_ACCESS_TOKEN', 'CLEANUP_INTERVAL_MINUTES']:
        os.environ.pop(var, None)

def test_config_initialization(test_env):
    """Test configuration initialization and validation."""
    config = Config.get_instance()
    assert config.instagram_api_key == 'test_key'
    assert config.cleanup_interval_minutes == 5
    assert config.max_carousel_images == 10  # Default value

def test_resource_manager_temp_file():
    """Test temporary file management."""
    manager = ResourceManager()
    test_content = b"test content"
    
    with manager.temp_file(suffix='.txt') as temp_path:
        assert temp_path.exists()
        temp_path.write_bytes(test_content)
        assert temp_path.read_bytes() == test_content
    
    assert not temp_path.exists()  # File should be cleaned up

def test_resource_manager_temp_directory():
    """Test temporary directory management."""
    manager = ResourceManager()
    
    with manager.temp_directory() as temp_dir:
        assert temp_dir.exists()
        assert temp_dir.is_dir()
        
        # Create a test file in the directory
        test_file = temp_dir / "test.txt"
        test_file.write_text("test")
        assert test_file.exists()
    
    assert not temp_dir.exists()  # Directory should be cleaned up

def test_cleanup_utility():
    """Test cleanup utility functions."""
    utility = CleanupUtility()
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create some test files
        path = Path(temp_dir)
        test_files = []
        for i in range(3):
            file_path = path / f"temp-{i}.txt"
            file_path.write_text("test")
            test_files.append(file_path)
        
        # Test cleanup
        removed = utility.cleanup_temp_files(temp_dir, "temp-*", max_age_hours=0)
        assert removed == 3
        assert not any(f.exists() for f in test_files)

def test_cleanup_scheduler():
    """Test cleanup scheduler operation."""
    scheduler = CleanupScheduler.get_instance()
    
    # Start scheduler
    scheduler.start()
    assert scheduler._thread is not None
    assert scheduler._thread.is_alive()
    
    # Stop scheduler
    scheduler.stop()
    assert not scheduler._thread.is_alive()

def test_resource_registration():
    """Test resource registration and tracking."""
    manager = ResourceManager()
    
    with manager.temp_file() as temp_path:
        # Register resource with 1 hour lifetime
        manager.register_resource(temp_path, lifetime_hours=1)
        
        # Check disk usage monitoring
        usage = manager.monitor_disk_usage()
        assert usage is not None
        assert 'total_size_mb' in usage
        assert 'file_count' in usage

def test_aggressive_cleanup():
    """Test aggressive cleanup mode."""
    utility = CleanupUtility()
    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir)
        
        # Create large test files
        for i in range(5):
            file_path = path / f"temp-{i}.txt"
            file_path.write_bytes(os.urandom(1024 * 1024))  # 1MB files
        
        # Test storage limit enforcement
        success = utility.enforce_storage_limit(temp_dir, max_size_mb=2)
        assert success
        
        # Check that files were removed to meet size limit
        remaining_size = sum(f.stat().st_size for f in path.glob("*"))
        assert remaining_size <= 2 * 1024 * 1024  # Should be under 2MB