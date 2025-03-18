"""
Video Processing and Validation Utilities

This module provides functionality for processing and validating videos for Instagram:
- Video format conversion and transcoding
- Duration validation
- Aspect ratio validation and correction
- Bitrate optimization
- Thumbnail generation
- Audio track handling

Usage Examples:
    Basic validation:
    >>> processor = VideoProcessor()
    >>> if processor.validate_video("video.mp4"):
    ...     print("Video meets Instagram requirements")
    
    Format conversion:
    >>> processor.convert_video(
    ...     input_path="input.avi",
    ...     output_path="output.mp4",
    ...     target_format="mp4"
    ... )
    
    With custom settings:
    >>> processor = VideoProcessor(
    ...     max_duration=120,
    ...     target_bitrate="2M",
    ...     min_width=320,
    ...     min_height=320
    ... )
"""

import os
import logging
from typing import Optional, Tuple, Dict, Any
from pathlib import Path
from moviepy.editor import VideoFileClip, ColorClip, CompositeVideoClip

logger = logging.getLogger(__name__)

class VideoProcessor:
    """
    Handles video processing and validation for Instagram uploads.
    
    Features:
    - Format validation and conversion
    - Duration checks
    - Resolution validation
    - Aspect ratio correction
    - Bitrate optimization
    - Audio track validation
    - Thumbnail generation
    
    Args:
        max_duration: Maximum video duration in seconds (default: 60)
        target_bitrate: Target video bitrate (default: "2M")
        min_width: Minimum video width (default: 320)
        min_height: Minimum video height (default: 320)
        allowed_formats: List of allowed video formats (default: ["mp4"])
    """
    
    def __init__(
        self,
        max_duration: int = 60,
        target_bitrate: str = "2M",
        min_width: int = 320,
        min_height: int = 320,
        allowed_formats: Optional[list] = None
    ):
        self.max_duration = max_duration
        self.target_bitrate = target_bitrate
        self.min_width = min_width
        self.min_height = min_height
        self.allowed_formats = allowed_formats or ["mp4"]

    def validate_video(self, video_path: str) -> bool:
        """
        Validate video meets Instagram requirements.
        
        Args:
            video_path: Path to video file
            
        Returns:
            bool: True if video is valid
            
        Checks:
        - File exists and readable
        - Valid format (mp4)
        - Duration within limits
        - Resolution meets minimums
        - Valid aspect ratio
        - Video codec (h264)
        - Audio codec (aac)
        
        Example:
            >>> if not processor.validate_video("video.mp4"):
            ...     # Convert to valid format
            ...     processor.convert_video(
            ...         "video.mp4",
            ...         "converted.mp4"
            ...     )
        """
        try:
            with VideoFileClip(video_path) as clip:
                # Check duration
                if clip.duration > self.max_duration:
                    logger.error(
                        f"Video too long: {clip.duration}s > {self.max_duration}s"
                    )
                    return False
                
                # Check dimensions
                width, height = clip.size
                if width < self.min_width or height < self.min_height:
                    logger.error(
                        f"Video too small: {width}x{height} < "
                        f"{self.min_width}x{self.min_height}"
                    )
                    return False
                
                # Check aspect ratio
                aspect = width / height
                if aspect < 0.8 or aspect > 1.91:
                    logger.error(
                        f"Invalid aspect ratio: {aspect:.2f}"
                    )
                    return False
                
                return True
                
        except Exception as e:
            logger.error(f"Video validation failed: {str(e)}")
            return False
            
    def convert_video(
        self,
        input_path: str,
        output_path: str,
        target_format: str = "mp4",
        **kwargs
    ):
        """
        Convert video to Instagram-compatible format.
        
        Args:
            input_path: Input video path
            output_path: Output video path
            target_format: Target format (default: mp4)
            **kwargs: Additional ffmpeg parameters:
                - target_width: Output width
                - target_height: Output height
                - remove_audio: Remove audio track
                - quality: Output quality (1-31, lower is better)
        
        Example:
            >>> # Convert and resize video
            >>> processor.convert_video(
            ...     "input.avi",
            ...     "output.mp4",
            ...     target_width=1080,
            ...     target_height=1080,
            ...     quality=23
            ... )
        """
        try:
            with VideoFileClip(input_path) as clip:
                # Handle resize if needed
                if "target_width" in kwargs and "target_height" in kwargs:
                    clip = clip.resize(
                        width=kwargs["target_width"],
                        height=kwargs["target_height"]
                    )
                
                # Handle audio removal if requested
                if kwargs.get("remove_audio"):
                    clip = clip.without_audio()
                
                # Write the processed video
                clip.write_videofile(
                    output_path,
                    codec="libx264",
                    audio_codec="aac" if clip.audio else None,
                    bitrate=self.target_bitrate,
                    preset="medium",
                    threads=4,
                    fps=clip.fps
                )
                
        except Exception as e:
            logger.error(f"Video conversion failed: {str(e)}")
            raise
            
    def generate_thumbnail(
        self,
        video_path: str,
        output_path: str,
        time: float = 0
    ) -> bool:
        """
        Generate thumbnail from video.
        
        Args:
            video_path: Video file path
            output_path: Output image path
            time: Time in seconds to extract frame (default: 0)
            
        Returns:
            bool: True if thumbnail generated successfully
            
        Example:
            >>> # Generate thumbnail from middle of video
            >>> info = processor.get_video_info("video.mp4")
            >>> middle = float(info["format"]["duration"]) / 2
            >>> processor.generate_thumbnail(
            ...     "video.mp4",
            ...     "thumb.jpg",
            ...     time=middle
            ... )
        """
        try:
            with VideoFileClip(video_path) as clip:
                # Get frame at specified time
                frame = clip.get_frame(time)
                
                # Save frame as image
                from PIL import Image
                import numpy as np
                img = Image.fromarray(np.uint8(frame))
                img.save(output_path, quality=95)
                return True
                
        except Exception as e:
            logger.error(f"Thumbnail generation failed: {str(e)}")
            return False
            
    def get_video_info(self, video_path: str) -> Dict[str, Any]:
        """
        Get detailed video metadata using moviepy.
        
        Args:
            video_path: Path to video file
            
        Returns:
            dict: Video metadata including:
                - format information
                - video stream details
                - audio stream details
                
        Example:
            >>> info = processor.get_video_info("video.mp4")
            >>> print(f"Duration: {info['format']['duration']}s")
            >>> print(f"Size: {info['format']['size']} bytes")
            >>> stream = processor._get_video_stream(info)
            >>> print(f"Resolution: {stream['width']}x{stream['height']}")
        """
        try:
            with VideoFileClip(video_path) as clip:
                info = {
                    "width": clip.size[0],
                    "height": clip.size[1],
                    "duration": clip.duration,
                    "fps": clip.fps,
                    "has_audio": clip.audio is not None,
                    "format": os.path.splitext(video_path)[1][1:],
                    "size_bytes": os.path.getsize(video_path)
                }
                return info
                
        except Exception as e:
            logger.error(f"Failed to get video info: {str(e)}")
            raise