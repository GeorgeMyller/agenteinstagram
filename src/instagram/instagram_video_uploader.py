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

import os
import time
import logging
import requests
from typing import Dict, Optional, Any
from pathlib import Path
from .exceptions import (
    InstagramError,
    RateLimitError,
    ContentPolicyViolation
)
from ..utils.config import Config

logger = logging.getLogger(__name__)

class InstagramVideoUploader:
    """Handles video uploads to Instagram with chunked upload support"""
    
    CHUNK_SIZE = 5 * 1024 * 1024  # 5MB chunks
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # seconds
    
    def __init__(self):
        self.config = Config.get_instance()
        self.api_version = "v12.0"
        self.base_url = f"https://graph.facebook.com/{self.api_version}"
        
    def upload_video(self, video_path: str, caption: str, is_reel: bool = False) -> Dict[str, Any]:
        """
        Upload a video to Instagram
        
        Args:
            video_path: Path to the video file
            caption: Caption for the video
            is_reel: Whether to post as a reel
            
        Returns:
            Dict containing upload result or error details
        """
        try:
            # Start video upload session
            session = self._start_upload_session(video_path, is_reel)
            if not session or "video_id" not in session:
                raise InstagramError("Failed to start video upload session")
            
            video_id = session["video_id"]
            
            # Upload video chunks
            if not self._upload_chunks(video_path, video_id):
                raise InstagramError("Failed to upload video chunks")
            
            # Complete the upload
            return self._complete_upload(video_id, caption, is_reel)
            
        except requests.exceptions.RequestException as e:
            if "rate limit" in str(e).lower():
                raise RateLimitError("Instagram API rate limit exceeded")
            raise InstagramError(f"Video upload failed: {str(e)}")
            
    def _start_upload_session(self, video_path: str, is_reel: bool) -> Optional[Dict]:
        """Initialize a chunked upload session"""
        try:
            file_size = os.path.getsize(video_path)
            
            params = {
                "access_token": self.config.INSTAGRAM_ACCESS_TOKEN,
                "media_type": "REELS" if is_reel else "VIDEO",
                "media_category": "REELS" if is_reel else "VIDEO",
                "file_size": file_size
            }
            
            url = f"{self.base_url}/{self.config.INSTAGRAM_ACCOUNT_ID}/media"
            
            response = self._make_request("POST", url, params=params)
            return response
            
        except Exception as e:
            logger.error(f"Error starting upload session: {e}")
            return None
            
    def _upload_chunks(self, video_path: str, video_id: str) -> bool:
        """Upload video in chunks"""
        try:
            with open(video_path, 'rb') as video_file:
                start_offset = 0
                chunk_number = 0
                
                while True:
                    chunk = video_file.read(self.CHUNK_SIZE)
                    if not chunk:
                        break
                        
                    # Upload this chunk
                    if not self._upload_chunk(chunk, video_id, start_offset, chunk_number):
                        return False
                        
                    start_offset += len(chunk)
                    chunk_number += 1
                    
            return True
            
        except Exception as e:
            logger.error(f"Error uploading video chunks: {e}")
            return False
            
    def _upload_chunk(self, chunk: bytes, video_id: str, offset: int, chunk_number: int) -> bool:
        """Upload a single video chunk"""
        for attempt in range(self.MAX_RETRIES):
            try:
                url = f"{self.base_url}/{video_id}"
                
                files = {
                    "video_file": (f"chunk{chunk_number}", chunk, "application/octet-stream")
                }
                
                params = {
                    "access_token": self.config.INSTAGRAM_ACCESS_TOKEN,
                    "upload_phase": "transfer",
                    "start_offset": offset
                }
                
                response = requests.post(url, files=files, params=params)
                response.raise_for_status()
                
                return True
                
            except Exception as e:
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY)
                    continue
                logger.error(f"Failed to upload chunk {chunk_number}: {e}")
                return False
                
    def _complete_upload(self, video_id: str, caption: str, is_reel: bool) -> Dict[str, Any]:
        """Complete the video upload and create the media container"""
        try:
            url = f"{self.base_url}/{video_id}"
            
            params = {
                "access_token": self.config.INSTAGRAM_ACCESS_TOKEN,
                "caption": caption,
                "upload_phase": "finish"
            }
            
            if is_reel:
                params["media_type"] = "REELS"
                params["share_to_feed"] = "true"
            
            response = self._make_request("POST", url, params=params)
            
            if "id" not in response:
                raise InstagramError("Failed to complete video upload")
                
            return {
                "status": "success",
                "media_id": response["id"],
                "type": "reel" if is_reel else "video"
            }
            
        except Exception as e:
            logger.error(f"Error completing upload: {e}")
            raise InstagramError(f"Failed to complete video upload: {str(e)}")
            
    def _make_request(self, method: str, url: str, **kwargs) -> Dict:
        """Make an API request with retries and error handling"""
        for attempt in range(self.MAX_RETRIES):
            try:
                response = requests.request(method, url, **kwargs)
                response.raise_for_status()
                
                return response.json()
                
            except requests.exceptions.RequestException as e:
                if "rate limit" in str(e).lower():
                    raise RateLimitError("Instagram API rate limit exceeded")
                    
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY)
                    continue
                    
                raise InstagramError(f"API request failed: {str(e)}")
                
        raise InstagramError("Max retries exceeded")