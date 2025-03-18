import os
import pytest
import tempfile
from PIL import Image
import base64
import json
from pathlib import Path
from src.instagram.instagram_post_service import InstagramPostService
from src.instagram.instagram_carousel_service import InstagramCarouselService
from src.instagram.instagram_reels_publisher import ReelsPublisher
from src.utils.config import Config

class TestInstagramServices:
    """Test suite for Instagram posting services"""
    
    @pytest.fixture
    def test_image(self):
        """Create a test image for testing"""
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            # Create a simple test image
            image = Image.new('RGB', (1080, 1080), color='red')
            image.save(tmp.name, 'JPEG')
            yield tmp.name
            # Cleanup
            os.unlink(tmp.name)
    
    @pytest.fixture
    def test_video(self):
        """Create a test video for testing"""
        # You would implement video creation here
        # For now, we'll just use a path
        return "test_video.mp4"
    
    @pytest.fixture
    def config(self):
        """Get configuration instance"""
        return Config.get_instance()
    
    def test_post_service_initialization(self, config):
        """Test Instagram Post Service initialization"""
        service = InstagramPostService()
        assert service.access_token == config.INSTAGRAM_API_KEY
        assert service.instagram_account_id == config.INSTAGRAM_ACCOUNT_ID
    
    def test_carousel_service_initialization(self, config):
        """Test Instagram Carousel Service initialization"""
        service = InstagramCarouselService()
        assert service.access_token == config.INSTAGRAM_API_KEY
        assert service.instagram_account_id == config.INSTAGRAM_ACCOUNT_ID
    
    def test_reels_publisher_initialization(self, config):
        """Test Reels Publisher initialization"""
        publisher = ReelsPublisher()
        assert publisher.access_token == config.INSTAGRAM_API_KEY
        assert publisher.instagram_account_id == config.INSTAGRAM_ACCOUNT_ID
    
    def test_post_image(self, test_image):
        """Test posting a single image"""
        service = InstagramPostService()
        
        # Convert image to base64 for testing
        with open(test_image, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
        
        # Create a test job
        job_id = service.queue_post(test_image, "Test caption")
        assert job_id is not None
        
        # Check job status
        status = service.check_job_status(job_id)
        assert status is not None
        assert 'status' in status
    
    def test_post_carousel(self, test_image):
        """Test posting a carousel"""
        service = InstagramCarouselService()
        
        # Create multiple test images
        image_paths = [test_image] * 3  # Use the same test image 3 times
        
        # Create a test carousel job
        job_id = service.queue_carousel(image_paths, "Test carousel")
        assert job_id is not None
        
        # Check job status
        status = service.check_job_status(job_id)
        assert status is not None
        assert 'status' in status
    
    def test_post_reel(self, test_video):
        """Test posting a reel"""
        publisher = ReelsPublisher()
        
        # Validate video first
        validation = publisher.validate_video(test_video)
        if not validation['valid']:
            pytest.skip(f"Test video invalid: {validation['issues']}")
        
        # Create a test reel job
        job_id = publisher.queue_reel(test_video, "Test reel")
        assert job_id is not None
        
        # Check job status
        status = publisher.check_job_status(job_id)
        assert status is not None
        assert 'status' in status
    
    def test_rate_limiting(self):
        """Test rate limiting functionality"""
        service = InstagramPostService()
        
        # Simulate multiple requests to test rate limiting
        for _ in range(5):
            response = service._make_request('GET', 'test')
            assert response is not None
    
    def test_error_handling(self):
        """Test error handling"""
        service = InstagramPostService()
        
        # Test with invalid image
        with pytest.raises(Exception):
            service.queue_post("nonexistent.jpg", "Test caption")
        
        # Test with invalid token
        service.access_token = "invalid_token"
        with pytest.raises(Exception):
            service._make_request('GET', 'test')
    
    def test_cleanup(self, test_image):
        """Test cleanup functionality"""
        service = InstagramPostService()
        
        # Create a test post
        job_id = service.queue_post(test_image, "Test cleanup")
        assert job_id is not None
        
        # Force cleanup
        service._cleanup_old_files()
        
        # Verify cleanup
        status = service.check_job_status(job_id)
        assert status is not None

"""
Tests for Instagram services.

Tests cover:
- Image validation and normalization
- Post creation and publishing
- Carousel handling
- Rate limiting
- Error handling
"""

import os
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from src.instagram.instagram_post_service import InstagramPostService
from src.instagram.instagram_carousel_service import InstagramCarouselService
from src.instagram.instagram_reels_publisher import ReelsPublisher
from src.instagram.image_validator import InstagramImageValidator
from src.instagram.errors import (
    AuthenticationError,
    RateLimitError,
    MediaError,
    BusinessValidationError
)
from src.utils.monitor import ApiMonitor
from src.utils.rate_limit import RateLimitHandler

# Test fixtures
@pytest.fixture
def mock_api_response():
    """Mock successful API response"""
    return {
        'id': '12345',
        'status_code': 'FINISHED',
        'permalink': 'https://instagram.com/p/123'
    }

@pytest.fixture
def mock_error_response():
    """Mock error API response"""
    return {
        'error': {
            'message': 'Test error',
            'code': 190,
            'error_subcode': 460
        }
    }

@pytest.fixture
def sample_image(tmp_path):
    """Create a temporary test image"""
    from PIL import Image
    
    image_path = tmp_path / "test.jpg"
    img = Image.new('RGB', (1080, 1080), color='white')
    img.save(image_path)
    
    return str(image_path)

@pytest.fixture
def sample_video(tmp_path):
    """Create a temporary test video"""
    import numpy as np
    import cv2
    
    video_path = str(tmp_path / "test.mp4")
    
    # Create blank video
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(video_path, fourcc, 30.0, (1080,1920))
    
    # Write 30 frames (1 second)
    for _ in range(30):
        frame = np.zeros((1920,1080,3), np.uint8)
        out.write(frame)
    
    out.release()
    return video_path

class TestInstagramPostService:
    """Test single image post functionality"""
    
    def test_create_media_container(self, sample_image, mock_api_response):
        """Test creating media container"""
        with patch('requests.post') as mock_post:
            mock_post.return_value.json.return_value = mock_api_response
            mock_post.return_value.ok = True
            
            service = InstagramPostService()
            container_id = service.create_media_container(
                sample_image,
                "Test caption"
            )
            
            assert container_id == mock_api_response['id']
    
    def test_publish_media(self, mock_api_response):
        """Test publishing media"""
        with patch('requests.post') as mock_post:
            mock_post.return_value.json.return_value = mock_api_response
            mock_post.return_value.ok = True
            
            service = InstagramPostService()
            post_id = service.publish_media('12345')
            
            assert post_id == mock_api_response['id']
    
    def test_rate_limit_handling(self, sample_image):
        """Test rate limit error handling"""
        with patch('requests.post') as mock_post:
            mock_post.return_value.ok = False
            mock_post.return_value.json.return_value = {
                'error': {
                    'code': 4,
                    'message': 'Rate limit exceeded'
                }
            }
            
            service = InstagramPostService()
            with pytest.raises(RateLimitError):
                service.create_media_container(sample_image, "Test")

class TestInstagramCarouselService:
    """Test carousel post functionality"""
    
    def test_create_carousel(self, sample_image, mock_api_response):
        """Test creating carousel container"""
        with patch('requests.post') as mock_post:
            mock_post.return_value.json.return_value = mock_api_response
            mock_post.return_value.ok = True
            
            service = InstagramCarouselService()
            container_id = service.create_carousel_container(
                [sample_image] * 3,
                "Test carousel"
            )
            
            assert container_id == mock_api_response['id']
    
    def test_carousel_validation(self, sample_image):
        """Test carousel validation rules"""
        validator = InstagramImageValidator()
        
        # Test minimum images
        result = validator.process_carousel([sample_image])
        assert result['status'] == 'error'
        assert 'requires at least 2 images' in result['message']
        
        # Test maximum images
        result = validator.process_carousel([sample_image] * 11)
        assert result['status'] == 'error'
        assert 'limited to 10 images' in result['message']

class TestReelsPublisher:
    """Test reels functionality"""
    
    def test_video_validation(self, sample_video):
        """Test video validation"""
        publisher = ReelsPublisher()
        result = publisher.validate_video(sample_video)
        
        assert result['valid']
        assert 'duration' in result
        assert 'dimensions' in result
    
    def test_create_reel(self, sample_video, mock_api_response):
        """Test creating reel container"""
        with patch('requests.post') as mock_post:
            mock_post.return_value.json.return_value = mock_api_response
            mock_post.return_value.ok = True
            
            publisher = ReelsPublisher()
            container_id = publisher.create_container(
                sample_video,
                "Test reel",
                True
            )
            
            assert container_id == mock_api_response['id']

class TestImageValidator:
    """Test image validation"""
    
    def test_image_size_validation(self, tmp_path):
        """Test image size requirements"""
        validator = InstagramImageValidator()
        
        # Test undersized image
        small_path = tmp_path / "small.jpg"
        with Image.new('RGB', (200, 200)) as img:
            img.save(small_path)
        
        result = validator.process_single_photo(str(small_path))
        assert result['status'] == 'error'
        assert 'too small' in result['message']
        
        # Test oversized image
        large_path = tmp_path / "large.jpg"
        with Image.new('RGB', (2000, 2000)) as img:
            img.save(large_path)
            
        result = validator.process_single_photo(str(large_path))
        assert result['status'] == 'error'
        assert 'too large' in result['message']
    
    def test_aspect_ratio_validation(self, tmp_path):
        """Test aspect ratio requirements"""
        validator = InstagramImageValidator()
        
        # Test narrow image
        narrow_path = tmp_path / "narrow.jpg"
        with Image.new('RGB', (320, 800)) as img:
            img.save(narrow_path)
            
        result = validator.process_single_photo(str(narrow_path))
        assert result['status'] == 'error'
        assert 'too narrow' in result['message']
        
        # Test wide image
        wide_path = tmp_path / "wide.jpg"
        with Image.new('RGB', (800, 320)) as img:
            img.save(wide_path)
            
        result = validator.process_single_photo(str(wide_path))
        assert result['status'] == 'error'
        assert 'too wide' in result['message']

class TestRateLimiting:
    """Test rate limiting functionality"""
    
    def test_rate_limit_windows(self):
        """Test rate limit windows"""
        handler = RateLimitHandler()
        
        # Fill per-minute quota
        for _ in range(30):
            assert handler.check_rate_limit('test_endpoint')
            handler.add_request('test_endpoint')
        
        # Should be rate limited
        assert not handler.check_rate_limit('test_endpoint')
    
    def test_backoff_strategy(self):
        """Test exponential backoff"""
        handler = RateLimitHandler()
        
        # Trigger backoff
        for _ in range(35):
            if handler.check_rate_limit('test_endpoint'):
                handler.add_request('test_endpoint')
        
        wait_time = handler.get_wait_time('test_endpoint')
        assert wait_time > 0
        
        # Second backoff should be longer
        wait_time_2 = handler.get_wait_time('test_endpoint')
        assert wait_time_2 > wait_time

class TestErrorHandling:
    """Test error handling"""
    
    def test_authentication_error(self, mock_error_response):
        """Test authentication error handling"""
        with patch('requests.post') as mock_post:
            mock_post.return_value.ok = False
            mock_post.return_value.json.return_value = mock_error_response
            
            service = InstagramPostService()
            with pytest.raises(AuthenticationError) as exc:
                service.publish_media('12345')
            
            assert exc.value.error_code == 190
    
    def test_media_error(self, sample_image):
        """Test media error handling"""
        # Corrupt image
        with open(sample_image, 'wb') as f:
            f.write(b'invalid image data')
        
        validator = InstagramImageValidator()
        result = validator.process_single_photo(sample_image)
        
        assert result['status'] == 'error'
        assert 'Invalid' in result['message']

class TestMonitoring:
    """Test API monitoring"""
    
    def test_track_api_calls(self):
        """Test API call tracking"""
        monitor = ApiMonitor()
        monitor.start()
        
        # Track successful call
        monitor.track_api_call('test_endpoint', success=True, duration=1.5)
        
        # Track error
        monitor.track_error('test_endpoint', 'Test error')
        
        # Check stats
        stats = monitor.get_stats()
        assert stats['total_calls'] == 1
        assert stats['total_errors'] == 1
        
        monitor.stop()
    
    def test_health_check(self):
        """Test health status calculation"""
        monitor = ApiMonitor()
        monitor.start()
        
        # Add some test data
        for _ in range(10):
            monitor.track_api_call('test_endpoint', success=True)
        
        monitor.track_error('test_endpoint', 'Test error')
        
        # Check health
        health = monitor.check_health()
        assert health['status'] == 'healthy'  # 90% success rate
        assert health['error_rate'] == 0.1
        
        monitor.stop()