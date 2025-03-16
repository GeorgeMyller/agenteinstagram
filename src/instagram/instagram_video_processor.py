import os
from moviepy.editor import VideoFileClip, clips_array, concatenate_videoclips
from moviepy.video.fx.resize import resize
from moviepy.video.tools.cuts import find_video_period
from moviepy.config import change_settings
import tempfile
from typing import Dict, Any
import logging
from moviepy.editor import VideoFileClip, CompositeVideoClip, ColorClip
from PIL import Image
from datetime import datetime
import subprocess
import re
import json
from pathlib import Path
from typing import Optional, Tuple
import moviepy.editor as mp
from moviepy.video.fx.all import resize
from src.utils.paths import Paths
# Defina um diretório temporário para o moviepy usar (opcional, mas recomendado)
# change_settings({"TEMP_DIR": "/caminho/para/seu/diretorio/temporario"}) # Linux/macOS
# change_settings({"TEMP_DIR": "C:\\caminho\\para\\seu\\diretorio\\temporario"}) # Windows
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# Apply patch for Pillow 10+ compatibility
def _apply_pillow_patch():
    """Apply compatibility patch for Pillow 10+ with MoviePy"""
    if not hasattr(Image, 'ANTIALIAS'):
        if hasattr(Image, 'LANCZOS'):
            Image.ANTIALIAS = Image.LANCZOS
        elif hasattr(Image.Resampling) and hasattr(Image.Resampling, 'LANCZOS'):
            Image.ANTIALIAS = Image.Resampling.LANCZOS
