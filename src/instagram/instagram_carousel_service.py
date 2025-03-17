"""
Instagram Carousel Service

Handles posting multiple images as a carousel to Instagram, including:
- Creating carousel containers
- Managing child media items
- Publishing carousels

Updated for Instagram Graph API v22.0
"""

import os
import time
import logging
from typing import List, Optional, Dict, Any, Tuple
import requests
from ..utils.config import ConfigManager

logger = logging.getLogger(__name__)

class InstagramCarouselService:
    """Service for posting carousels (multiple images) to Instagram with Graph API v22.0"""
    
    def __init__(self, access_token=None, instagram_account_id=None):
        """
        Initialize the Instagram carousel service
        
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
    
    def create_carousel_container(self, image_urls: List[str], caption: str) -> Optional[str]:
        """
        Create a carousel container for multiple images
        
        Args:
            image_urls: List of image URLs to include in carousel
            caption: Caption text for the carousel
            
        Returns:
            str: Container ID if successful, None otherwise
        """
        try:
            if len(image_urls) < 2:
                logger.error("At least 2 images required for carousel")
                return None
                
            if len(image_urls) > 10:
                logger.warning("Maximum 10 images allowed, truncating list")
                image_urls = image_urls[:10]
            
            # Create child media objects first
            child_containers = []
            for url in image_urls:
                child_id = self._create_child_container(url)
                if child_id:
                    child_containers.append(child_id)
                else:
                    logger.error(f"Failed to create child container for {url}")
                    # Clean up any created containers
                    self._cleanup_child_containers(child_containers)
                    return None
            
            if len(child_containers) < 2:
                logger.error("Not enough valid child containers created")
                self._cleanup_child_containers(child_containers)
                return None
            
            # Create carousel container
            endpoint = f'{self.base_url}/{self.instagram_account_id}/media'
            
            params = {
                'media_type': 'CAROUSEL',
                'caption': caption,
                'children': ','.join(child_containers),
                'access_token': self.access_token
            }
            
            response = requests.post(endpoint, params=params)
            response.raise_for_status()
            
            result = response.json()
            if 'id' in result:
                logger.info(f"Created carousel container: {result['id']}")
                return result['id']
            
            logger.error(f"Failed to create carousel container: {result}")
            return None
            
        except Exception as e:
            logger.error(f"Error creating carousel container: {e}")
            return None
    
    def _create_child_container(self, image_url: str) -> Optional[str]:
        """
        Create a child media container for a carousel image
        
        Args:
            image_url: URL of the image
            
        Returns:
            str: Container ID if successful, None otherwise
        """
        try:
            endpoint = f'{self.base_url}/{self.instagram_account_id}/media'
            
            params = {
                'image_url': image_url,
                'is_carousel_item': 'true',
                'access_token': self.access_token
            }
            
            response = requests.post(endpoint, params=params)
            response.raise_for_status()
            
            result = response.json()
            if 'id' in result:
                logger.info(f"Created child container: {result['id']}")
                return result['id']
            
            logger.error(f"Failed to create child container: {result}")
            return None
            
        except Exception as e:
            logger.error(f"Error creating child container: {e}")
            return None
    
    def _cleanup_child_containers(self, container_ids: List[str]) -> None:
        """
        Clean up child containers in case of failure
        
        Args:
            container_ids: List of container IDs to clean up
        """
        for container_id in container_ids:
            try:
                endpoint = f'{self.base_url}/{container_id}'
                params = {'access_token': self.access_token}
                
                response = requests.delete(endpoint, params=params)
                if response.ok:
                    logger.info(f"Cleaned up container: {container_id}")
                else:
                    logger.warning(f"Failed to clean up container {container_id}: {response.text}")
                    
            except Exception as e:
                logger.warning(f"Error cleaning up container {container_id}: {e}")
    
    def wait_for_container_status(self, container_id: str, timeout: int = 300) -> str:
        """
        Wait for carousel container to be ready
        
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
                    logger.error(f"Carousel container failed with status: {status}")
                    return status
                    
                # Wait before checking again
                time.sleep(5)
                
            except Exception as e:
                logger.error(f"Error checking carousel container status: {e}")
                return 'ERROR'
        
        logger.error("Carousel container status check timed out")
        return 'TIMEOUT'
    
    def publish_carousel(self, container_id: str) -> Optional[str]:
        """
        Publish a carousel container
        
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
                logger.info(f"Published carousel: {result['id']}")
                return result['id']
            
            logger.error(f"Failed to publish carousel: {result}")
            return None
            
        except Exception as e:
            logger.error(f"Error publishing carousel: {e}")
            return None
    
    def get_post_permalink(self, post_id: str) -> Optional[str]:
        """
        Get the permalink for a carousel post
        
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
            logger.error(f"Error getting carousel permalink: {e}")
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