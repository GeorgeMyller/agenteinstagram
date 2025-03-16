from typing import List, Optional, Tuple, Dict, Any
import os
import asyncio
import logging
from dotenv import load_dotenv
from urllib.parse import urlparse
from .base_instagram_service import BaseInstagramService
from .instagram_post_service import InstagramPostService
from .carousel_normalizer import CarouselNormalizer
from .describe_carousel_tool import CarouselDescriber
from .crew_post_instagram import InstagramPostCrew
from .exceptions import InstagramError
from .instagram_carousel_service import InstagramCarouselService
from .instagram_reels_publisher import ReelsPublisher
from .instagram_video_processor import VideoProcessor
from .image_validator import InstagramImageValidator

load_dotenv()

logger = logging.getLogger(__name__)


class InstagramFacade:
    """
    Facade to simplify interactions with the Instagram API.
    Encapsulates the complexity of different functionalities into a single interface.
    """
    
    def __init__(self, access_token: str = None, ig_user_id: str = None, skip_token_validation: bool = False):
        """Initialize the Instagram facade with necessary credentials."""
        # Use env variables if parameters not provided
        if access_token is None:
            access_token = os.getenv('INSTAGRAM_API_KEY')
        if ig_user_id is None:
            ig_user_id = os.getenv('INSTAGRAM_ACCOUNT_ID')
            
        # Initialize services
        self.media_service = InstagramMediaService(access_token, ig_user_id, skip_token_validation)
        self.post_service = InstagramPostService(access_token, ig_user_id, skip_token_validation)
        self.carousel_service = InstagramCarouselService(access_token, ig_user_id, skip_token_validation)
        self.reels_service = ReelsPublisher(access_token, ig_user_id, skip_token_validation)
        
        # Initialize utilities
        self.normalizer = CarouselNormalizer()
        self.describer = CarouselDescriber()
        self.validator = InstagramImageValidator()
        self.video_processor = VideoProcessor()

    async def post_single_image(self, image_path: str, caption: str = None, **kwargs) -> Dict[str, Any]:
        """Posts a single image to Instagram with validation and optimization."""
        try:
            # Validate image
            is_valid, validation_message = self.media_service.validate_media(image_path)
            if not is_valid:
                return {'status': 'error', 'message': validation_message}

            # Optimize image if needed
            optimized_path = self.validator.optimize_for_instagram(image_path)
            if not optimized_path:
                return {'status': 'error', 'message': 'Failed to optimize image'}

            # Upload and post
            result = await self.media_service.publish_photo(optimized_path, caption)
            if result[0]:  # Success
                return {'status': 'success', 'id': result[2]}
            else:
                return {'status': 'error', 'message': result[1]}

        except Exception as e:
            logger.error(f"Error posting single image: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    async def post_carousel(self, image_paths: List[str], caption: str = None) -> Dict[str, Any]:
        """Posts a carousel with validation and normalization of all images."""
        try:
            if len(image_paths) < 2:
                return {'status': 'error', 'message': 'Minimum 2 images required for carousel'}
            if len(image_paths) > 10:
                return {'status': 'error', 'message': 'Maximum 10 images allowed for carousel'}

            # Validate all images
            valid_images = []
            for path in image_paths:
                is_valid, message = self.media_service.validate_media(path)
                if not is_valid:
                    logger.warning(f"Skipping invalid image {path}: {message}")
                    continue
                valid_images.append(path)

            if len(valid_images) < 2:
                return {'status': 'error', 'message': f'Not enough valid images ({len(valid_images)}), minimum 2 required'}

            # Normalize all images for consistent display
            normalized_paths = self.normalizer.normalize_carousel_images(valid_images)
            
            # Post carousel
            result = await self.media_service.publish_carousel(normalized_paths, caption)
            if result[0]:  # Success
                return {'status': 'success', 'id': result[2]}
            else:
                return {'status': 'error', 'message': result[1]}

        except Exception as e:
            logger.error(f"Error posting carousel: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    async def post_video(self, video_path: str, caption: str = None, **kwargs) -> Dict[str, Any]:
        """Posts a video/reel to Instagram with validation and optimization."""
        try:
            # Validate video
            is_valid, validation_message = self.media_service.validate_media(video_path)
            if not is_valid:
                return {'status': 'error', 'message': validation_message}

            # Process video for Instagram requirements
            optimized_video = await self.video_processor.optimize_for_instagram(
                video_path,
                target_type='reels' if kwargs.get('is_reel') else 'video'
            )
            
            if not optimized_video:
                return {'status': 'error', 'message': 'Failed to optimize video'}

            # Handle hashtags
            hashtags = kwargs.get('hashtags', [])
            if hashtags:
                caption = f"{caption or ''}\n\n{' '.join(['#' + tag for tag in hashtags])}"

            # Post video
            share_to_feed = kwargs.get('share_to_feed', True)
            try:
                result = await self.reels_service.publish_video(
                    optimized_video,
                    caption=caption,
                    share_to_feed=share_to_feed
                )
                if result and 'id' in result:
                    return {
                        'status': 'success',
                        'id': result['id'],
                        'permalink': result.get('permalink')
                    }
                return {'status': 'error', 'message': 'Failed to publish video'}
            finally:
                # Clean up temporary optimized video
                if os.path.exists(optimized_video) and optimized_video != video_path:
                    os.unlink(optimized_video)

        except Exception as e:
            logger.error(f"Error posting video: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    def get_account_status(self) -> Dict[str, Any]:
        """Get current account status including rate limits and quotas."""
        try:
            status = {
                'rate_limits': {
                    'remaining_calls': self.post_service._max_requests_per_window - 
                                    len(self.post_service._rate_limit_cache),
                    'window_reset': self.post_service._get_rate_limit_reset_time()
                },
                'stats': self.post_service.stats,
                'pending_posts': len(self.post_service.pending_containers)
            }
            return {'status': 'success', 'data': status}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}