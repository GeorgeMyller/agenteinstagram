from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
import os
import logging
from pathlib import Path
import aiohttp
import asyncio
from datetime import datetime

from .base_instagram_service import BaseInstagramService
from .image_validator import InstagramImageValidator
from .exceptions import InstagramError, MediaValidationError
from ..utils.config import Config

logger = logging.getLogger(__name__)

@dataclass
class MediaMetadata:
    file_path: Path
    media_type: str
    size_bytes: int
    dimensions: Tuple[int, int]
    format: str
    creation_time: datetime

@dataclass
class PublishResult:
    success: bool
    media_id: Optional[str] = None
    error_message: Optional[str] = None
    permalink: Optional[str] = None

class InstagramMediaService(BaseInstagramService):
    def __init__(self, access_token: str = None, account_id: str = None, skip_validation: bool = False):
        # Update Config with credentials if provided
        if access_token and account_id:
            config = Config.get_instance()
            config.INSTAGRAM_ACCESS_TOKEN = access_token
            config.INSTAGRAM_ACCOUNT_ID = account_id
            
        # Now call super().__init__() which will use the updated Config
        super().__init__()
        self.validator = InstagramImageValidator()
        self.skip_validation = skip_validation

    def validate_media(self, file_path: str) -> Tuple[bool, str]:
        """Validate media file for Instagram requirements"""
        try:
            if self.skip_validation:
                return True, "Validation skipped"

            path = Path(file_path)
            if not path.exists():
                return False, f"File not found: {file_path}"

            metadata = self._get_media_metadata(path)
            
            # Check file size
            max_size = self.config.get_api_config().max_file_size_mb * 1024 * 1024
            if metadata.size_bytes > max_size:
                return False, f"File size exceeds {max_size/1024/1024}MB limit"

            # Validate based on media type
            if metadata.media_type == "image":
                return self.validator.validate_image(
                    file_path,
                    metadata.dimensions,
                    metadata.format
                )
            elif metadata.media_type == "video":
                return self.validator.validate_video(file_path)
            else:
                return False, f"Unsupported media type: {metadata.media_type}"

        except Exception as e:
            logger.error(f"Media validation error: {e}")
            return False, str(e)

    def _get_media_metadata(self, file_path: Path) -> MediaMetadata:
        """Extract metadata from media file"""
        from PIL import Image
        import magic

        mime = magic.Magic(mime=True)
        mime_type = mime.from_file(str(file_path))
        
        media_type = mime_type.split('/')[0]
        size_bytes = file_path.stat().st_size
        
        # Get dimensions and format for images
        dimensions = (0, 0)
        format_name = ""
        if media_type == "image":
            with Image.open(file_path) as img:
                dimensions = img.size
                format_name = img.format

        return MediaMetadata(
            file_path=file_path,
            media_type=media_type,
            size_bytes=size_bytes,
            dimensions=dimensions,
            format=format_name,
            creation_time=datetime.fromtimestamp(file_path.stat().st_ctime)
        )

    async def publish_photo(
        self,
        image_path: str,
        caption: Optional[str] = None
    ) -> PublishResult:
        """Publish a photo to Instagram"""
        try:
            # Validate image
            is_valid, message = self.validate_media(image_path)
            if not is_valid:
                return PublishResult(
                    success=False,
                    error_message=f"Invalid image: {message}"
                )

            # Create container for media
            container = await self._create_media_container(
                image_path,
                media_type="IMAGE",
                caption=caption
            )

            if not container.get('id'):
                return PublishResult(
                    success=False,
                    error_message="Failed to create media container"
                )

            # Publish the container
            result = await self._publish_container(container['id'])
            
            if result.get('id'):
                return PublishResult(
                    success=True,
                    media_id=result['id'],
                    permalink=result.get('permalink')
                )
            else:
                return PublishResult(
                    success=False,
                    error_message="Failed to publish media"
                )

        except Exception as e:
            logger.error(f"Error publishing photo: {e}")
            return PublishResult(success=False, error_message=str(e))

    async def publish_carousel(
        self,
        image_paths: List[str],
        caption: Optional[str] = None
    ) -> PublishResult:
        """Publish a carousel to Instagram"""
        try:
            # Validate all images
            for path in image_paths:
                is_valid, message = self.validate_media(path)
                if not is_valid:
                    return PublishResult(
                        success=False,
                        error_message=f"Invalid image {path}: {message}"
                    )

            # Create container for carousel
            container = await self._create_carousel_container(
                image_paths,
                caption=caption
            )

            if not container.get('id'):
                return PublishResult(
                    success=False,
                    error_message="Failed to create carousel container"
                )

            # Publish the container
            result = await self._publish_container(container['id'])
            
            if result.get('id'):
                return PublishResult(
                    success=True,
                    media_id=result['id'],
                    permalink=result.get('permalink')
                )
            else:
                return PublishResult(
                    success=False,
                    error_message="Failed to publish carousel"
                )

        except Exception as e:
            logger.error(f"Error publishing carousel: {e}")
            return PublishResult(success=False, error_message=str(e))

    async def _create_media_container(
        self,
        media_path: str,
        media_type: str,
        caption: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a container for media upload"""
        params = {
            'media_type': media_type,
            'image_url': await self._upload_to_cdn(media_path)
        }
        
        if caption:
            params['caption'] = caption

        endpoint = f'/{self.api_version}/{self.account_id}/media'
        return await self._make_request('POST', endpoint, params)

    async def _create_carousel_container(
        self,
        media_paths: List[str],
        caption: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a container for carousel upload"""
        # Upload all media to CDN first
        children = []
        for path in media_paths:
            upload_url = await self._upload_to_cdn(path)
            children.append({
                'media_type': 'IMAGE',
                'image_url': upload_url
            })

        params = {
            'media_type': 'CAROUSEL',
            'children': children
        }
        
        if caption:
            params['caption'] = caption

        endpoint = f'/{self.api_version}/{self.account_id}/media'
        return await self._make_request('POST', endpoint, params)

    async def _publish_container(self, container_id: str) -> Dict[str, Any]:
        """Publish a created media container"""
        endpoint = f'/{self.api_version}/{self.account_id}/media_publish'
        params = {'creation_id': container_id}
        return await self._make_request('POST', endpoint, params)

    async def _upload_to_cdn(self, file_path: str) -> str:
        """Upload media to Facebook's CDN"""
        # Implementation of CDN upload
        # This is a placeholder - actual implementation would depend on your CDN setup
        return f"https://your-cdn.com/media/{Path(file_path).name}"