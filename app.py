"""
Instagram Publishing Application

Provides endpoints for queuing and managing Instagram posts.
Handles single images, carousels, and reels with proper rate limiting.
"""

import os
import logging
from typing import Dict, Any, List, Optional
from flask import Flask, request, jsonify
from datetime import datetime

from src.instagram.instagram_post_service import InstagramPostService
from src.instagram.instagram_carousel_service import InstagramCarouselService
from src.instagram.instagram_reels_publisher import ReelsPublisher
from src.instagram.image_validator import InstagramImageValidator
from src.utils.monitor import ApiMonitor
from src.utils.config import ConfigManager
from src.utils.error_handler import error_handler, init_error_handlers

app = Flask(__name__)
monitor = ApiMonitor()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize error handlers
init_error_handlers(app)

# Initialize configuration
config = ConfigManager()
# Load configuration from file if it exists
config_file_path = os.path.join(os.path.dirname(__file__), 'config.json')
if os.path.exists(config_file_path):
    config.load_file(config_file_path)
    logger.info(f"Loaded configuration from {config_file_path}")
# Also load from environment variables (these override file settings)
config.load_env()

# Initialize services
post_service = InstagramPostService()
carousel_service = InstagramCarouselService()
reels_publisher = ReelsPublisher()
image_validator = InstagramImageValidator()

@app.route('/health', methods=['GET'])
@error_handler
def health_check():
    """Health check endpoint"""
    # Check Instagram API credentials
    is_valid, missing = post_service.check_token_permissions()
    
    # Get API health metrics
    health = monitor.check_health()
    
    return jsonify({
        'status': 'healthy' if is_valid else 'degraded',
        'missing_permissions': missing,
        'api_health': health,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/post/image', methods=['POST'])
@error_handler
def queue_image_post():
    """Queue a single image post"""
    data = request.get_json()
    if not data:
        return jsonify({
            'status': 'error',
            'message': 'No data provided'
        }), 400
    
    image_path = data.get('image_path')
    caption = data.get('caption')
    
    if not image_path:
        return jsonify({
            'status': 'error',
            'message': 'image_path is required'
        }), 400
    
    # Validate image
    validation = image_validator.process_single_photo(image_path)
    if validation['status'] == 'error':
        return jsonify({
            'status': 'error',
            'message': validation['message']
        }), 400
    
    # Queue post
    container_id = post_service.create_media_container(image_path, caption)
    if not container_id:
        return jsonify({
            'status': 'error',
            'message': 'Failed to create media container'
        }), 500
    
    return jsonify({
        'status': 'success',
        'message': 'Post queued successfully',
        'container_id': container_id
    })

@app.route('/post/carousel', methods=['POST'])
@error_handler
def queue_carousel_post():
    """Queue a carousel post"""
    data = request.get_json()
    if not data:
        return jsonify({
            'status': 'error',
            'message': 'No data provided'
        }), 400
    
    image_paths = data.get('image_paths', [])
    caption = data.get('caption')
    
    if not image_paths:
        return jsonify({
            'status': 'error',
            'message': 'image_paths is required'
        }), 400
    
    # Validate images
    validation = image_validator.process_carousel(image_paths)
    if validation['status'] == 'error':
        return jsonify({
            'status': 'error',
            'message': validation['message'],
            'details': validation['images']
        }), 400
    
    # Queue carousel
    container_id = carousel_service.create_carousel_container(image_paths, caption)
    if not container_id:
        return jsonify({
            'status': 'error',
            'message': 'Failed to create carousel container'
        }), 500
    
    return jsonify({
        'status': 'success',
        'message': 'Carousel queued successfully',
        'container_id': container_id
    })

@app.route('/post/reel', methods=['POST'])
@error_handler
def queue_reel_post():
    """Queue a reel post"""
    data = request.get_json()
    if not data:
        return jsonify({
            'status': 'error',
            'message': 'No data provided'
        }), 400
    
    video_path = data.get('video_path')
    caption = data.get('caption')
    share_to_feed = data.get('share_to_feed', True)
    
    if not video_path:
        return jsonify({
            'status': 'error',
            'message': 'video_path is required'
        }), 400
    
    # Validate video
    validation = reels_publisher.validate_video(video_path)
    if not validation.get('valid'):
        return jsonify({
            'status': 'error',
            'message': 'Invalid video',
            'details': validation
        }), 400
    
    # Queue reel
    container_id = reels_publisher.create_container(
        video_path,
        caption,
        share_to_feed
    )
    if not container_id:
        return jsonify({
            'status': 'error',
            'message': 'Failed to create reel container'
        }), 500
    
    return jsonify({
        'status': 'success',
        'message': 'Reel queued successfully',
        'container_id': container_id
    })

@app.route('/post/status/<container_id>', methods=['GET'])
@error_handler
def check_post_status(container_id):
    """Check status of a queued post"""
    # Try each service type
    services = [post_service, carousel_service, reels_publisher]
    
    for service in services:
        try:
            status = service.wait_for_container_status(container_id)
            if status:
                return jsonify({
                    'status': 'success',
                    'container_status': status
                })
        except Exception:
            continue
    
    return jsonify({
        'status': 'error',
        'message': 'Container not found'
    }), 404

@app.route('/monitor/stats', methods=['GET'])
@error_handler
def get_monitor_stats():
    """Get API monitoring statistics"""
    stats = monitor.get_stats()
    return jsonify({
        'status': 'success',
        'stats': stats
    })

if __name__ == '__main__':
    # Start monitoring
    monitor.start()
    
    try:
        # Run Flask app
        port = int(os.environ.get('PORT', 5000))
        app.run(host='0.0.0.0', port=port)
    finally:
        # Stop monitoring
        monitor.stop()