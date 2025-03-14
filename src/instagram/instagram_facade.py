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
        """
        Initialize the Instagram facade with necessary credentials.
        
        Args:
            access_token: Instagram API access token (optional, will load from env if None)
            ig_user_id: Instagram user ID (optional, will load from env if None)
            skip_token_validation: Whether to skip token validation (default: False)
        """
        # Use env variables if parameters not provided
        if access_token is None:
            access_token = os.getenv('INSTAGRAM_API_KEY')
        if ig_user_id is None:
            ig_user_id = os.getenv('INSTAGRAM_ACCOUNT_ID')
            
        # Initialize services with the option to skip token validation
        self.service = BaseInstagramService(access_token, ig_user_id)
        self.post_service = InstagramPostService(access_token, ig_user_id, skip_token_validation)
        self.reels_service = ReelsPublisher(access_token, ig_user_id, skip_token_validation)
        self.carousel_service = InstagramCarouselService(access_token, ig_user_id, skip_token_validation)
        
        self.normalizer = CarouselNormalizer()
        self.describer = CarouselDescriber()
        self.crew = InstagramPostCrew()
        
    def post_single_image(self, image_path: str, caption: str = None, **kwargs) -> Dict[str, Any]:
        """
        Posts a single image to Instagram.
        
        This method serves as an adapter for the old API structure.
        It delegates to post_single_photo method.
        
        Args:
            image_path: Path to the image file
            caption: Caption for the post
            **kwargs: Additional parameters
            
        Returns:
            Dict with operation result
        """
        logger.info(f"Posting single image via adapter method: {image_path}")
        return self.post_single_photo(image_path, caption)
        
    def post_video(self, video_path: str, caption: str = None, **kwargs) -> Dict[str, Any]:
        """
        Posts a video to Instagram.
        
        This method serves as an adapter for the old API structure.
        It delegates to post_reels method.
        
        Args:
            video_path: Path to the video file
            caption: Caption for the post
            **kwargs: Additional parameters
            
        Returns:
            Dict with operation result
        """
        logger.info(f"Posting video via adapter method: {video_path}")
        # Extract relevant kwargs
        hashtags = kwargs.get('hashtags', [])
        share_to_feed = kwargs.get('share_to_feed', True)
        
        return self.post_reels(video_path, caption, hashtags, share_to_feed)
    
    def post_carousel(self, image_paths: List[str], caption: str = None) -> Dict[str, Any]:
        """Posts a photo carousel on Instagram with enhanced validation"""
        try:
            logger.info(f"Starting carousel post with {len(image_paths)} images")
            valid_images = []
            
            # Input validation
            if len(image_paths) < 2:
                return {'status': 'error', 'message': 'Minimum of 2 images required for carousel'}
            if len(image_paths) > 10:
                return {'status': 'error', 'message': 'Maximum of 10 images allowed for carousel'}
            for image_path in image_paths:
                is_valid, message = self.validate_media(image_path)
                if not is_valid:
                    logger.warning(f"Invalid image {image_path}: {message}")
                    continue
                valid_images.append(image_path)
            
            if len(valid_images) < 2:
                return {
                    'status': 'error',
                    'message': f'Insufficient number of valid images ({len(valid_images)}). Minimum: 2'
                }
            
            normalized_paths = self.normalizer.normalize_carousel_images(valid_images)
            
            # Upload to Imgur in parallel for better performance
            async def upload_image(image_path: str) -> Optional[str]:
                if urlparse(image_path).scheme in ('http', 'https'):
                    return image_path
                try:
                    with open(image_path, 'rb') as img_file:
                        import aiohttp
                        async with aiohttp.ClientSession() as session:
                            async with session.post(
                                'https://api.imgur.com/3/upload',
                                headers={'Authorization': f"Client-ID {os.getenv('IMGUR_CLIENT_ID', '546c25a59c58ad7')}"},
                                data={'image': img_file.read()}
                            ) as response:
                                data = await response.json()
                                if data.get('success'):
                                    return data['data']['link']
                except Exception as e:
                    logger.error(f"Error uploading image {image_path}: {str(e)}")
                return None
            async def upload_images(paths: List[str]) -> List[str]:
                tasks = [upload_image(path) for path in paths]
                uploaded_urls = await asyncio.gather(*tasks)
                return [url for url in uploaded_urls if url]
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            media_urls = loop.run_until_complete(upload_images(normalized_paths))
            loop.close()

            if not media_urls or len(media_urls) < 2:
                return {
                    'status': 'error',
                    'message': f'Failed to upload images. Valid URLs: {len(media_urls)}'
                }

            result = self.carousel_service.post_carousel(media_urls, caption)
            logger.info(f"Carousel post result: {result}")
            return result
        except Exception as e:
            logger.error(f"Error posting carousel: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'message': str(e)
            }

    def post_single_photo(self, image_path: str, caption: str = None) -> Dict[str, Any]:
        """Posts a single photo on Instagram"""
        try:
            logger.info(f"Starting single photo post: {image_path}")
            
            # Validate and optimize image first
            validator = InstagramImageValidator()
            is_valid, issues = validator.validate_single_photo(image_path)
            if not is_valid:
                logger.error(f"Image validation failed: {issues}")
                return {'status': 'error', 'message': f'Invalid image: {issues}'}
                
            optimized_path = validator.optimize_for_instagram(image_path)
            if not optimized_path:
                return {'status': 'error', 'message': 'Failed to optimize image'}
            # Upload image to Imgur if necessary
            if urlparse(optimized_path).scheme in ('http', 'https'):
                image_url = optimized_path
            else:
                try:
                    import requests
                    with open(optimized_path, 'rb') as img_file:
                        response = requests.post(
                            'https://api.imgur.com/3/upload',
                            headers={'Authorization': 'Client-ID ' + os.getenv('IMGUR_CLIENT_ID', '546c25a59c58ad7')},
                            files={'image': img_file}
                        )
                        data = response.json()
                        if not data.get('success'):
                            logger.error(f"Failed to upload image: {data}")
                            return {'status': 'error', 'message': 'Failed to upload image'}
                        image_url = data['data']['link']
                except Exception as e:
                    logger.error(f"Error uploading image: {str(e)}")
                    return {'status': 'error', 'message': f'Error uploading image: {str(e)}'}

            container_id = self.post_service.create_media_container(image_url, caption)
            if not container_id:
                return {'status': 'error', 'message': 'Failed to create media container'}

            status = self.post_service.wait_for_container_status(container_id)
            if status != 'FINISHED':
                return {'status': 'error', 'message': f'Container not ready. Status: {status}'}

            post_id = self.post_service.publish_media(container_id)
            if post_id:
                return {
                    'status': 'success',
                    'id': post_id
                }
            else:
                return {'status': 'error', 'message': 'Failed to publish image'}
        except Exception as e:
            logger.error(f"Error posting photo: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    def post_reels(self, video_path: str, caption: str = None, hashtags: List[str] = None, 
                   share_to_feed: bool = True, optimized_video: str = None) -> Dict[str, Any]:
        """Posts a reel on Instagram"""
        try:
            logger.info(f"Starting reels post: {video_path}")
            
            if not optimized_video:
                optimized_video = VideoProcessor.force_optimize_for_instagram(video_path, post_type='reels')
                if not optimized_video:
                    return {'status': 'error', 'message': 'Video optimization failed'}
            
            result = self.reels_service.publish_reels(
                video_path=optimized_video,
                caption=caption,
                hashtags=hashtags,
                share_to_feed=share_to_feed
            )
            
            if result and 'id' in result:
                return {
                    'status': 'success', 
                    'id': result['id'],
                    'permalink': result.get('permalink', None)
                }
            else:
                return {'status': 'error', 'message': 'Failed to publish reels'}
        except Exception as e:
            logger.error(f"Error posting reels: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    def validate_media(self, file_path: str) -> Tuple[bool, str]:
        """Validates if a media file is suitable for posting"""
        try:
            _, ext = os.path.splitext(file_path)
            ext = ext.lower()
            if ext in ['.jpg', '.jpeg', '.png']:
                try:
                    validator = InstagramImageValidator()
                    is_valid, message = validator.validate_image(file_path)
                    if not is_valid:
                        return False, message
                    return True, "Valid image file"
                except Exception as e:
                    return False, str(e)
            elif ext in ['.mp4', '.mov']:
                try:
                    is_valid, message = VideoProcessor.validate_video(file_path)
                    if not is_valid:
                        return False, message
                    return True, "Valid video file"
                except Exception as e:
                    return False, str(e)
            else:
                return False, f"Unsupported file format: {ext}"
        except Exception as e:
            return False, str(e)
                    
    def get_account_status(self) -> Dict[str, Any]:
        """
        Returns the current account status (rate limits, usage, etc)
        """
        return self.service.get_app_usage_info()