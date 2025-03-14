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
import subprocess
import json

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
        
        # Verify ffmpeg installation
        self._check_ffmpeg()
        
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
            # Get video metadata
            info = self.get_video_info(video_path)
            
            # Check format
            if info["format"]["format_name"] not in self.allowed_formats:
                logger.error(
                    f"Invalid format: {info['format']['format_name']}"
                )
                return False
                
            # Check duration
            duration = float(info["format"]["duration"])
            if duration > self.max_duration:
                logger.error(
                    f"Video too long: {duration}s > {self.max_duration}s"
                )
                return False
                
            # Check dimensions
            stream = self._get_video_stream(info)
            width = int(stream["width"])
            height = int(stream["height"])
            
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
                
            # Check codecs
            if stream["codec_name"] != "h264":
                logger.error(
                    f"Invalid video codec: {stream['codec_name']}"
                )
                return False
                
            audio = self._get_audio_stream(info)
            if audio and audio["codec_name"] != "aac":
                logger.error(
                    f"Invalid audio codec: {audio['codec_name']}"
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
        # Build ffmpeg command
        cmd = [
            "ffmpeg",
            "-i", input_path,
            "-c:v", "libx264",  # H.264 video codec
            "-preset", "medium",
            "-b:v", self.target_bitrate,
        ]
        
        # Add output size if specified
        if "target_width" in kwargs and "target_height" in kwargs:
            cmd.extend([
                "-vf",
                f"scale={kwargs['target_width']}:{kwargs['target_height']}"
            ])
            
        # Handle audio
        if kwargs.get("remove_audio"):
            cmd.extend(["-an"])
        else:
            cmd.extend([
                "-c:a", "aac",  # AAC audio codec
                "-b:a", "128k"
            ])
            
        # Add quality
        if "quality" in kwargs:
            cmd.extend(["-crf", str(kwargs["quality"])])
            
        # Output format
        cmd.extend([
            "-f", target_format,
            "-y",  # Overwrite output
            output_path
        ])
        
        # Run conversion
        try:
            subprocess.run(
                cmd,
                check=True,
                capture_output=True
            )
        except subprocess.CalledProcessError as e:
            logger.error(
                f"Video conversion failed: {e.stderr.decode()}"
            )
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
            cmd = [
                "ffmpeg",
                "-ss", str(time),
                "-i", video_path,
                "-vframes", "1",
                "-q:v", "2",
                "-y",
                output_path
            ]
            
            subprocess.run(
                cmd,
                check=True,
                capture_output=True
            )
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(
                f"Thumbnail generation failed: {e.stderr.decode()}"
            )
            return False
            
    def get_video_info(self, video_path: str) -> Dict[str, Any]:
        """
        Get detailed video metadata using ffprobe.
        
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
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            video_path
        ]
        
        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True
            )
            return json.loads(result.stdout)
            
        except subprocess.CalledProcessError as e:
            logger.error(
                f"Failed to get video info: {e.stderr.decode()}"
            )
            raise
            
    def _check_ffmpeg(self):
        """Verify ffmpeg and ffprobe are installed."""
        try:
            subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                check=True
            )
            subprocess.run(
                ["ffprobe", "-version"],
                capture_output=True,
                check=True
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError(
                "ffmpeg and ffprobe are required but not installed"
            )
            
    def _get_video_stream(self, info: Dict) -> Dict:
        """Get primary video stream info."""
        for stream in info["streams"]:
            if stream["codec_type"] == "video":
                return stream
        raise ValueError("No video stream found")
        
    def _get_audio_stream(self, info: Dict) -> Optional[Dict]:
        """Get primary audio stream info if present."""
        for stream in info["streams"]:
            if stream["codec_type"] == "audio":
                return stream
        return None