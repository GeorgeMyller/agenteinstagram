"""
Instagram Reels Publisher

Handles posting videos as Reels to Instagram, including:
- Video validation and optimization
- Container creation and management
- Publishing reels

Updated for Instagram Graph API v22.0
"""

import os
import time
import logging
from typing import Optional, Dict, Any, Tuple
import requests
from moviepy.editor import VideoFileClip
from ..utils.config import ConfigManager

logger = logging.getLogger(__name__)

class ReelsPublisher:
    """Service for publishing Reels to Instagram with Graph API v22.0"""
    
    def __init__(self, access_token=None, instagram_account_id=None):
        """
        Initialize the Reels publisher service
        
        Args:
            access_token: Instagram Graph API access token
            instagram_account_id: Instagram business account ID
        """
        self.config = ConfigManager()
        
        # Use parameters if provided, otherwise try config
        self.access_token = access_token or self.config.get_value('instagram.auth.access_token')
        self.instagram_account_id = instagram_account_id or self.config.get_value('instagram.auth.business_account_id')
        
        if not self.access_token or not self.instagram_account_id:
            raise ValueError("Instagram API key and account ID must be configured")
            
        self.api_version = 'v22.0'  # Updated Instagram Graph API version
        self.base_url = f'https://graph.facebook.com/{self.api_version}'
        
        # Video requirements
        self.min_duration = 3.0  # seconds (updated for Reels)
        self.max_duration = 90.0  # seconds
        self.min_width = 600  # pixels
        self.min_height = 600  # pixels
        self.aspect_ratio_min = 4.0/5.0
        self.aspect_ratio_max = 1.91
    
    def validate_video(self, video_path: str) -> Dict[str, Any]:
        """
        Validate video meets Instagram requirements
        
        Args:
            video_path: Path to video file
            
        Returns:
            Dict with validation results
        """
        try:
            if not os.path.exists(video_path):
                return {'valid': False, 'error': 'Video file not found'}
                
            with VideoFileClip(video_path) as clip:
                duration = clip.duration
                width = clip.w
                height = clip.h
                aspect_ratio = width / height
                
                issues = []
                
                if duration < self.min_duration:
                    issues.append(f"Video too short ({duration:.1f}s < {self.min_duration}s)")
                elif duration > self.max_duration:
                    issues.append(f"Video too long ({duration:.1f}s > {self.max_duration}s)")
                    
                if width < self.min_width or height < self.min_height:
                    issues.append(f"Video dimensions too small ({width}x{height})")
                    
                if aspect_ratio < self.aspect_ratio_min:
                    issues.append(f"Aspect ratio too narrow ({aspect_ratio:.2f})")
                elif aspect_ratio > self.aspect_ratio_max:
                    issues.append(f"Aspect ratio too wide ({aspect_ratio:.2f})")
                
                return {
                    'valid': len(issues) == 0,
                    'duration': duration,
                    'dimensions': f"{width}x{height}",
                    'aspect_ratio': aspect_ratio,
                    'issues': issues
                }
                
        except Exception as e:
            logger.error(f"Error validating video: {e}")
            return {'valid': False, 'error': str(e)}
    
    def optimize_video(self, video_path: str, output_path: Optional[str] = None) -> Optional[str]:
        """
        Optimize video for Instagram requirements
        
        Args:
            video_path: Path to input video
            output_path: Optional path for optimized video
            
        Returns:
            str: Path to optimized video if successful, None otherwise
        """
        try:
            if not output_path:
                filename = os.path.splitext(os.path.basename(video_path))[0]
                output_path = os.path.join(
                    os.path.dirname(video_path),
                    f"{filename}_optimized.mp4"
                )
            
            with VideoFileClip(video_path) as clip:
                # Resize if needed
                width = clip.w
                height = clip.h
                
                if width < self.min_width or height < self.min_height:
                    scale = max(
                        self.min_width / width,
                        self.min_height / height
                    )
                    clip = clip.resize(scale)
                
                # Trim if too long
                if clip.duration > self.max_duration:
                    clip = clip.subclip(0, self.max_duration)
                
                # Write optimized video
                clip.write_videofile(
                    output_path,
                    codec='libx264',
                    audio_codec='aac',
                    temp_audiofile='temp-audio.m4a',
                    remove_temp=True,
                    threads=4,
                    preset='medium'
                )
                
                return output_path
                
        except Exception as e:
            logger.error(f"Error optimizing video: {e}")
            return None
    
    def create_container(self, video_url: str, caption: str, share_to_feed: bool = True) -> Optional[str]:
        """
        Create a container for a Reel
        
        Args:
            video_url: URL of the video
            caption: Caption text
            share_to_feed: Whether to share to main feed
            
        Returns:
            str: Container ID if successful, None otherwise
        """
        try:
            endpoint = f'{self.base_url}/{self.instagram_account_id}/media'
            
            params = {
                'media_type': 'REELS',
                'video_url': video_url,
                'caption': caption,
                'share_to_feed': str(share_to_feed).lower(),
                'access_token': self.access_token
            }
            
            response = requests.post(endpoint, params=params)
            response.raise_for_status()
            
            result = response.json()
            if 'id' in result:
                logger.info(f"Created Reels container: {result['id']}")
                return result['id']
            
            logger.error(f"Failed to create Reels container: {result}")
            return None
            
        except Exception as e:
            logger.error(f"Error creating Reels container: {e}")
            return None
    
    def wait_for_container_status(self, container_id: str, timeout: int = 300) -> str:
        """
        Wait for Reels container to be ready
        
        Args:
            container_id: Container ID to check
            timeout: Maximum time to wait in seconds
            
        Returns:
            str: Container status
        """
        endpoint = f'{self.base_url}/{container_id}'
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                response = requests.get(
                    endpoint,
                    params={'fields': 'status_code', 'access_token': self.access_token}
                )
                response.raise_for_status()
                
                result = response.json()
                status = result.get('status_code')
                
                if status == 'FINISHED':
                    return status
                elif status in ['ERROR', 'EXPIRED']:
                    logger.error(f"Reels container failed with status: {status}")
                    return status
                    
                # Wait before checking again
                time.sleep(5)
                
            except Exception as e:
                logger.error(f"Error checking Reels container status: {e}")
                return 'ERROR'
        
        logger.error("Reels container status check timed out")
        return 'TIMEOUT'
    
    def publish_reel(self, container_id: str) -> Optional[str]:
        """
        Publish a Reel container
        
        Args:
            container_id: Container ID to publish
            
        Returns:
            str: Post ID if successful, None otherwise
        """
        try:
            endpoint = f'{self.base_url}/{self.instagram_account_id}/media_publish'
            
            params = {
                'creation_id': container_id,
                'access_token': self.access_token
            }
            
            response = requests.post(endpoint, params=params)
            response.raise_for_status()
            
            result = response.json()
            if 'id' in result:
                logger.info(f"Published Reel: {result['id']}")
                return result['id']
            
            logger.error(f"Failed to publish Reel: {result}")
            return None
            
        except Exception as e:
            logger.error(f"Error publishing Reel: {e}")
            return None
    
    def get_post_permalink(self, post_id: str) -> Optional[str]:
        """
        Get the permalink for a Reel
        
        Args:
            post_id: Post ID to get permalink for
            
        Returns:
            str: Post permalink if successful, None otherwise
        """
        try:
            endpoint = f'{self.base_url}/{post_id}'
            
            params = {
                'fields': 'permalink',
                'access_token': self.access_token
            }
            
            response = requests.get(endpoint, params=params)
            response.raise_for_status()
            
            result = response.json()
            return result.get('permalink')
            
        except Exception as e:
            logger.error(f"Error getting Reel permalink: {e}")
            return None
            
    def check_token_permissions(self) -> Tuple[bool, list]:
        """
        Check if the access token has required permissions
        
        Returns:
            tuple: (is_valid, list of missing permissions)
        """
        required_permissions = [
            'instagram_basic',
            'instagram_content_publish',
            'pages_read_engagement'
        ]
        
        try:
            endpoint = f'{self.base_url}/debug_token'
            
            params = {
                'input_token': self.access_token,
                'access_token': self.access_token
            }
            
            response = requests.get(endpoint, params=params)
            response.raise_for_status()
            
            result = response.json()
            if 'data' not in result:
                return False, required_permissions
                
            data = result['data']
            if 'scopes' not in data:
                return False, required_permissions
                
            current_permissions = data['scopes']
            missing_permissions = [
                perm for perm in required_permissions 
                if perm not in current_permissions
            ]
            
            return len(missing_permissions) == 0, missing_permissions
            
        except Exception as e:
            logger.error(f"Error checking token permissions: {e}")
            return False, required_permissions