from typing import List, Optional, Tuple, Dict, Any, Union
import os
import asyncio
import logging
from dotenv import load_dotenv
from urllib.parse import urlparse
import uuid
from datetime import datetime
from dataclasses import dataclass, field
from pathlib import Path

from ..utils.config import Config
from ..utils.monitor import ApiMonitor
from ..utils.rate_limiter import RateLimiter
from .base_instagram_service import BaseInstagramService
from .instagram_post_service import InstagramPostService
from .carousel_normalizer import CarouselNormalizer
from .describe_carousel_tool import CarouselDescriber
from .crew_post_instagram import InstagramPostCrew
from .exceptions import InstagramError, RateLimitError, ContentPolicyViolation
from .instagram_carousel_service import InstagramCarouselService
from .instagram_reels_publisher import ReelsPublisher
from .video_processor import VideoProcessor
from .image_validator import InstagramImageValidator
from .instagram_media_service import InstagramMediaService

load_dotenv()
logger = logging.getLogger(__name__)

@dataclass
class PostContainer:
    id: str
    status: str
    created_at: datetime
    type: str
    media_url: Optional[str] = None
    caption: Optional[str] = None
    error: Optional[str] = None

@dataclass
class QueueStats:
    pending: int = 0
    processing: int = 0
    completed: int = 0
    failed: int = 0

class InstagramFacade:
    """
    Facade for Instagram publishing operations.
    Provides a simplified interface for posting different types of media.
    """
    
    def __init__(self, access_token: Optional[str] = None, ig_user_id: Optional[str] = None):
        self.config = Config.get_instance()
        self.post_service = InstagramPostService(access_token, ig_user_id)
        self.carousel_service = InstagramCarouselService(access_token, ig_user_id)
        self.media_service = InstagramMediaService(access_token, ig_user_id)
        
    async def post_image(self, image_path: Union[str, Path], caption: str, **kwargs) -> Dict[str, Any]:
        """Post a single image to Instagram"""
        try:
            logger.info(f"Posting image: {image_path}")
            result = await self.post_service.post_image(str(image_path), caption, **kwargs)
            return {
                "success": True,
                "media_id": result.get("id"),
                "permalink": result.get("permalink")
            }
        except Exception as e:
            logger.error(f"Error posting image: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def post_carousel(self, image_paths: List[Union[str, Path]], caption: str, **kwargs) -> Dict[str, Any]:
        """Post multiple images as a carousel"""
        try:
            logger.info(f"Posting carousel with {len(image_paths)} images")
            result = await self.carousel_service.post_carousel(
                [str(path) for path in image_paths],
                caption,
                **kwargs
            )
            return {
                "success": True,
                "media_id": result.get("id"),
                "permalink": result.get("permalink")
            }
        except Exception as e:
            logger.error(f"Error posting carousel: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def post_video(self, video_path: Union[str, Path], caption: str, is_reel: bool = False, **kwargs) -> Dict[str, Any]:
        """Post a video or reel to Instagram"""
        try:
            logger.info(f"Posting {'reel' if is_reel else 'video'}: {video_path}")
            result = await self.media_service.post_video(
                str(video_path),
                caption,
                is_reel=is_reel,
                **kwargs
            )
            return {
                "success": True,
                "media_id": result.get("id"),
                "permalink": result.get("permalink")
            }
        except Exception as e:
            logger.error(f"Error posting video: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }