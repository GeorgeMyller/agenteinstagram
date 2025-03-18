"""
Test Configuration and Fixtures

Provides test fixtures and utilities for testing Instagram API integration.
Includes mock API responses, test data generators, and helper functions.

Usage:
    pytest will automatically use these fixtures in test files.
    Import specific fixtures in test files as needed.
"""

import os
import json
import pytest
import tempfile
from typing import Dict, List, Any
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.utils.config import Config
from src.instagram.instagram_carousel_service import InstagramCarouselService
from src.instagram.base_instagram_service import BaseInstagramService

@pytest.fixture
def test_config():
    """
    Provide test configuration with mock credentials.
    
    Returns:
        Config: Test configuration instance
        
    Example:
        def test_api_call(test_config):
            api = InstagramAPI(test_config.get_credentials())
            assert api.is_configured()
    """
    config = Config()
    config.INSTAGRAM_API_KEY = "test_api_key"
    config.INSTAGRAM_ACCOUNT_ID = "123456789"
    config.MAX_RETRIES = 1
    return config

@pytest.fixture
def mock_api_response():
    """
    Generate mock Instagram API responses.
    
    Returns:
        function: Response generator
        
    Example:
        def test_post_image(mock_api_response):
            response = mock_api_response(
                success=True,
                media_id="123456789"
            )
            with patch('requests.post') as mock_post:
                mock_post.return_value.json.return_value = response
                result = api.post_image("test.jpg")
                assert result['media_id'] == "123456789"
    """
    def _generate_response(success: bool = True, **kwargs) -> Dict[str, Any]:
        if success:
            return {
                "id": kwargs.get("media_id", "12345"),
                "status_code": kwargs.get("status_code", 200),
                **kwargs
            }
        else:
            return {
                "error": {
                    "message": kwargs.get("error_message", "API Error"),
                    "type": kwargs.get("error_type", "OAuthException"),
                    "code": kwargs.get("error_code", 190),
                    "error_subcode": kwargs.get("error_subcode", 460),
                    "fbtrace_id": kwargs.get("fbtrace_id", "xyz123")
                }
            }
    return _generate_response

@pytest.fixture
def test_images(tmp_path) -> List[str]:
    """
    Create temporary test images.
    
    Args:
        tmp_path: pytest temporary directory
        
    Returns:
        List[str]: Paths to test images
        
    Example:
        def test_carousel(test_images):
            result = api.post_carousel(test_images)
            assert result['media_count'] == len(test_images)
    """
    from PIL import Image
    
    image_paths = []
    sizes = [(1080, 1080), (1080, 1350), (1080, 608)]
    
    for i, size in enumerate(sizes):
        img = Image.new('RGB', size, color='white')
        path = tmp_path / f"test_image_{i}.jpg"
        img.save(path)
        image_paths.append(str(path))
        
    return image_paths

@pytest.fixture
def mock_instagram_service(test_config, mock_api_response):
    """
    Provide mock Instagram service for testing.
    
    Returns:
        BaseInstagramService: Mocked service instance
        
    Example:
        def test_authentication(mock_instagram_service):
            assert mock_instagram_service.verify_credentials()
    """
    service = BaseInstagramService(
        api_key=test_config.INSTAGRAM_API_KEY,
        account_id=test_config.INSTAGRAM_ACCOUNT_ID
    )
    
    # Mock API methods
    service._make_request = MagicMock(
        return_value=mock_api_response(success=True)
    )
    service.verify_credentials = MagicMock(return_value=True)
    
    return service

@pytest.fixture
def mock_carousel_service(test_config, mock_api_response):
    """
    Provide mock carousel service for testing.
    
    Returns:
        InstagramCarouselService: Mocked carousel service
        
    Example:
        def test_carousel_upload(mock_carousel_service, test_images):
            result = mock_carousel_service.post_carousel(test_images)
            assert result['success'] == True
    """
    service = InstagramCarouselService(
        api_key=test_config.INSTAGRAM_API_KEY,
        account_id=test_config.INSTAGRAM_ACCOUNT_ID
    )
    
    # Mock carousel methods
    service.create_media_container = MagicMock(
        return_value="container_123"
    )
    service.upload_carousel_images = MagicMock(
        return_value={"success": True, "media_id": "123456789"}
    )
    
    return service

@pytest.fixture
def sample_error_responses() -> Dict[str, Dict]:
    """
    Provide sample error responses for testing error handling.
    
    Returns:
        Dict[str, Dict]: Map of error scenarios to responses
        
    Example:
        def test_rate_limit(sample_error_responses):
            with patch('requests.post') as mock_post:
                mock_post.return_value.json.return_value = (
                    sample_error_responses['rate_limit']
                )
                with pytest.raises(RateLimitError) as exc:
                    api.post_image("test.jpg")
                assert exc.value.retry_after == 3600
    """
    return {
        'rate_limit': {
            "error": {
                "message": "Application request limit reached",
                "code": 4,
                "error_subcode": 2207051,
                "fbtrace_id": "abc123",
                "retry_after": 3600
            }
        },
        'invalid_token': {
            "error": {
                "message": "Invalid OAuth access token",
                "type": "OAuthException",
                "code": 190,
                "error_subcode": 460,
                "fbtrace_id": "xyz789"
            }
        },
        'media_error': {
            "error": {
                "message": "Invalid image file format",
                "type": "MediaError",
                "code": 2208001,
                "fbtrace_id": "def456"
            }
        }
    }

@pytest.fixture
def test_video(tmp_path) -> str:
    """
    Create a test video file.
    
    Args:
        tmp_path: pytest temporary directory
        
    Returns:
        str: Path to test video file
        
    Example:
        def test_video_upload(test_video):
            result = api.post_video(test_video)
            assert result['media_type'] == 'VIDEO'
    """
    import numpy as np
    import cv2
    
    video_path = str(tmp_path / "test_video.mp4")
    
    # Create a simple 3-second video
    fps = 30
    duration = 3
    size = (1080, 1080)
    
    out = cv2.VideoWriter(
        video_path,
        cv2.VideoWriter_fourcc(*'mp4v'),
        fps,
        size
    )
    
    # Generate frames
    for _ in range(fps * duration):
        frame = np.random.randint(0, 255, (*size, 3), dtype=np.uint8)
        out.write(frame)
        
    out.release()
    return video_path

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", 
        "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers",
        "slow: mark test as slow running"
    )
    
def pytest_collection_modifyitems(config, items):
    """Modify test collection based on markers."""
    if not config.getoption("--run-integration"):
        skip_integration = pytest.mark.skip(
            reason="Need --run-integration option to run"
        )
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_integration)
                
    if not config.getoption("--run-slow"):
        skip_slow = pytest.mark.skip(
            reason="Need --run-slow option to run"
        )
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)

def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="run integration tests"
    )
    parser.addoption(
        "--run-slow",
        action="store_true",
        default=False,
        help="run slow tests"
    )