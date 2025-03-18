import os
import logging
import tempfile
from typing import Dict, Optional, Union, Tuple
from pathlib import Path
from moviepy.editor import VideoFileClip, ColorClip, CompositeVideoClip
from ..utils.config import Config
from ..utils.resource_manager import ResourceManager

logger = logging.getLogger(__name__)

class InstagramVideoProcessor:
    """Handles video processing and validation for Instagram requirements"""

    VIDEO_CONFIG = {
        'aspect_ratio': {
            'min': 4.0/5.0,  # Instagram minimum (4:5)
            'max': 1.91      # Instagram maximum (1.91:1)
        },
        'min_duration': 3,
        'max_duration': 60,
        'min_width': 500,
        'recommended_width': 1080,
        'max_size_mb': 100
    }

    REELS_CONFIG = {
        'aspect_ratio': {
            'min': 9.0/16.0,  # Vertical video (9:16)
            'max': 9.0/16.0
        },
        'min_duration': 3,
        'max_duration': 90,
        'min_width': 500,
        'recommended_width': 1080,
        'recommended_height': 1920,
        'max_size_mb': 100
    }

    @staticmethod
    def validate_video(video_path: str, target_type: str = 'video') -> Tuple[bool, str]:
        """Validates video meets Instagram requirements"""
        try:
            config = InstagramVideoProcessor.REELS_CONFIG if target_type == 'reels' else InstagramVideoProcessor.VIDEO_CONFIG
            
            # Check file size
            file_size = os.path.getsize(video_path) / (1024 * 1024)  # Convert to MB
            if file_size > config['max_size_mb']:
                return False, f"Video too large ({file_size:.1f}MB). Maximum: {config['max_size_mb']}MB"

            with VideoFileClip(video_path) as clip:
                # Check duration
                if clip.duration < config['min_duration']:
                    return False, f"Video too short ({clip.duration:.1f}s). Minimum: {config['min_duration']}s"
                if clip.duration > config['max_duration']:
                    return False, f"Video too long ({clip.duration:.1f}s). Maximum: {config['max_duration']}s"

                # Check dimensions
                width, height = clip.size
                if width < config['min_width']:
                    return False, f"Video width too small ({width}px). Minimum: {config['min_width']}px"

                # Check aspect ratio
                aspect_ratio = width / height
                if aspect_ratio < config['aspect_ratio']['min'] or aspect_ratio > config['aspect_ratio']['max']:
                    return False, f"Invalid aspect ratio ({aspect_ratio:.2f}). Must be between {config['aspect_ratio']['min']:.2f} and {config['aspect_ratio']['max']:.2f}"

            return True, "Video validation successful"

        except Exception as e:
            logger.error(f"Error validating video: {str(e)}")
            return False, f"Error validating video: {str(e)}"

    @staticmethod
    def optimize_video(video_path: str, target_type: str = 'video') -> Optional[str]:
        """Optimizes video for Instagram upload"""
        try:
            config = InstagramVideoProcessor.REELS_CONFIG if target_type == 'reels' else InstagramVideoProcessor.VIDEO_CONFIG

            # Create temp directory
            temp_dir = os.path.join(os.path.dirname(video_path), 'temp_videos')
            os.makedirs(temp_dir, exist_ok=True)

            # Generate output path
            output_path = os.path.join(
                temp_dir,
                f"optimized_{os.path.basename(video_path)}"
            )

            with VideoFileClip(video_path) as clip:
                width, height = clip.size
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

                # Resize video
                resized = clip.resize(width=target_width, height=target_height)

                # Write optimized video
                resized.write_videofile(
                    output_path,
                    codec='libx264',
                    audio_codec='aac' if clip.audio else None,
                    bitrate='4000k',
                    threads=4,
                    preset='medium'
                )

                # Check if optimization helped
                if os.path.getsize(output_path) >= os.path.getsize(video_path):
                    logger.info("Optimized version is larger than original, using original")
                    return video_path

                return output_path

        except Exception as e:
            logger.error(f"Error optimizing video: {str(e)}")
            return None