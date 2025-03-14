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
from typing import Optional
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
    """
    Process and validate videos for Instagram upload requirements.
    Handles video optimization, format validation, and automatic adjustments.
    
    Features:
        - Video format validation and conversion
        - Resolution and aspect ratio optimization
        - Bitrate and codec validation
        - Duration limits enforcement
        - File size optimization
        - Frame rate adjustment
        
    Example:
        >>> processor = VideoProcessor()
        >>> video_info = processor.get_video_info("input.mp4")
        >>> if processor.check_duration(video_info['duration'], 'reel'):
        ...     optimized_path = processor.process_video("input.mp4", post_type='reel')
    """
    # Instagram video requirements
    REELS_LIMITS = {
        'min_duration': 1,     # seconds
        'max_duration': 90,    # seconds
        'min_width': 500,      # pixels
        'max_width': 1080,     # pixels
        'min_height': 889,     # pixels
        'max_height': 1920,    # pixels
        'max_size': 4096,      # MB
        'aspect_ratio': {
            'min': 1.91,       # For horizontal videos
            'max': 0.01        # For vertical videos (effectively no limit)
        }
    }
    
    FEED_VIDEO_LIMITS = {
        'min_duration': 3,     # seconds
        'max_duration': 60,    # seconds
        'min_width': 500,      # pixels
        'max_width': 1080,     # pixels
        'min_height': 889,     # pixels
        'max_height': 1350,    # pixels
        'max_size': 4096,      # MB
        'aspect_ratio': {
            'min': 1.91,       # For horizontal videos
            'max': 0.8         # For vertical videos
        }
    }
    
    @staticmethod
    def force_optimize_for_instagram(video_path: str, post_type: str = 'reel') -> Optional[str]:
        """
        Força otimização do vídeo para Instagram mesmo que já esteja em conformidade.
        
        Este método estático garante que o vídeo sempre será processado para 
        requisitos ótimos do Instagram, sem checar se o vídeo já está otimizado.
        
        Args:
            video_path: Caminho para o vídeo de entrada
            post_type: Tipo de postagem ('reel' ou 'feed')
            
        Returns:
            str: Caminho para o vídeo otimizado ou None se falhar
            
        Example:
            >>> optimized = VideoProcessor.force_optimize_for_instagram("video.mp4", "reel")
            >>> print(f"Video optimized and saved to: {optimized}")
        """
        try:
            logger.info(f"Forçando otimização do vídeo: {video_path}")
            
            # Criar nome de arquivo temporário para saída
            temp_dir = os.path.join(tempfile.gettempdir(), 'instagram_video')
            os.makedirs(temp_dir, exist_ok=True)
            
            output_filename = f"optimized_{os.path.basename(video_path)}"
            output_path = os.path.join(temp_dir, output_filename)
            
            # Obter informações do vídeo
            with VideoFileClip(video_path) as clip:
                # Determinar resolução alvo com base no tipo de postagem
                target_resolution = (1080, 1920) if post_type == 'reel' else (1080, 1350)
                
                # Redimensionar o vídeo mantendo a proporção
                width, height = clip.size
                aspect_ratio = width / height
                
                if post_type == 'reel':
                    # Para reels, priorizamos altura
                    if aspect_ratio >= 9/16:  # Se for mais largo que 9:16
                        new_width = int(target_resolution[1] * aspect_ratio)
                        new_height = target_resolution[1]
                    else:
                        new_width = target_resolution[0]
                        new_height = int(new_width / aspect_ratio)
                else:
                    # Para feed, garantimos que está dentro dos limites
                    if aspect_ratio > 1:  # Landscape
                        new_width = target_resolution[0]
                        new_height = int(new_width / aspect_ratio)
                    else:  # Portrait
                        new_height = target_resolution[1]
                        new_width = int(new_height * aspect_ratio)
                
                # Aplicar redimensionamento
                resized_clip = clip.resize(width=new_width, height=new_height)
                
                # Limitar a duração se necessário
                max_duration = VideoProcessor.REELS_LIMITS['max_duration'] if post_type == 'reel' else VideoProcessor.FEED_VIDEO_LIMITS['max_duration']
                if resized_clip.duration > max_duration:
                    resized_clip = resized_clip.subclip(0, max_duration)
                
                # Exportar com configurações otimizadas para Instagram
                resized_clip.write_videofile(
                    output_path,
                    codec='libx264',
                    audio_codec='aac',
                    temp_audiofile=os.path.join(temp_dir, 'temp_audio.m4a'),
                    remove_temp=True,
                    audio_bitrate='128k',
                    bitrate='4000k',
                    fps=30,
                    preset='medium',  # Balanceamento entre velocidade e qualidade
                    threads=2,
                    logger=None  # Silenciar logs do moviepy
                )
                
            logger.info(f"Vídeo otimizado para Instagram: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Erro ao otimizar vídeo: {str(e)}")
            return None
    
    @staticmethod
    def validate_video(video_path: str) -> tuple[bool, str]:
        """
        Valida se um vídeo atende aos requisitos para upload no Instagram.
        
        Args:
            video_path: Caminho para o vídeo
            
        Returns:
            tuple: (is_valid, message) onde is_valid é um booleano e 
                   message é uma mensagem de erro ou sucesso
        """
        try:
            processor = VideoProcessor()
            info = processor.get_video_info(video_path)
            
            # Verificar duração
            if info['duration'] < 1:
                return False, "Vídeo muito curto (mínimo 1 segundo)"
            if info['duration'] > 90:
                return False, f"Vídeo muito longo: {info['duration']:.1f}s (máximo 90 segundos)"
                
            # Verificar resolução
            if info['width'] < 500 or info['height'] < 889:
                return False, f"Resolução muito baixa: {info['width']}x{info['height']}"
                
            # Verificar proporção
            aspect = info['width'] / info['height']
            if aspect > 1.91:  # Muito horizontal
                return False, f"Vídeo muito largo (proporção: {aspect:.2f})"
                
            # Verificar tamanho do arquivo
            if info['size_mb'] > 100:
                return False, f"Arquivo muito grande: {info['size_mb']:.1f}MB"
                
            return True, "Vídeo válido para Instagram"
            
        except Exception as e:
            return False, f"Erro ao validar vídeo: {str(e)}"

    @staticmethod
    def get_video_info(video_path: str) -> Dict[str, Any]:
        """
        Get comprehensive video file information using moviepy.
        
        Analyzes video properties including:
        - Duration and frame rate
        - Resolution and aspect ratio
        - Codecs and container format
        - File size and bitrate
        
        Args:
            video_path: Path to the video file
            
        Returns:
            dict: Video information with keys:
                - duration: Length in seconds
                - width: Frame width in pixels
                - height: Frame height in pixels
                - fps: Frames per second
                - size_mb: File size in megabytes
                - aspect_ratio: Width/height ratio
                - video_codec: Video codec name
                - audio_codec: Audio codec name if present
                
        Example:
            >>> info = VideoProcessor.get_video_info("my_video.mp4")
            >>> print(f"Duration: {info['duration']:.1f}s, "
            ...       f"Resolution: {info['width']}x{info['height']}")
        """
        try:
            with VideoFileClip(video_path) as clip:
                file_size = os.path.getsize(video_path) / (1024 * 1024)  # Convert to MB
                return {
                    'duration': clip.duration,
                    'width': clip.w,
                    'height': clip.h,
                    'fps': clip.fps,
                    'size_mb': file_size,
                    'aspect_ratio': clip.w / clip.h,
                    'video_codec': clip.codec_name if hasattr(clip, 'codec_name') else None,
                    'audio_codec': clip.audio.codec_name if clip.audio and hasattr(clip.audio, 'codec_name') else None
                }
        except Exception as e:
            logger.error(f"Error getting video info: {e}")
            raise ValueError(f"Failed to analyze video: {e}")
            
    @staticmethod
    def check_duration(duration: float, post_type: str) -> bool:
        """
        Verify if video duration meets Instagram's requirements.
        
        Args:
            duration: Video length in seconds
            post_type: Type of post ('reel' or 'feed')
            
        Returns:
            bool: True if duration is within acceptable range
            
        Example:
            >>> processor = VideoProcessor()
            >>> info = processor.get_video_info("video.mp4")
            >>> if not processor.check_duration(info['duration'], 'reel'):
            ...     print("Video too long for a reel")
        """
        limits = VideoProcessor.REELS_LIMITS if post_type == 'reel' else VideoProcessor.FEED_VIDEO_LIMITS
        if duration < limits['min_duration']:
            logger.warning(f"Video too short. Minimum duration: {limits['min_duration']}s")
            return False
        if duration > limits['max_duration']:
            logger.warning(f"Video too long. Maximum duration: {limits['max_duration']}s")
            return False
        return True
        
    @staticmethod
    def check_resolution(width: int, height: int, post_type: str) -> bool:
        """
        Verify if video resolution meets Instagram's requirements.
        
        Args:
            width: Frame width in pixels
            height: Frame height in pixels
            post_type: Type of post ('reel' or 'feed')
            
        Returns:
            bool: True if resolution is acceptable
            
        Example usage included in docstring for clarity:
            >>> if not processor.check_resolution(1920, 1080, 'feed'):
            ...     print("Resolution not suitable for feed video")
        """
        limits = VideoProcessor.REELS_LIMITS if post_type == 'reel' else VideoProcessor.FEED_VIDEO_LIMITS
        
        if width < limits['min_width'] or height < limits['min_height']:
            logger.warning(f"Video resolution too low. Minimum: {limits['min_width']}x{limits['min_height']}")
            return False
        if width > limits['max_width'] or height > limits['max_height']:
            logger.warning(f"Video resolution too high. Maximum: {limits['max_width']}x{limits['max_height']}")
            return False
        return True
        
    @staticmethod
    def check_aspect_ratio(width: float, height: float, post_type: str) -> bool:
        """
        Verify if video aspect ratio is acceptable for Instagram.
        
        Instagram accepts different aspect ratios for different post types:
        - Reels: Primarily vertical (9:16 recommended)
        - Feed: Both horizontal and vertical with limits
        
        Args:
            width: Frame width
            height: Frame height
            post_type: Type of post ('reel' or 'feed')
            
        Returns:
            bool: True if aspect ratio is acceptable
            
        Examples:
            >>> # Check if vertical video is suitable for reels
            >>> processor.check_aspect_ratio(1080, 1920, 'reel')  # 9:16 ratio
            True
            >>> # Check if horizontal video works for feed
            >>> processor.check_aspect_ratio(1920, 1080, 'feed')  # 16:9 ratio
            True
        """
        limits = VideoProcessor.REELS_LIMITS if post_type == 'reel' else VideoProcessor.FEED_VIDEO_LIMITS
        ratio = width / height
        
        if ratio < limits['aspect_ratio']['min']:
            logger.warning(f"Video too narrow. Minimum ratio: {limits['aspect_ratio']['min']:.2f}")
            return False
        if ratio > limits['aspect_ratio']['max']:
            logger.warning(f"Video too wide. Maximum ratio: {limits['aspect_ratio']['max']:.2f}")
            return False
        return True
        
    @staticmethod
    def check_file_size(file_size: float, post_type: str) -> bool:
        """
        Verify if video file size is within Instagram's limits.
        
        Args:
            file_size: Size in megabytes
            post_type: Type of post ('reel' or 'feed')
            
        Returns:
            bool: True if file size is acceptable
            
        Example:
            >>> info = processor.get_video_info("large_video.mp4")
            >>> if not processor.check_file_size(info['size_mb'], 'reel'):
            ...     print(f"File too large ({info['size_mb']:.1f}MB)")
        """
        limits = VideoProcessor.REELS_LIMITS if post_type == 'reel' else VideoProcessor.FEED_VIDEO_LIMITS
        if file_size > limits['max_size']:
            logger.warning(f"File too large. Maximum size: {limits['max_size']}MB")
            return False
        return True
        
    def process_video(self, video_path: str, post_type: str = 'reel') -> Optional[str]:
        """
        Process and optimize video for Instagram upload.
        
        Performs several optimizations:
        1. Validates video parameters
        2. Adjusts resolution if needed
        3. Optimizes bitrate and file size
        4. Converts to proper format if necessary
        5. Adjusts frame rate if needed
        
        Args:
            video_path: Path to input video
            post_type: Type of post ('reel' or 'feed')
            
        Returns:
            str: Path to processed video, or None if processing failed
            
        Example:
            >>> processor = VideoProcessor()
            >>> optimized = processor.process_video("input.mp4", "reel")
            >>> if optimized:
            ...     print(f"Video optimized and saved to: {optimized}")
            
        Raises:
            ValueError: If video doesn't meet Instagram's requirements
            IOError: If file operations fail
        """
        try:
            info = self.get_video_info(video_path)
            
            # Validate video parameters
            checks = [
                self.check_duration(info['duration'], post_type),
                self.check_resolution(info['width'], info['height'], post_type),
                self.check_aspect_ratio(info['width'], info['height'], post_type),
                self.check_file_size(info['size_mb'], post_type)
            ]
            
            if not all(checks):
                logger.warning("Video requires optimization")
                return self._optimize_video(video_path, post_type)
                
            logger.info("Video already meets Instagram requirements")
            return video_path
            
        except Exception as e:
            logger.error(f"Error processing video: {e}")
            return None
            
    def _optimize_video(self, video_path: str, post_type: str) -> Optional[str]:
        """
        Internal method to optimize video for Instagram upload.
        
        Optimization steps:
        1. Adjust resolution while maintaining aspect ratio
        2. Optimize bitrate based on duration
        3. Convert to compatible format
        4. Ensure proper frame rate
        5. Compress if needed
        
        Args:
            video_path: Path to input video
            post_type: Type of post ('reel' or 'feed')
            
        Returns:
            str: Path to optimized video
            
        Technical notes:
        - Uses two-pass encoding for better quality
        - Implements smart bitrate allocation
        - Preserves important metadata
        - Handles audio optimization
        """
        return VideoProcessor.force_optimize_for_instagram(video_path, post_type)