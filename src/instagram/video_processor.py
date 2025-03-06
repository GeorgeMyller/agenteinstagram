import os
import logging
import subprocess
import json
import time
import shutil
from typing import Tuple, Dict, Any, Optional
from moviepy.editor import VideoFileClip
import tempfile

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VideoProcessor:
    """
    Class responsible for processing and validating videos for Instagram Reels.
    """
    
    # Instagram Reels requirements
    MIN_DURATION_SECONDS = 3
    MAX_DURATION_SECONDS = 90
    RECOMMENDED_ASPECT_RATIO = 9/16  # Vertical video (portrait)
    RECOMMENDED_WIDTH = 1080
    RECOMMENDED_HEIGHT = 1920
    MAX_FILE_SIZE_MB = 100
    
    # Supported formats
    SUPPORTED_FORMATS = ['mp4', 'mov']
    
    @staticmethod
    def get_video_info(video_path: str) -> Dict[str, Any]:
        """
        Get video information using moviepy instead of ffprobe.
        
        Args:
            video_path: Path to the video file
            
        Returns:
            Dictionary with video metadata
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        try:
            # Use moviepy instead of ffprobe
            with VideoFileClip(video_path) as clip:
                width = int(clip.size[0])
                height = int(clip.size[1])
                duration = float(clip.duration)
                
                # Get file size
                file_size_bytes = os.path.getsize(video_path)
                file_size_mb = file_size_bytes / (1024 * 1024)
                
                # Get format/container from file extension
                _, ext = os.path.splitext(video_path)
                format_name = ext.lower().strip('.')
                
                return {
                    'width': width,
                    'height': height,
                    'duration': duration,
                    'file_size_mb': file_size_mb,
                    'format': format_name,
                    'aspect_ratio': width / height if height else 0
                }
        except Exception as e:
            logger.error(f"Error analyzing video: {str(e)}")
            raise

    @classmethod
    def validate_video(cls, video_path: str) -> Tuple[bool, str]:
        """
        Validate if a video meets Instagram Reels requirements.
        
        Args:
            video_path: Path to the video file
            
        Returns:
            Tuple of (is_valid, message)
        """
        try:
            video_info = cls.get_video_info(video_path)
            
            # Check file format
            _, ext = os.path.splitext(video_path)
            format_name = ext.lower().strip('.')
            format_valid = format_name in cls.SUPPORTED_FORMATS
            
            if not format_valid:
                return False, f"Formato de vídeo não suportado. Use: {', '.join(cls.SUPPORTED_FORMATS)}"
            
            # Check duration
            duration = video_info['duration']
            if duration < cls.MIN_DURATION_SECONDS:
                return False, f"Duração do vídeo muito curta: {duration:.1f}s. Mínimo: {cls.MIN_DURATION_SECONDS}s"
                
            if duration > cls.MAX_DURATION_SECONDS:
                return False, f"Duração do vídeo muito longa: {duration:.1f}s. Máximo: {cls.MAX_DURATION_SECONDS}s"
            
            # Check file size
            if video_info['file_size_mb'] > cls.MAX_FILE_SIZE_MB:
                return False, f"Tamanho do arquivo muito grande: {video_info['file_size_mb']:.1f}MB. Máximo: {cls.MAX_FILE_SIZE_MB}MB"
            
            # All checks passed
            return True, "Vídeo válido para Instagram Reels"
            
        except Exception as e:
            logger.error(f"Error validating video: {str(e)}")
            return False, f"Erro ao validar vídeo: {str(e)}"

    @classmethod
    def process_video_for_reels(cls, input_path: str, output_path: Optional[str] = None) -> str:
        """
        Process video to make it compatible with Instagram Reels using moviepy.
        
        Args:
            input_path: Path to the input video file
            output_path: Path to save the processed video (if None, a temp file is created)
            
        Returns:
            Path to the processed video file
        """
        if not output_path:
            # Create temporary output path
            temp_dir = os.path.dirname(input_path)
            filename = f"processed_{int(time.time())}_{os.path.basename(input_path)}"
            output_path = os.path.join(temp_dir, filename)
        
        try:
            video_info = cls.get_video_info(input_path)
            
            # Check if processing is needed
            if (video_info['width'] == cls.RECOMMENDED_WIDTH and 
                video_info['height'] == cls.RECOMMENDED_HEIGHT and
                any(fmt in video_info['format'] for fmt in cls.SUPPORTED_FORMATS)):
                # Video already meets requirements, just copy
                shutil.copy2(input_path, output_path)
                return output_path
            
            # Process video with moviepy
            with VideoFileClip(input_path) as clip:
                # Resize to Instagram Reels format
                target_aspect_ratio = cls.RECOMMENDED_ASPECT_RATIO
                current_aspect_ratio = clip.size[0] / clip.size[1]
                
                if current_aspect_ratio > target_aspect_ratio:
                    # Video too wide, crop sides
                    new_width = int(clip.size[1] * target_aspect_ratio)
                    x_center = clip.size[0] / 2
                    clip = clip.crop(x1=x_center - new_width / 2, 
                                     x2=x_center + new_width / 2)
                elif current_aspect_ratio < target_aspect_ratio:
                    # Video too tall, crop top and bottom
                    new_height = int(clip.size[0] / target_aspect_ratio)
                    y_center = clip.size[1] / 2
                    clip = clip.crop(y1=y_center - new_height / 2, 
                                     y2=y_center + new_height / 2)
                
                # Resize to recommended dimensions
                clip = clip.resize(width=cls.RECOMMENDED_WIDTH, height=cls.RECOMMENDED_HEIGHT)
                
                # Write to file with recommended codecs
                clip.write_videofile(
                    output_path,
                    codec="libx264",
                    audio_codec="aac" if clip.audio else None,
                    bitrate="5000k",
                    preset="medium",
                    threads=4,
                    verbose=False
                )
            
            logger.info(f"Video processed successfully: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error processing video: {str(e)}")
            raise

    @staticmethod
    def clean_temp_directory(directory: str, max_age_hours: int = 24) -> None:
        """
        Clean temporary video files older than max_age_hours.
        
        Args:
            directory: Directory to clean
            max_age_hours: Maximum age in hours for files to keep
        """
        if not os.path.exists(directory):
            return
        
        try:
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600
            
            for filename in os.listdir(directory):
                if filename.startswith('temp-') or filename.startswith('processed_'):
                    file_path = os.path.join(directory, filename)
                    
                    # Check if file is old enough to delete
                    if os.path.isfile(file_path):
                        file_age = current_time - os.path.getmtime(file_path)
                        if file_age > max_age_seconds:
                            os.remove(file_path)
                            logger.info(f"Removed old temporary file: {file_path}")
                            
        except Exception as e:
            logger.error(f"Error cleaning temporary directory: {str(e)}")
