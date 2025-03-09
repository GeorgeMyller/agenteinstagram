import os
import time
import json
import logging
import random
from typing import Dict, Any, Optional, List
from datetime import datetime
from dotenv import load_dotenv
from src.instagram.base_instagram_service import (
    BaseInstagramService, AuthenticationError, PermissionError,
    RateLimitError, MediaError, TemporaryServerError, InstagramAPIError
)

logger = logging.getLogger('InstagramCarouselService')

class CarouselCreationError(Exception):
    """Raised when there are issues creating a carousel"""
    def __init__(self, message, error_code=None, error_subcode=None, fb_trace_id=None):
        self.error_code = error_code
        self.error_subcode = error_subcode
        self.fb_trace_id = fb_trace_id
        super().__init__(message)

class InstagramCarouselService(BaseInstagramService):
    """Classe para gerenciar o upload e publicação de carrosséis no Instagram."""

    SUPPORTED_MEDIA_TYPES = ["image/jpeg", "image/png"]
    MAX_MEDIA_SIZE = 8 * 1024 * 1024  # 8MB in bytes

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
        self.token_expires_at = None
        self._validate_token()

    def _validate_token(self, force_check=False):
        """Validates the access token and retrieves its expiration time.
        
        Args:
            force_check: If True, always check the token validity with the API.
                        If False (default), might use cached validation results.
        """
        try:
            # Add more detailed logging
            logger.info(f"Validating Instagram token (force_check={force_check})")
            logger.info(f"Using Instagram Account ID: {self.instagram_account_id}")
            
            response = self._make_request(
                "GET",
                "debug_token",
                params={"input_token": self.access_token}
            )
            if response and 'data' in response and response['data'].get('is_valid'):
                logger.info("Token de acesso validado com sucesso.")
                
                # Check and log scopes
                scopes = response['data'].get('scopes', [])
                logger.info(f"Token scopes: {scopes}")
                
                if 'instagram_basic' not in scopes:
                    logger.warning("Token is missing 'instagram_basic' permission")
                
                if 'instagram_content_publish' not in scopes:
                    logger.warning("Token is missing 'instagram_content_publish' permission - REQUIRED for posting!")
                
                # Check for other important permissions
                missing_perms = []
                required_perms = ['instagram_basic', 'instagram_content_publish']
                for perm in required_perms:
                    if perm not in scopes:
                        missing_perms.append(perm)
                
                if missing_perms:
                    logger.error(f"Token is missing required permissions: {missing_perms}")
                    raise PermissionError(
                        f"Token is missing required permissions: {missing_perms}. "
                        f"Please request these permissions in your app and get a new token."
                    )
                
                self.token_expires_at = response['data'].get('expires_at')
                if self.token_expires_at:
                    logger.info(f"Token will expire at: {datetime.fromtimestamp(self.token_expires_at)}")
                    
                    # Check if token needs refresh soon
                    if time.time() > self.token_expires_at - (86400 * 3):  # 3 days before expiration
                        logger.warning("Token will expire soon. Consider refreshing it.")
            else:
                logger.error("Access token is invalid or expired.")
                raise AuthenticationError("Access token is invalid or expired.")
        except InstagramAPIError as e:
            logger.error(f"Error validating token: {e}")
            raise

    def _refresh_token(self):
        """Refreshes the access token."""
        if not os.getenv("INSTAGRAM_API_KEY"):
            raise AuthenticationError("Cannot refresh token. No long-lived access token available.")

        logger.info("Refreshing Instagram access token...")
        try:
            response = self._make_request(
                "GET",
                "oauth/access_token",
                params={
                    "grant_type": "ig_refresh_token",
                    "client_secret": os.getenv("INSTAGRAM_CLIENT_SECRET"),
                    "access_token": self.access_token,
                }
            )
            self.access_token = response['access_token']
            self.token_expires_at = time.time() + response['expires_in']
            logger.info(f"Token refreshed. New expiration: {datetime.fromtimestamp(self.token_expires_at)}")
            
            # Update the .env file (with warning)
            self._update_env_file("INSTAGRAM_API_KEY", self.access_token)
        except InstagramAPIError as e:
            logger.error(f"Error refreshing token: {e}")
            raise

    def _update_env_file(self, key, new_value):
        """Updates the .env file with the new token (use with caution)."""
        try:
            with open(".env", "r") as f:
                lines = f.readlines()
            updated_lines = []
            found = False
            for line in lines:
                if line.startswith(f"{key}="):
                    updated_lines.append(f"{key}={new_value}\n")
                    found = True
                else:
                    updated_lines.append(line)
            if not found:
                updated_lines.append(f"{key}={new_value}\n")
            with open(".env", "w") as f:
                f.writelines(updated_lines)
            logger.warning(
                ".env file updated. THIS IS GENERALLY NOT RECOMMENDED FOR PRODUCTION."
            )
        except Exception as e:
            logger.error(f"Error updating .env file: {e}")

    def _validate_media(self, media_url: str) -> bool:
        """Validates media URL and type before uploading with retry mechanism."""
        max_retries = 5
        base_delay = 5  # seconds - increased from 2 to 5
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Validating media URL (attempt {attempt+1}/{max_retries}): {media_url}")
                
                # Create a new session for each attempt to avoid connection pooling issues
                import requests
                session = requests.Session()
                
                # Add user agent to mimic browser request
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                    'Accept': 'image/jpeg, image/png, */*'
                }
                
                response = session.head(media_url, timeout=20, headers=headers)  # Increased timeout
                
                if response.status_code != 200:
                    logger.error(f"Media URL not accessible: {media_url}, status code: {response.status_code}")
                    
                    # If we get a 429, we should back off more aggressively
                    if response.status_code == 429:
                        # Use retry-after header if present, otherwise use exponential backoff
                        retry_after = int(response.headers.get('retry-after', base_delay * (2 ** attempt)))
                        # Ensure we wait at least 10 seconds for Imgur rate limits
                        retry_after = max(retry_after, 10 + random.randint(1, 10))
                        logger.warning(f"Rate limit hit from image host. Waiting {retry_after}s before retry...")
                        time.sleep(retry_after)
                    elif attempt < max_retries - 1:
                        # Exponential backoff with jitter for other errors
                        delay = base_delay * (2 ** attempt) + random.uniform(0, 3)
                        logger.warning(f"Will retry after {delay:.2f}s...")
                        time.sleep(delay)
                    continue

                content_type = response.headers.get('content-type', '').lower()
                if content_type not in self.SUPPORTED_MEDIA_TYPES:
                    logger.error(f"Unsupported media type: {content_type}")
                    return False

                content_length = int(response.headers.get('content-length', 0))
                if content_length > self.MAX_MEDIA_SIZE:
                    logger.error(f"Media file too large: {content_length} bytes")
                    return False

                logger.info(f"Media validation successful: {media_url}")
                return True
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Error validating media (attempt {attempt+1}/{max_retries}): {str(e)}")
                
                if "too many 429 error responses" in str(e) or "429" in str(e):
                    # This is likely a rate limit issue
                    delay = base_delay * (3 ** attempt) + random.uniform(5, 15)  # More aggressive backoff
                    logger.warning(f"Rate limit hit from image host. Waiting {delay:.2f}s before retry...")
                    time.sleep(delay)
                elif attempt < max_retries - 1:
                    # General network error, retry with exponential backoff
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 5)
                    logger.warning(f"Network error, will retry after {delay:.2f}s...")
                    time.sleep(delay)
            except Exception as e:
                logger.error(f"Unexpected error validating media: {str(e)}")
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 5)
                    logger.warning(f"Will retry after {delay:.2f}s...")
                    time.sleep(delay)
        
        logger.error(f"Failed to validate media after {max_retries} attempts: {media_url}")
        return False

    def _create_child_container(self, media_url: str) -> Optional[str]:
        """Creates a child container for a carousel image."""
        if self.token_expires_at and time.time() > self.token_expires_at - 60:
            self._refresh_token()

        if not self._validate_media(media_url):
            logger.error(f"Media validation failed for: {media_url}")
            return None

        params = {
            'image_url': media_url,
            'is_carousel_item': 'true'
        }

        try:
            result = self._make_request('POST', f"{self.ig_user_id}/media", data=params)
            if result and 'id' in result:
                container_id = result['id']
                logger.info(f"Child container created: {container_id}")
                return container_id
            return None
        except InstagramAPIError as e:
            logger.error(f"Failed to create child container: {e}")
            raise

    def create_carousel_container(self, media_urls: List[str], caption: str) -> Optional[str]:
        """Creates a container for a carousel post."""
        if self.token_expires_at and time.time() > self.token_expires_at - 60:
            self._refresh_token()
            
        logger.info(f"Creating carousel container with {len(media_urls)} images")

        # Validate all media first - but don't fail immediately if one fails
        valid_media_urls = []
        for media_url in media_urls:
            if self._validate_media(media_url):
                valid_media_urls.append(media_url)
            else:
                logger.warning(f"Skipping invalid media URL: {media_url}")
        
        if len(valid_media_urls) < 2:
            logger.error(f"Not enough valid media URLs to create carousel. Found: {len(valid_media_urls)}, required: at least 2")
            return None
        
        logger.info(f"Proceeding with {len(valid_media_urls)} valid media URLs")

        # Create children containers
        children = []
        for media_url in valid_media_urls:
            child_id = self._create_child_container(media_url)
            if not child_id:
                logger.error(f"Failed to create child container for {media_url}")
                continue
            children.append(child_id)
            time.sleep(2)  # Respect rate limits between child creation

        if len(children) < 2:
            logger.error(f"Not enough child containers created. Found: {len(children)}, required: at least 2")
            return None

        params = {
            'media_type': 'CAROUSEL',
            'caption': caption[:2200],  # Instagram caption limit
            'children': ','.join(children)
        }

        try:
            result = self._make_request('POST', f"{self.ig_user_id}/media", data=params)
            if result and 'id' in result:
                container_id = result['id']
                logger.info(f"Carousel container created successfully: {container_id}")
                return container_id
            return None
        except InstagramAPIError as e:
            logger.error(f"Failed to create carousel container: {e}")
            raise

    def wait_for_container_status(self, container_id: str, max_attempts: int = 30, delay: int = 5) -> str:
        """Verifica o status do container até estar pronto ou falhar."""
        if self.token_expires_at and time.time() > self.token_expires_at - 60:
            self._refresh_token()

        for attempt in range(max_attempts):
            try:
                params = {
                    'fields': 'status_code,status'
                }
                
                data = self._make_request('GET', f"{container_id}", params=params)
                if not data:
                    logger.warning(f"Failed to get container status (attempt {attempt + 1}/{max_attempts})")
                    time.sleep(delay)
                    continue

                status = data.get('status_code', '')
                logger.info(f"Container status (attempt {attempt + 1}/{max_attempts}): {status}")

                if status == 'FINISHED':
                    return status
                elif status in ['ERROR', 'EXPIRED']:
                    logger.error(f"Container failed with status: {status}")
                    return status

                time.sleep(delay)

            except RateLimitError as e:
                logger.warning(f"Rate limit hit while checking status. Waiting {e.retry_seconds}s...")
                time.sleep(e.retry_seconds)
            except Exception as e:
                logger.error(f"Error checking container status: {str(e)}")
                time.sleep(delay)

        logger.error(f"Container status check timed out after {max_attempts} attempts.")
        return 'TIMEOUT'

    def publish_carousel(self, container_id: str) -> Optional[str]:
        """Publishes the carousel post."""
        if self.token_expires_at and time.time() > self.token_expires_at - 60:
            self._refresh_token()

        params = {
            'creation_id': container_id
        }

        try:
            # Add detailed logging to help diagnose issues
            logger.info(f"Attempting to publish carousel with container ID: {container_id}")
            
            # Print detailed info about the request
            logger.info(f"Publishing to endpoint: {self.ig_user_id}/media_publish")
            logger.info(f"Publishing with params: {params}")
            
            result = self._make_request('POST', f"{self.ig_user_id}/media_publish", data=params)
            
            if result and 'id' in result:
                post_id = result['id']
                logger.info(f"Carousel published successfully! ID: {post_id}")
                return post_id

            logger.error(f"Failed to publish carousel. Response: {result}")
            return None
            
        except InstagramAPIError as e:
            logger.error(f"Error publishing carousel: {e}")
            
            # Add additional error details
            if hasattr(e, 'error_type'):
                logger.error(f"Error type: {getattr(e, 'error_type')}")
            if hasattr(e, 'error_message'):
                logger.error(f"Error message: {getattr(e, 'error_message')}")
            if hasattr(e, 'error_code'):
                logger.error(f"Error code: {getattr(e, 'error_code')}")
            if hasattr(e, 'fb_trace_id'):
                logger.error(f"FB trace ID: {getattr(e, 'fb_trace_id')}")
                
            raise

    def post_carousel(self, media_urls: List[str], caption: str) -> Optional[str]:
        """Handles the full flow of creating and publishing a carousel post."""
        if len(media_urls) < 2 or len(media_urls) > 10:
            raise ValueError(f"Invalid number of media URLs. Found: {len(media_urls)}, required: 2-10")

        # Create carousel container
        container_id = self.create_carousel_container(media_urls, caption)
        if not container_id:
            return None

        # Wait for container to be ready
        status = self.wait_for_container_status(container_id)
        if status != 'FINISHED':
            logger.error(f"Container não ficou pronto. Status final: {status}")
            return None

        # Additional delay before publishing to ensure container is fully processed
        logger.info("Adding extra delay before publishing to ensure container is fully processed...")
        time.sleep(10)  # 10 seconds extra delay

        # Publish carousel
        return self.publish_carousel(container_id)
        
    def check_token_permissions(self):
        """
        Check if the access token has the necessary permissions for posting.
        Returns a tuple (is_valid, missing_permissions)
        """
        try:
            response = self._make_request(
                "GET",
                "debug_token",
                params={"input_token": self.access_token}
            )
            
            if not response or 'data' not in response:
                return False, ["Unable to verify token"]
                
            token_data = response['data']
            
            if not token_data.get('is_valid', False):
                return False, ["Token is invalid or expired"]
                
            scopes = token_data.get('scopes', [])
            required_permissions = ['instagram_basic', 'instagram_content_publish']
            
            missing = [p for p in required_permissions if p not in scopes]
            
            return len(missing) == 0, missing
            
        except Exception as e:
            logger.error(f"Error checking token permissions: {e}")
            return False, [str(e)]