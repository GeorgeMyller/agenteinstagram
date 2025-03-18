import os
import requests
import json
import time
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)

class VideoUploader:
    """Class to handle video uploads to temporary hosting service"""
    
    def __init__(self):
        """Initialize the video uploader with default settings"""
        self.api_url = "https://api.imgur.com/3/upload"
        self.client_id = os.getenv("IMGUR_CLIENT_ID")
        self.upload_history = []
        
    def upload_from_path(self, video_path: str) -> Optional[Dict]:
        """
        Upload a video file from a local path
        
        Args:
            video_path (str): Path to the video file
            
        Returns:
            dict: Upload response containing url and deletehash, or None if failed
        """
        if not os.path.exists(video_path):
            logger.error(f"Video file not found: {video_path}")
            return None
            
        try:
            # Read video file
            with open(video_path, 'rb') as video:
                files = {'video': video}
                headers = {'Authorization': f'Client-ID {self.client_id}'}
                
                # Upload to temporary host
                response = requests.post(
                    self.api_url,
                    headers=headers,
                    files=files
                )
                
                if response.status_code == 200:
                    data = response.json()['data']
                    result = {
                        'url': data['link'],
                        'deletehash': data['deletehash'],
                        'id': data['id']
                    }
                    self.upload_history.append(result)
                    return result
                else:
                    logger.error(f"Upload failed: {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error uploading video: {str(e)}")
            return None
            
    def delete_video(self, delete_hash: str) -> bool:
        """
        Delete an uploaded video using its delete hash
        
        Args:
            delete_hash (str): The delete hash returned when the video was uploaded
            
        Returns:
            bool: True if deleted successfully, False otherwise
        """
        try:
            headers = {'Authorization': f'Client-ID {self.client_id}'}
            response = requests.delete(
                f"https://api.imgur.com/3/image/{delete_hash}",
                headers=headers
            )
            
            if response.status_code == 200:
                # Remove from upload history if present
                self.upload_history = [
                    upload for upload in self.upload_history 
                    if upload.get('deletehash') != delete_hash
                ]
                return True
            else:
                logger.error(f"Failed to delete video: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting video: {str(e)}")
            return False
            
    def cleanup(self):
        """Clean up all uploaded videos in the upload history"""
        for upload in self.upload_history[:]:
            if 'deletehash' in upload:
                self.delete_video(upload['deletehash'])
                
    def __del__(self):
        """Ensure cleanup when the uploader is destroyed"""
        self.cleanup()