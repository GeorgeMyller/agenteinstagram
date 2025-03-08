import os
import time
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
from src.instagram.base_instagram_service import (
    BaseInstagramService, AuthenticationError, PermissionError,
    RateLimitError, MediaError, TemporaryServerError, InstagramAPIError
)

logger = logging.getLogger('InstagramPostService')

class InstagramPostService(BaseInstagramService):
    """Service for posting images to Instagram."""

    def __init__(self, access_token=None, ig_user_id=None):
        load_dotenv()
        access_token = access_token or os.getenv('INSTAGRAM_API_KEY')
        ig_user_id = ig_user_id or os.getenv("INSTAGRAM_ACCOUNT_ID")
        
        if not access_token or not ig_user_id:
            raise ValueError(
                "Credenciais incompletas. Defina INSTAGRAM_API_KEY e "
                "INSTAGRAM_ACCOUNT_ID nas variáveis de ambiente ou forneça-os diretamente."
            )

        super().__init__(access_token, ig_user_id)
        self.state_file = 'api_state.json'
        self.container_cache = {}
        self._load_state()

    def _load_state(self):
        """Load previous API state if available"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    if 'container_cache' in state:
                        for key, data in state['container_cache'].items():
                            if 'timestamp' in data:
                                data['timestamp'] = float(data['timestamp'])
                        self.container_cache = state['container_cache']
        except Exception as e:
            logger.error(f"Failed to load API state: {str(e)}")

    def _save_state(self):
        """Save current API state for future use"""
        try:
            state = {
                'container_cache': self.container_cache,
            }
            with open(self.state_file, 'w') as f:
                json.dump(state, f)
        except Exception as e:
            logger.error(f"Failed to save API state: {str(e)}")

    def create_media_container(self, image_url, caption):
        """Creates a media container for the post."""
        # Check container cache first
        cache_key = f"{image_url}:{caption[:50]}"
        if cache_key in self.container_cache and time.time() - self.container_cache[cache_key]['timestamp'] < 3600:
            container_id = self.container_cache[cache_key]['id']
            logger.info(f"Reusing cached container ID: {container_id}")
            return container_id

        params = {
            'image_url': image_url,
            'caption': caption
        }

        try:
            result = self._make_request('POST', f"{self.ig_user_id}/media", data=params)
            if result and 'id' in result:
                container_id = result['id']
                logger.info(f"Media container created with ID: {container_id}")
                
                # Cache the container ID
                self.container_cache[cache_key] = {
                    'id': container_id,
                    'timestamp': time.time()
                }
                self._save_state()
                
                return container_id
            return None
        except InstagramAPIError as e:
            logger.error(f"Failed to create media container: {e}")
            raise

    def verify_media_status(self, media_id, max_attempts=5, delay=30):
        """Verify if a media post exists and is published."""
        known_status = {
            'PUBLISHED': True,
            'FINISHED': True,
            'IN_PROGRESS': None,
            'ERROR': False,
            'EXPIRED': False,
            'SCHEDULED': None
        }

        params = {
            'fields': 'id,status_code,status,permalink'
        }

        for attempt in range(max_attempts):
            if attempt > 0:
                wait_time = delay * (1.5 ** attempt)
                logger.info(f"Checking status (attempt {attempt + 1}/{max_attempts}), waiting {int(wait_time)} seconds...")
                time.sleep(wait_time)

            try:
                data = self._make_request('GET', f"{media_id}", params=params)
                
                if 'id' in data:
                    status = data.get('status_code') or data.get('status', 'UNKNOWN')
                    logger.info(f"Post status: {status}")

                    # Check if we have a permalink (usually means post is live)
                    if data.get('permalink'):
                        logger.info(f"Post is live with permalink: {data['permalink']}")
                        return True

                    # Handle known status
                    if status in known_status:
                        result = known_status[status]
                        if result is not None:  # We have a definitive answer
                            return result
                        # For None results (like IN_PROGRESS), we continue waiting
                        logger.info(f"Post is still processing (status: {status})")
                        continue

                    # For unknown status, if we have an ID and no error, assume success on last attempt
                    if attempt == max_attempts - 1:
                        logger.info(f"Unknown status '{status}' but post ID exists")
                        return True

            except RateLimitError as e:
                logger.warning(f"Rate limit hit, waiting {e.retry_seconds}s...")
                time.sleep(e.retry_seconds)
            except Exception as e:
                logger.error(f"Error checking status: {str(e)}")
                if attempt == max_attempts - 1:
                    logger.error("Max retries reached with errors")
                    return False

        logger.warning("Could not confirm post status after maximum attempts")
        return False

    def publish_media(self, media_container_id):
        """Publishes the media container to Instagram."""
        # Initial stabilization wait
        wait_time = 30
        logger.info(f"Waiting {wait_time} seconds for container processing...")
        time.sleep(wait_time)

        # First verify if the container is ready
        if not self.verify_media_status(media_container_id, max_attempts=3, delay=20):
            logger.error("Media container not ready for publishing")
            return None

        params = {
            'creation_id': media_container_id,
        }

        try:
            result = self._make_request('POST', f"{self.ig_user_id}/media_publish", data=params)
            
            if result and 'id' in result:
                post_id = result['id']
                logger.info(f"Publication initiated with ID: {post_id}")
                
                # Give Instagram time to process before verification
                time.sleep(45)
                
                # Verify with new post ID first
                if self.verify_media_status(post_id, max_attempts=4, delay=30):
                    logger.info("Post publication confirmed with new ID!")
                    return post_id
                
                # If that fails, try with original container ID
                if post_id != media_container_id:
                    logger.info("Trying verification with original container ID...")
                    if self.verify_media_status(media_container_id, max_attempts=3, delay=30):
                        logger.info("Post publication confirmed with container ID!")
                        return media_container_id
            
            logger.error("Could not confirm post publication")
            return None
            
        except InstagramAPIError as e:
            logger.error(f"Error publishing media: {e}")
            raise

    def post_image(self, image_url, caption):
        """Handles the full flow of creating and publishing an Instagram post."""
        logger.info("Starting Instagram image publication...")

        media_container_id = self.create_media_container(image_url, caption)
        if not media_container_id:
            logger.error("Failed to create media container.")
            return None

        # Add a delay for container stabilization
        wait_time = 45
        logger.info(f"Waiting {wait_time} seconds for container stabilization...")
        time.sleep(wait_time)

        # Verify container before attempting to publish
        logger.info("Verifying media container...")
        if not self.verify_media_status(media_container_id, max_attempts=3, delay=20):
            logger.error("Media container verification failed")
            return None

        post_id = self.publish_media(media_container_id)
        if post_id:
            logger.info(f"Process completed successfully! Post ID: {post_id}")
            return post_id

        logger.info("Final verification of post status...")
        time.sleep(60)  # Extended wait for final check
        
        # One last verification attempt with longer delays
        if self.verify_media_status(media_container_id, max_attempts=3, delay=45):
            logger.info("Post verified and confirmed on Instagram!")
            return media_container_id

        logger.error("Could not confirm post publication after multiple attempts.")
        return None

