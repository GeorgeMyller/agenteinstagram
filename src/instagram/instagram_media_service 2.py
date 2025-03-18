from typing import List, Dict, Tuple, Optional
from .base_instagram_service import BaseInstagramService
from .exceptions import InstagramError, MediaError, ValidationError

class InstagramMediaService(BaseInstagramService):
    """Service for managing media uploads and validation for Instagram."""

    MEDIA_CONFIG = {
        'image': {
            'aspect_ratio': {
                'min': 4.0/5.0,  # Instagram minimum (4:5)
                'max': 1.91      # Instagram maximum (1.91:1)
            },
            'resolution': {
                'min': 320,
                'max': 1440
            },
            'size_limit_mb': 8,
            'formats': ['jpg', 'jpeg', 'png']
        },
        'video': {
            'aspect_ratio': {
                'min': 4.0/5.0,
                'max': 1.91
            },
            'resolution': {
                'min': 500,
                'recommended': 1080
            },
            'duration': {
                'min': 3,
                'max': 90
            },
            'formats': ['mp4'],
            'codecs': {
                'video': ['h264'],
                'audio': ['aac']
            }
        }
    }

    async def publish_photo(self, image_path: str, caption: str) -> Tuple[bool, str, Optional[str]]:
        """Publica uma única foto no Instagram"""
        try:
            # Criar container
            container_id = await self._create_media_container(image_path, caption)
            if not container_id:
                raise MediaError("Falha ao criar container de mídia")

            # Publicar
            result = await self._publish_container(container_id)
            return True, "Publicado com sucesso", result.get("id")
        except InstagramError as e:
            return False, str(e), None

    async def publish_carousel(self, image_paths: List[str], caption: str) -> Tuple[bool, str, Optional[str]]:
        """Publica um carrossel de fotos no Instagram"""
        try:
            # Criar containers para cada imagem
            containers = []
            for image in image_paths:
                container = await self._create_media_container(image)
                if not container:
                    raise MediaError(f"Falha ao criar container para {image}")
                containers.append(container)

            # Criar carrossel
            carousel_id = await self._create_carousel_container(containers, caption)
            if not carousel_id:
                raise MediaError("Falha ao criar container do carrossel")

            # Publicar
            result = await self._publish_container(carousel_id)
            return True, "Carrossel publicado com sucesso", result.get("id")
        except InstagramError as e:
            return False, str(e), None

    async def _create_media_container(self, image_path: str, caption: str = None) -> Optional[str]:
        """Cria um container para uma única mídia"""
        try:
            response = await self._make_request(
                'POST',
                f'{self.ig_user_id}/media',
                data={
                    'image_url': image_path,
                    'caption': caption,
                    'access_token': self.access_token
                }
            )
            return response.get('id')
        except Exception as e:
            raise MediaError(f"Erro ao criar container: {str(e)}")

    async def _create_carousel_container(self, media_ids: List[str], caption: str) -> Optional[str]:
        """Cria um container para carrossel"""
        try:
            response = await self._make_request(
                'POST',
                f'{self.ig_user_id}/media',
                data={
                    'media_type': 'CAROUSEL',
                    'children': media_ids,
                    'caption': caption,
                    'access_token': self.access_token
                }
            )
            return response.get('id')
        except Exception as e:
            raise MediaError(f"Erro ao criar container do carrossel: {str(e)}")

    async def _publish_container(self, container_id: str) -> Dict:
        """Publica um container de mídia"""
        try:
            return await self._make_request(
                'POST',
                f'{self.ig_user_id}/media_publish',
                data={
                    'creation_id': container_id,
                    'access_token': self.access_token
                }
            )
        except Exception as e:
            raise MediaError(f"Erro ao publicar: {str(e)}")

    def validate_media(self, file_path: str) -> Tuple[bool, str]:
        """Validates if a media file meets Instagram requirements"""
        try:
            import os
            from PIL import Image
            import magic

            mime = magic.Magic(mime=True)
            file_type = mime.from_file(file_path)

            if file_type.startswith('image/'):
                return self._validate_image(file_path)
            elif file_type.startswith('video/'):
                return self._validate_video(file_path)
            else:
                return False, f"Unsupported media type: {file_type}"

        except Exception as e:
            return False, f"Validation error: {str(e)}"

    def _validate_image(self, image_path: str) -> Tuple[bool, str]:
        """Validates image dimensions, format, and size"""
        try:
            with Image.open(image_path) as img:
                width, height = img.size
                aspect_ratio = width / height

                # Check dimensions
                if width < self.MEDIA_CONFIG['image']['resolution']['min'] or \
                   height < self.MEDIA_CONFIG['image']['resolution']['min']:
                    return False, f"Image too small (minimum {self.MEDIA_CONFIG['image']['resolution']['min']}px)"

                # Check aspect ratio
                if aspect_ratio < self.MEDIA_CONFIG['image']['aspect_ratio']['min'] or \
                   aspect_ratio > self.MEDIA_CONFIG['image']['aspect_ratio']['max']:
                    return False, f"Invalid aspect ratio: {aspect_ratio:.2f}"

                # Check file size
                file_size = os.path.getsize(image_path) / (1024 * 1024)  # Convert to MB
                if file_size > self.MEDIA_CONFIG['image']['size_limit_mb']:
                    return False, f"File too large: {file_size:.1f}MB"

                return True, "Image validation successful"

        except Exception as e:
            return False, f"Image validation error: {str(e)}"

    def _validate_video(self, video_path: str) -> Tuple[bool, str]:
        """Validates video format, duration, and specifications"""
        try:
            import cv2
            from moviepy.editor import VideoFileClip

            # Check basic file validity
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return False, "Could not open video file"

            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()

            # Check resolution
            if width < self.MEDIA_CONFIG['video']['resolution']['min'] or \
               height < self.MEDIA_CONFIG['video']['resolution']['min']:
                return False, f"Video resolution too low (minimum {self.MEDIA_CONFIG['video']['resolution']['min']}px)"

            # Check duration and other specs using moviepy
            with VideoFileClip(video_path) as clip:
                duration = clip.duration
                if duration < self.MEDIA_CONFIG['video']['duration']['min']:
                    return False, f"Video too short (minimum {self.MEDIA_CONFIG['video']['duration']['min']}s)"
                if duration > self.MEDIA_CONFIG['video']['duration']['max']:
                    return False, f"Video too long (maximum {self.MEDIA_CONFIG['video']['duration']['max']}s)"

            return True, "Video validation successful"

        except Exception as e:
            return False, f"Video validation error: {str(e)}"