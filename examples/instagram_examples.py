"""
Instagram Service Examples

Demonstrates common usage patterns for Instagram services.
"""

import os
import logging
from typing import List
from pathlib import Path

from src.instagram.instagram_post_service import InstagramPostService
from src.instagram.instagram_carousel_service import InstagramCarouselService
from src.instagram.instagram_reels_publisher import ReelsPublisher
from src.instagram.image_validator import InstagramImageValidator
from src.utils.monitor import ApiMonitor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def post_single_image(image_path: str, caption: str) -> bool:
    """
    Post a single image to Instagram
    
    Args:
        image_path: Path to image file
        caption: Image caption
        
    Returns:
        bool: True if successful
    """
    # Initialize services
    validator = InstagramImageValidator()
    post_service = InstagramPostService()
    
    try:
        # Validate image
        validation = validator.process_single_photo(image_path)
        if validation['status'] == 'error':
            logger.error(f"Image validation failed: {validation['message']}")
            return False
        
        # Create container
        container_id = post_service.create_media_container(image_path, caption)
        if not container_id:
            logger.error("Failed to create media container")
            return False
        
        # Wait for container to be ready
        status = post_service.wait_for_container_status(container_id)
        if status != 'FINISHED':
            logger.error(f"Container failed with status: {status}")
            return False
        
        # Publish post
        post_id = post_service.publish_media(container_id)
        if not post_id:
            logger.error("Failed to publish post")
            return False
        
        # Get permalink
        permalink = post_service.get_post_permalink(post_id)
        logger.info(f"Post published successfully: {permalink}")
        return True
        
    except Exception as e:
        logger.error(f"Error posting image: {e}")
        return False

def post_carousel(image_paths: List[str], caption: str) -> bool:
    """
    Post multiple images as a carousel
    
    Args:
        image_paths: List of image file paths
        caption: Carousel caption
        
    Returns:
        bool: True if successful
    """
    # Initialize services
    validator = InstagramImageValidator()
    carousel_service = InstagramCarouselService()
    
    try:
        # Validate all images
        validation = validator.process_carousel(image_paths)
        if validation['status'] == 'error':
            logger.error(f"Carousel validation failed: {validation['message']}")
            return False
        
        # Create carousel container
        container_id = carousel_service.create_carousel_container(
            image_paths,
            caption
        )
        if not container_id:
            logger.error("Failed to create carousel container")
            return False
        
        # Wait for container
        status = carousel_service.wait_for_container_status(container_id)
        if status != 'FINISHED':
            logger.error(f"Carousel failed with status: {status}")
            return False
        
        # Publish carousel
        post_id = carousel_service.publish_carousel(container_id)
        if not post_id:
            logger.error("Failed to publish carousel")
            return False
        
        # Get permalink
        permalink = carousel_service.get_post_permalink(post_id)
        logger.info(f"Carousel published successfully: {permalink}")
        return True
        
    except Exception as e:
        logger.error(f"Error posting carousel: {e}")
        return False

def post_reel(video_path: str, caption: str, share_to_feed: bool = True) -> bool:
    """
    Post a video as a Reel
    
    Args:
        video_path: Path to video file
        caption: Reel caption
        share_to_feed: Whether to share to main feed
        
    Returns:
        bool: True if successful
    """
    # Initialize services
    reels_publisher = ReelsPublisher()
    
    try:
        # Validate video
        validation = reels_publisher.validate_video(video_path)
        if not validation['valid']:
            logger.error(f"Video validation failed: {validation['issues']}")
            return False
        
        # Optimize video if needed
        if validation.get('needs_optimization'):
            optimized_path = reels_publisher.optimize_video(video_path)
            if not optimized_path:
                logger.error("Failed to optimize video")
                return False
            video_path = optimized_path
        
        # Create container
        container_id = reels_publisher.create_container(
            video_path,
            caption,
            share_to_feed
        )
        if not container_id:
            logger.error("Failed to create reel container")
            return False
        
        # Wait for container
        status = reels_publisher.wait_for_container_status(container_id)
        if status != 'FINISHED':
            logger.error(f"Reel failed with status: {status}")
            return False
        
        # Publish reel
        post_id = reels_publisher.publish_reel(container_id)
        if not post_id:
            logger.error("Failed to publish reel")
            return False
        
        # Get permalink
        permalink = reels_publisher.get_post_permalink(post_id)
        logger.info(f"Reel published successfully: {permalink}")
        return True
        
    except Exception as e:
        logger.error(f"Error posting reel: {e}")
        return False

def main():
    """Run example posts"""
    # Start monitoring
    monitor = ApiMonitor()
    monitor.start()
    
    try:
        # Example single image post
        image_path = "examples/images/sample.jpg"
        success = post_single_image(
            image_path,
            "Test single image post #test"
        )
        print(f"Single image post {'succeeded' if success else 'failed'}")
        
        # Example carousel post
        image_paths = [
            "examples/images/carousel1.jpg",
            "examples/images/carousel2.jpg",
            "examples/images/carousel3.jpg"
        ]
        success = post_carousel(
            image_paths,
            "Test carousel post #test"
        )
        print(f"Carousel post {'succeeded' if success else 'failed'}")
        
        # Example reel post
        video_path = "examples/videos/sample.mp4"
        success = post_reel(
            video_path,
            "Test reel post #test",
            share_to_feed=True
        )
        print(f"Reel post {'succeeded' if success else 'failed'}")
        
        # Print monitoring stats
        stats = monitor.get_stats()
        print("\nAPI Statistics:")
        print(f"Total calls: {stats['total_calls']}")
        print(f"Success rate: {stats['success_rate']:.1%}")
        print(f"Average duration: {stats.get('avg_duration', 0):.2f}s")
        
    finally:
        # Stop monitoring
        monitor.stop()

if __name__ == '__main__':
    main()