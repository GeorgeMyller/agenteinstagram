import os
import requests
import time
import json
from dotenv import load_dotenv
from typing import Optional, List, Dict, Any
import logging

#Import Base Class and exceptions:
from src.instagram.instagram_post_service import BaseInstagramService, AuthenticationError, PermissionError, RateLimitError, MediaError, TemporaryServerError, InstagramAPIError


logger = logging.getLogger(__name__)

class InstagramCarouselService(BaseInstagramService):
    """Classe para gerenciar o upload e publicação de carrosséis no Instagram."""
    # API_VERSION = "v22.0"  # Defined in Base Class.
    SUPPORTED_MEDIA_TYPES = ["image/jpeg", "image/png"]
    MAX_MEDIA_SIZE = 8 * 1024 * 1024  # 8MB in bytes

    def __init__(self, access_token=None, user_id=None):
        """Inicializa o serviço com as credenciais do Instagram."""
        load_dotenv()
        access_token = access_token or os.getenv('INSTAGRAM_API_KEY')
        user_id = user_id or os.getenv("INSTAGRAM_ACCOUNT_ID")
        if not access_token or not user_id:
            raise ValueError("INSTAGRAM_API_KEY and INSTAGRAM_ACCOUNT_ID must be set.")

        super().__init__(access_token, user_id)
        self.token_expires_at = None
        self._validate_token()


    def _validate_token(self):
        """Validates the access token and retrieves its expiration time."""
        try:
            response = self._make_request(
                "GET",
                "debug_token",
                params={
                    "input_token": self.access_token,
                },
            )
            if response and 'data' in response and response['data'].get('is_valid'):
                logger.info("Token de acesso validado com sucesso.")
                if 'instagram_basic' not in response['data'].get('scopes', []) or \
                   'instagram_content_publish' not in response['data'].get('scopes', []):
                    logger.warning("Token may not have necessary permissions for posting")
                # Store the token expiration time, if available
                self.token_expires_at = response['data'].get('expires_at')
                if self.token_expires_at:
                    logger.info(f"Token will expire at: {datetime.fromtimestamp(self.token_expires_at)}")
            else:
                logger.error("Access token is invalid or expired.")
                raise AuthenticationError("Access token is invalid or expired.")

        except InstagramAPIError as e:
            logger.error(f"Error validating token: {e}")
            raise  # Re-raise the exception to halt execution if the token is invalid

    def _refresh_token(self):
        """Refreshes the access token."""

        # Check if we have a long-lived token. If not, we can't refresh.
        if not os.getenv("INSTAGRAM_API_KEY"):
            raise AuthenticationError("Cannot refresh token. No long-lived access token available.")

        logger.info("Refreshing Instagram access token...")
        try:
            response = self._make_request(
                "GET",
                "oauth/access_token",
                params={
                    "grant_type": "ig_refresh_token",
                    "client_secret": os.getenv("INSTAGRAM_CLIENT_SECRET"),  # Use client secret
                    "access_token": self.access_token,
                },
            )

            self.access_token = response['access_token']
            self.token_expires_at = time.time() + response['expires_in']
            logger.info(f"Token refreshed. New expiration: {datetime.fromtimestamp(self.token_expires_at)}")

            # Update the .env file (DANGEROUS)
            self._update_env_file("INSTAGRAM_API_KEY", self.access_token)


        except InstagramAPIError as e:
            logger.error(f"Error refreshing token: {e}")
            raise

    def _update_env_file(self, key, new_value):
        """
        Updates the .env file with the new token.
        WARNING: Modifying the .env file directly is generally a BAD IDEA.
        """
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
                ".env file updated.  THIS IS GENERALLY NOT RECOMMENDED FOR PRODUCTION. "
            )

        except Exception as e:
            logger.error(f"Error updating .env file: {e}")
            # Don't raise - continue with the (potentially) old value


    def _validate_media(self, media_url: str) -> bool:
        """Validates media URL and type before uploading."""
        try:
            response = requests.head(media_url, timeout=10) # Don't use the session here.
            response.raise_for_status()
            content_type = response.headers.get('content-type', '').lower()
            if content_type not in self.SUPPORTED_MEDIA_TYPES:
                logger.error(f"Unsupported media type: {content_type}")
                return False
            content_length = int(response.headers.get('content-length', 0))
            if content_length > self.MAX_MEDIA_SIZE:
                logger.error(f"Media file too large: {content_length} bytes")
                return False
            return True
        except Exception as e:
            logger.error(f"Error validating media: {str(e)}")
            return False


    def _create_child_container(self, media_url):
        """Cria um contêiner filho para uma imagem do carrossel."""
        if self.token_expires_at and time.time() > self.token_expires_at - 60:
            self._refresh_token()
        endpoint = f"{self.user_id}/media" # Removed BASE_URL
        params = {
            'image_url': media_url,
            'is_carousel_item': 'true',
        }
        try:
            data = self._make_request('POST', endpoint, data=params) # Use base class method
            if not data or 'id' not in data:
                logger.error(f"Erro ao criar container filho: {data}")
                return None
            return data['id']
        except InstagramAPIError as e:
          logger.error(f"Failed to create child container: {e}")
          raise

    def create_carousel_container(self, media_urls: List[str], caption: str) -> Optional[str]:
        """Cria um contêiner de carrossel no Instagram."""
        if self.token_expires_at and time.time() > self.token_expires_at - 60:
            self._refresh_token()
        for media_url in media_urls:
            if not self._validate_media(media_url):
                return None

        children = []
        for media_url in media_urls:
            child_id = self._create_child_container(media_url)
            if not child_id:
                logger.error(f"Failed to create child container for {media_url}")
                return None #Consider raising exception
            children.append(child_id)
            time.sleep(2)  # Small delay

        if not children:
            logger.error("No child containers were created")
            return None

        params = {
            'media_type': 'CAROUSEL',
            'caption': caption[:2200],  # Instagram caption limit
            'children': ','.join(children),
        }
        try:
            data = self._make_request('POST', f'{self.user_id}/media', data=params) # Use base class method
            if data and 'id' in data:
                logger.info(f"Carousel container created successfully: {data['id']}")
                return data['id']
            return None
        except InstagramAPIError as e:
          logger.error(f"Failed to create carousel container: {e}")
          raise

    def wait_for_container_status(self, container_id: str, max_attempts: int = 30, delay: int = 5) -> str:
        """Verifica o status do container até estar pronto ou falhar."""
        if self.token_expires_at and time.time() > self.token_expires_at - 60:
            self._refresh_token()
        endpoint = f"{container_id}"  # Removed BASE_URL
        params = {
            'fields': 'status_code,status',
        }
        for attempt in range(max_attempts):
            try:
                data = self._make_request('GET', endpoint, params=params)
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
                logger.warning(f"Rate limit hit while checking status. Waiting {e.retry_after}s...")
                time.sleep(e.retry_after)
            except Exception as e:
                logger.error(f"Error checking container status: {str(e)}")
                time.sleep(delay)

        logger.error(f"Container status check timed out after {max_attempts} attempts.")
        return 'TIMEOUT'


    def publish_carousel(self, container_id):
        """Publica o carrossel no Instagram."""
        if self.token_expires_at and time.time() > self.token_expires_at - 60:
            self._refresh_token()
        endpoint = f"{self.user_id}/media_publish" # Removed BASE_URL
        params = {
            'creation_id': container_id,
        }
        try:
            data = self._make_request('POST', endpoint, data=params) # Use base class method.
            if not data:
                return None
            if 'id' in data:
                logger.info(f"Carrossel publicado com sucesso! ID: {data['id']}")
                return data['id']
            return None
        except InstagramAPIError as e:
          logger.error(f"Failed to publish carousel: {e}")
          raise

    def post_carousel(self, media_urls, caption):
        """Realiza todo o processo de publicação de um carrossel."""
        if self.token_expires_at and time.time() > self.token_expires_at - 60:
            self._refresh_token()
        container_id = self.create_carousel_container(media_urls, caption)
        if not container_id:
            return None
        status = self.wait_for_container_status(container_id)
        if status != 'FINISHED':
            logger.error(f"Container não ficou pronto. Status final: {status}")
            return None
        return self.publish_carousel(container_id)