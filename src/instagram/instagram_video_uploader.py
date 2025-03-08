import os
import logging
from typing import Optional, Tuple
import moviepy.editor as mp
from imgurpython import ImgurClient
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class VideoUploader:
    """
    Class for handling video uploads and validation for Instagram Reels.
    """

    REELS_CONFIG = {
        'aspect_ratio': '9:16',     # Proporção de aspecto padrão para Reels (vertical)
        'min_duration': 3,          # Duração mínima em segundos
        'max_duration': 90,         # Duração máxima em segundos
        'recommended_duration': 30,  # Duração recomendada pela Meta
        'min_width': 500,           # Largura mínima em pixels
        'recommended_width': 1080,  # Largura recomendada em pixels
        'recommended_height': 1920, # Altura recomendada em pixels
        'video_formats': ['mp4'],   # Formatos suportados
        'video_codecs': ['h264'],   # Codecs de vídeo recomendados
        'audio_codecs': ['aac'],    # Codecs de áudio recomendados
    }

    def __init__(self):
        """Initialize with Imgur client."""
        load_dotenv()
        self.imgur_client = ImgurClient(
            os.getenv('IMGUR_CLIENT_ID'),
            os.getenv('IMGUR_CLIENT_SECRET')
        )

    def validate_video(self, video_path: str) -> Tuple[bool, str]:
        """
        Validates video against Instagram Reels requirements.
        
        Returns:
            Tuple[bool, str]: (is_valid, message)
        """
        try:
            if not os.path.exists(video_path):
                return False, "Video file not found"

            if not video_path.lower().endswith(('.mp4', '.mov', '.avi')):
                return False, "Unsupported video format"

            video = mp.VideoFileClip(video_path)
            
            # Check duration
            duration = video.duration
            if duration < self.REELS_CONFIG['min_duration']:
                return False, f"Video too short ({duration}s). Minimum duration is {self.REELS_CONFIG['min_duration']}s"
            if duration > self.REELS_CONFIG['max_duration']:
                return False, f"Video too long ({duration}s). Maximum duration is {self.REELS_CONFIG['max_duration']}s"

            # Check dimensions and aspect ratio
            width, height = video.size
            if width < self.REELS_CONFIG['min_width']:
                return False, f"Video width too small ({width}px). Minimum width is {self.REELS_CONFIG['min_width']}px"

            aspect_ratio = height / width
            if abs(aspect_ratio - 16/9) > 0.1:  # Allow some tolerance
                return False, f"Incorrect aspect ratio ({width}x{height}). Should be close to 9:16"

            # Close the video to free resources
            video.close()
            
            return True, "Video meets all requirements"

        except Exception as e:
            logger.error(f"Error validating video: {str(e)}")
            return False, f"Error validating video: {str(e)}"

    def upload_video(self, video_path: str) -> Optional[dict]:
        """
        Uploads video to Imgur.
        
        Returns:
            Optional[dict]: Upload response with URL if successful
        """
        try:
            # First validate the video
            is_valid, message = self.validate_video(video_path)
            if not is_valid:
                logger.error(f"Video validation failed: {message}")
                return None

            logger.info(f"Uploading video to Imgur: {video_path}")
            response = self.imgur_client.upload_from_path(video_path)
            
            if not response or 'link' not in response:
                logger.error("Failed to get upload URL from Imgur")
                return None

            logger.info(f"Video uploaded successfully. URL: {response['link']}")
            return response

        except Exception as e:
            logger.error(f"Error uploading video: {str(e)}")
            return None

    def delete_video(self, delete_hash: str) -> bool:
        """
        Deletes a video from Imgur using its delete hash.
        
        Returns:
            bool: True if deletion was successful
        """
        try:
            if not delete_hash:
                return False

            logger.info(f"Deleting video with hash: {delete_hash}")
            return bool(self.imgur_client.delete_image(delete_hash))

        except Exception as e:
            logger.error(f"Error deleting video: {str(e)}")
            return False