# Apply the patch immediately
_apply_pillow_patch()
class VideoProcessor:
    """Handles video validation and optimization for Instagram."""

    REELS_CONFIG = {
        'aspect_ratio': '9:16',     # Default aspect ratio for Reels
        'min_duration': 3,          # Minimum duration in seconds
        'max_duration': 90,         # Maximum duration in seconds
        'recommended_duration': 30,  # Recommended duration
        'min_width': 500,           # Minimum width in pixels
        'recommended_width': 1080,  # Recommended width
        'recommended_height': 1920, # Recommended height
        'video_formats': ['mp4'],   # Supported formats
        'video_codecs': ['h264'],   # Recommended video codecs
        'audio_codecs': ['aac'],    # Recommended audio codecs
        'max_size_mb': 100         # Maximum file size in MB
    }

    VIDEO_CONFIG = {
        'aspect_ratio': {
            'min': 4.0/5.0,  # Instagram minimum (4:5)
            'max': 1.91      # Instagram maximum (1.91:1)
        },
        'min_duration': 3,
        'max_duration': 60,
        'min_width': 500,
        'recommended_width': 1080,
        'video_formats': ['mp4'],
        'video_codecs': ['h264'],
        'audio_codecs': ['aac'],
        'max_size_mb': 100
    }

    async def optimize_for_instagram(self, video_path: str, target_type: str = 'video') -> Optional[str]:
        """
        Optimizes video for Instagram upload based on target type (video/reels).
        Returns path to optimized video or None if optimization fails.
        """
        try:
            import ffmpeg
            from moviepy.editor import VideoFileClip
            import os
            import tempfile

            config = self.REELS_CONFIG if target_type == 'reels' else self.VIDEO_CONFIG
            
            # Create temp directory if needed
            temp_dir = os.path.join(os.path.dirname(video_path), 'temp_videos')
            os.makedirs(temp_dir, exist_ok=True)
            
            # Generate output path
            output_path = os.path.join(
                temp_dir,
                f"optimized_{os.path.basename(video_path)}"
            )

            # Get video info
            probe = ffmpeg.probe(video_path)
            video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
            width = int(video_info['width'])
            height = int(video_info['height'])
            
            # Calculate target dimensions
            target_width = config['recommended_width']
            if target_type == 'reels':
                target_height = config['recommended_height']
            else:
                # Maintain aspect ratio for regular videos
                target_height = int(target_width * (height / width))
                # Ensure aspect ratio constraints
                aspect_ratio = target_width / target_height
                if aspect_ratio < config['aspect_ratio']['min']:
                    target_height = int(target_width / config['aspect_ratio']['min'])
                elif aspect_ratio > config['aspect_ratio']['max']:
                    target_height = int(target_width / config['aspect_ratio']['max'])

            # Prepare FFmpeg stream
            stream = ffmpeg.input(video_path)
            
            # Apply video optimization
            stream = ffmpeg.filter(stream, 'scale', target_width, target_height)
            
            # Set video codec and quality
            stream = ffmpeg.output(
                stream,
                output_path,
                acodec='aac',
                vcodec='libx264',
                preset='medium',
                crf=23,  # Balanced quality/size
                video_bitrate='4000k',
                audio_bitrate='128k'
            )

            # Run FFmpeg
            ffmpeg.run(stream, overwrite_output=True, capture_stdout=True, capture_stderr=True)

            # Verify output
            if not os.path.exists(output_path):
                logger.error("Failed to create optimized video")
                return None

            # Check if optimization actually helped
            if os.path.getsize(output_path) >= os.path.getsize(video_path):
                logger.info("Optimized version is larger than original, using original")
                return video_path

            return output_path

        except Exception as e:
            logger.error(f"Error optimizing video: {str(e)}")
            return None

    @staticmethod
    def validate_video(video_path: str) -> Tuple[bool, str]:
        """
        Validates video file against Instagram requirements.
        Returns (is_valid, message).
        """
        try:
            import ffmpeg
            from moviepy.editor import VideoFileClip
            
            # Check if file exists
            if not os.path.exists(video_path):
                return False, "Video file not found"
                
            # Check file size
            file_size = os.path.getsize(video_path) / (1024 * 1024)  # Convert to MB
            if file_size > VideoProcessor.VIDEO_CONFIG['max_size_mb']:
                return False, f"Video too large ({file_size:.1f}MB). Maximum allowed: {VideoProcessor.VIDEO_CONFIG['max_size_mb']}MB"

            # Get video info using ffprobe
            probe = ffmpeg.probe(video_path)
            video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
            
            # Check dimensions
            width = int(video_info['width'])
            height = int(video_info['height'])
            if width < VideoProcessor.VIDEO_CONFIG['min_width']:
                return False, f"Video width too small ({width}px). Minimum: {VideoProcessor.VIDEO_CONFIG['min_width']}px"

            # Check aspect ratio
            aspect_ratio = width / height
            if aspect_ratio < VideoProcessor.VIDEO_CONFIG['aspect_ratio']['min']:
                return False, f"Aspect ratio too narrow: {aspect_ratio:.2f}"
            if aspect_ratio > VideoProcessor.VIDEO_CONFIG['aspect_ratio']['max']:
                return False, f"Aspect ratio too wide: {aspect_ratio:.2f}"

            # Check duration using moviepy
            with VideoFileClip(video_path) as clip:
                duration = clip.duration
                if duration < VideoProcessor.VIDEO_CONFIG['min_duration']:
                    return False, f"Video too short ({duration:.1f}s). Minimum: {VideoProcessor.VIDEO_CONFIG['min_duration']}s"
                if duration > VideoProcessor.VIDEO_CONFIG['max_duration']:
                    return False, f"Video too long ({duration:.1f}s). Maximum: {VideoProcessor.VIDEO_CONFIG['max_duration']}s"

            # Check codec
            vcodec = video_info.get('codec_name', '').lower()
            if vcodec not in VideoProcessor.VIDEO_CONFIG['video_codecs']:
                return False, f"Unsupported video codec: {vcodec}"

            # Check audio if present
            audio_stream = next((s for s in probe['streams'] if s['codec_type'] == 'audio'), None)
            if audio_stream:
                acodec = audio_stream.get('codec_name', '').lower()
                if acodec not in VideoProcessor.VIDEO_CONFIG['audio_codecs']:
                    return False, f"Unsupported audio codec: {acodec}"

            return True, "Video validation successful"

        except Exception as e:
            return False, f"Validation error: {str(e)}"