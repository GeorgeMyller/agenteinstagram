from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import os
import logging
import base64
from datetime import datetime
import uuid
from io import BytesIO
from moviepy.editor import VideoFileClip

from .paths import Paths

logger = logging.getLogger(__name__)

@dataclass
class VideoMetadata:
    width: int
    height: int
    duration: float
    format: str
    codec: str
    bitrate: Optional[int] = None
    fps: Optional[float] = None

@dataclass
class DecodedVideo:
    file_path: Path
    metadata: VideoMetadata
    size_bytes: int
    processing_time: float
    mime_type: str
    created_at: datetime = field(default_factory=datetime.now)

class VideoDecodeSaver:
    """
    Handles decoding and saving base64-encoded videos
    
    Methods:
        process: Decode and save a base64 video
        decode: Convert base64 string to video data
        save_video: Save video data to a file
        get_metadata: Extract metadata from video file
    """
    
    @classmethod
    def process(
        cls,
        base64_data: Optional[str],
        prefix: str = "video_",
        output_dir: Optional[str] = None
    ) -> str:
        """
        Process a base64-encoded video string
        
        Args:
            base64_data: Base64-encoded video data
            prefix: Filename prefix
            output_dir: Directory to save to (default: temp_videos)
            
        Returns:
            File path of saved video
        """
        start_time = datetime.now()
        
        try:
            if not base64_data:
                raise ValueError("No video data provided")
            
            # Decode video
            video_data, mime_type = cls.decode(base64_data)
            
            # Determine output path
            if output_dir:
                output_path = Path(output_dir)
            else:
                output_path = Paths.temp_videos_dir
            
            # Ensure directory exists
            output_path.mkdir(exist_ok=True, parents=True)
            
            # Generate unique filename with proper extension
            extension = cls._get_extension_from_mime(mime_type)
            filename = f"{prefix}{uuid.uuid4()}.{extension}"
            file_path = output_path / filename
            
            # Save the video
            cls.save_video(video_data, file_path)
            
            # Get video metadata using moviepy
            with VideoFileClip(str(file_path)) as clip:
                metadata = VideoMetadata(
                    width=clip.size[0],
                    height=clip.size[1],
                    duration=clip.duration,
                    format=extension,
                    codec="h264",  # Assuming h264 as it's standard for web videos
                    fps=clip.fps
                )
            
            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds()
            
            result = DecodedVideo(
                file_path=file_path,
                metadata=metadata,
                size_bytes=file_path.stat().st_size,
                processing_time=processing_time,
                mime_type=mime_type
            )
            
            logger.debug(
                f"Video processed: {file_path} ({metadata.width}x{metadata.height}, "
                f"{result.size_bytes/1024/1024:.1f}MB, {metadata.duration:.1f}s)"
            )
            
            return str(file_path)
            
        except Exception as e:
            logger.error(f"Failed to process video: {str(e)}")
            raise
    
    @staticmethod
    def decode(
        base64_data: str
    ) -> Tuple[BytesIO, str]:
        """
        Decode base64 video data
        
        Args:
            base64_data: Base64-encoded video data
            
        Returns:
            Tuple of (video_data, mime_type)
        """
        try:
            # Handle data URI format
            if "," in base64_data:
                header, encoded = base64_data.split(",", 1)
                mime_type = header.split(":")[1].split(";")[0] if ":" in header else "video/mp4"
            else:
                encoded = base64_data
                mime_type = "video/mp4"  # Default
            
            # Decode the video
            video_data = BytesIO(base64.b64decode(encoded))
            return video_data, mime_type
            
        except Exception as e:
            logger.error(f"Failed to decode video: {e}")
            raise ValueError(f"Invalid video data: {str(e)}")
    
    @staticmethod
    def save_video(
        video_data: BytesIO,
        file_path: Path
    ) -> None:
        """Save video data to a file"""
        try:
            with open(file_path, "wb") as f:
                f.write(video_data.getvalue())
        except Exception as e:
            logger.error(f"Failed to save video: {e}")
            raise
    
    @staticmethod
    def _get_extension_from_mime(mime_type: str) -> str:
        """Get file extension from MIME type"""
        mime_map = {
            "video/mp4": "mp4",
            "video/mpeg": "mp4",
            "video/quicktime": "mov",
            "video/x-msvideo": "avi",
            "video/webm": "webm"
        }
        return mime_map.get(mime_type, "mp4")