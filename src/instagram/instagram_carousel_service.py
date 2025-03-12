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

class RateLimitState:
    """Track rate limit state"""
    def __init__(self):
        self.last_error_time = 0
        self.error_count = 0
        self.backoff_until = 0
        self.min_delay = 60  # Start with 1 minute
        self.max_delay = 3600  # Max 1 hour delay

    def should_backoff(self) -> bool:
        """Check if we should still be backing off"""
        return time.time() < self.backoff_until

    def get_backoff_time(self) -> float:
        """Get how many seconds to wait"""
        if self.should_backoff():
            return self.backoff_until - time.time()
        return 0

    def record_error(self):
        """Record a rate limit error and calculate backoff"""
        current_time = time.time()
        
        # Reset error count if it's been more than an hour
        if current_time - self.last_error_time > 3600:
            self.error_count = 0
            
        self.error_count += 1
        self.last_error_time = current_time
        
        # Calculate exponential backoff with jitter
        delay = min(self.min_delay * (2 ** (self.error_count - 1)), self.max_delay)
        jitter = random.uniform(0, delay * 0.1)  # 10% jitter
        self.backoff_until = current_time + delay + jitter
        
        return delay + jitter

class InstagramCarouselService(BaseInstagramService):
    """Classe para gerenciar o upload e publicação de carrosséis no Instagram."""

    SUPPORTED_MEDIA_TYPES = ["image/jpeg", "image/png"]
    MAX_MEDIA_SIZE = 8 * 1024 * 1024  # 8MB in bytes
    MAX_RETRIES = 3
    BASE_DELAY = 5

    def __init__(self, access_token=None, ig_user_id=None, skip_token_validation=False):
        load_dotenv()
        access_token = access_token or os.getenv('INSTAGRAM_API_KEY')
        ig_user_id = ig_user_id or os.getenv('INSTAGRAM_ACCOUNT_ID')
        
        if not access_token or not ig_user_id:
            raise ValueError(
                "Credenciais incompletas. Defina INSTAGRAM_API_KEY e "
                "INSTAGRAM_ACCOUNT_ID nas variáveis de ambiente ou forneça-os diretamente."
            )
            
        super().__init__(access_token, ig_user_id)
        self.token_expires_at = None
        self.skip_token_validation = skip_token_validation
        
        if not skip_token_validation:
            self._validate_token()

    def post_carousel(self, media_urls: List[str], caption: str) -> Dict[str, Any]:
        """Handles the full flow of creating and publishing a carousel post."""
        try:
            if len(media_urls) < 2 or len(media_urls) > 10:
                return {
                    'status': 'error',
                    'message': f'Invalid number of media URLs. Found: {len(media_urls)}, required: 2-10'
                }

            # Validate all media first with parallel processing
            valid_media_urls = []
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                validation_futures = {executor.submit(self._validate_media, url): url for url in media_urls}
                for future in concurrent.futures.as_completed(validation_futures):
                    url = validation_futures[future]
                    try:
                        if future.result():
                            valid_media_urls.append(url)
                    except Exception as e:
                        logger.warning(f"Failed to validate {url}: {str(e)}")

            if len(valid_media_urls) < 2:
                return {
                    'status': 'error',
                    'message': f'Not enough valid media URLs. Found: {len(valid_media_urls)}, required: at least 2'
                }

            # Create carousel container with retry logic
            container_id = None
            retry_count = 0
            while retry_count < self.MAX_RETRIES and not container_id:
                try:
                    container_id = self.create_carousel_container(valid_media_urls, caption)
                    if container_id:
                        break
                except (RateLimitError, TemporaryServerError) as e:
                    retry_after = getattr(e, 'retry_seconds', self.BASE_DELAY * (2 ** retry_count))
                    if retry_count < self.MAX_RETRIES - 1:
                        logger.warning(f"Retrying container creation after {retry_after}s...")
                        time.sleep(retry_after)
                    retry_count += 1
                except Exception as e:
                    logger.error(f"Failed to create carousel container: {str(e)}")
                    return {'status': 'error', 'message': str(e)}

            if not container_id:
                return {'status': 'error', 'message': 'Failed to create carousel container'}

            # Wait for container with improved status checking
            logger.info(f"Waiting for container {container_id} to be ready...")
            status = self.wait_for_container_status(container_id)

            if status not in ['FINISHED', 'PUBLISHED']:
                if retry_count > 0:  # If we already retried creation, try publishing anyway
                    logger.warning(f"Container status {status}, attempting publish after retries...")
                else:
                    return {'status': 'error', 'message': f'Container not ready. Status: {status}'}

            # Publish with retry logic
            post_id = None
            publish_retry = 0
            while publish_retry < self.MAX_RETRIES and not post_id:
                try:
                    post_id = self.publish_carousel(container_id)
                    if post_id:
                        return {'status': 'success', 'id': post_id}
                except (RateLimitError, TemporaryServerError) as e:
                    retry_after = getattr(e, 'retry_seconds', self.BASE_DELAY * (2 ** publish_retry))
                    if publish_retry < self.MAX_RETRIES - 1:
                        logger.warning(f"Retrying publish after {retry_after}s...")
                        time.sleep(retry_after)
                    publish_retry += 1
                except Exception as e:
                    logger.error(f"Failed to publish carousel: {str(e)}")
                    return {'status': 'error', 'message': str(e)}

            return {'status': 'error', 'message': 'Failed to publish carousel after retries'}

        except Exception as e:
            logger.error(f"Unexpected error in post_carousel: {str(e)}")
            return {'status': 'error', 'message': str(e)}

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
            
        # Adiciona um atraso inicial para dar tempo ao Instagram processar o container
        logger.info("Aguardando processamento inicial do container...")
        time.sleep(15)  # Atraso inicial de 15 segundos
        
        for attempt in range(max_attempts):
            try:
                # Requisição simplificada - menos campos diminui chance de rejeição
                params = {
                    'fields': 'status_code'
                }
                
                data = self._make_request('GET', f"{container_id}", params=params)
                if not data:
                    logger.warning(f"Failed to get container status (attempt {attempt + 1}/{max_attempts})")
                    time.sleep(delay)
                    continue
                
                status_code = data.get('status_code', '')
                logger.info(f"Container status check (attempt {attempt + 1}/{max_attempts}): {status_code}")
                
                if status_code == 'FINISHED':
                    return status_code
                    
                elif status_code == 'IN_PROGRESS':
                    # Container still processing, continue waiting
                    time.sleep(delay)
                    continue
                    
                elif status_code == 'ERROR':
                    logger.error(f"Container failed with error status")
                    
                    # Tenta obter detalhes do erro em uma chamada separada
                    try:
                        error_details = self._make_request('GET', f"{container_id}", params={'fields': 'status'})
                        logger.error(f"Error details: {error_details}")
                    except Exception as detail_err:
                        logger.error(f"Could not get error details: {str(detail_err)}")
                    
                    return 'ERROR'
                    
                elif status_code == 'EXPIRED':
                    logger.error("Container expired before publishing")
                    return 'EXPIRED'
                    
                else:
                    # Unknown status code
                    logger.warning(f"Unknown status code: {status_code}")
                    if attempt < max_attempts - 1:
                        time.sleep(delay)
                        continue
                    return 'UNKNOWN'
                    
            except RateLimitError as e:
                logger.warning(f"Rate limit hit while checking status. Waiting {e.retry_seconds}s...")
                time.sleep(e.retry_seconds)
                
            except InstagramAPIError as e:
                logger.error(f"API Error when checking container status: {str(e)}")
                
                # Se for um erro 400 Bad Request, tente com um conjunto diferente de campos
                if 'Bad Request' in str(e):
                    logger.warning("Trying alternative approach due to 400 error...")
                    try:
                        # Tente uma abordagem ainda mais simples
                        time.sleep(5)
                        alternative_data = self._make_request('GET', f"{container_id}", params={})
                        logger.info(f"Alternative check response: {alternative_data}")
                        
                        # Se conseguiu acessar o container de alguma forma, considere pronto após alguns checks
                        if alternative_data and (attempt > 3):
                            logger.info("Container appears to be accessible, considering it ready")
                            return 'FINISHED'
                    except Exception as alt_err:
                        logger.error(f"Alternative check also failed: {str(alt_err)}")
                
                if attempt < max_attempts - 1:
                    # Aumento no tempo de espera para erros 400
                    backoff_time = delay * 2
                    logger.info(f"Will retry after {backoff_time}s...")
                    time.sleep(backoff_time)
                    continue
                
                return 'BAD_REQUEST'
                
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

        if self._rate_limit_state.should_backoff():
            wait_time = self._rate_limit_state.get_backoff_time()
            logger.warning(f"Still in backoff period. Waiting {wait_time:.1f} seconds...")
            time.sleep(wait_time)
            
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
                
                # Reset rate limit state on success
                self._rate_limit_state = RateLimitState()
                
                return post_id

            logger.error(f"Failed to publish carousel. Response: {result}")
            return None
            
        except PermissionError as e:
            if "request limit reached" in str(e).lower():
                self._handle_rate_limit()
                raise
            raise
            
        except Exception as e:
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

    def _validate_media(self, media_url: str) -> bool:
        """Validates media URL and type before uploading."""
        try:
            import requests
            
            logger.info(f"Validating media URL: {media_url}")
            
            # Add headers to mimic browser request
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Accept': 'image/jpeg, image/png, */*'
            }
            
            response = requests.head(media_url, timeout=20, headers=headers)
            
            if response.status_code != 200:
                logger.error(f"Media URL not accessible: {media_url}, status code: {response.status_code}")
                return False
                
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
            
        except Exception as e:
            logger.error(f"Error validating media: {str(e)}")
            return False

    def _validate_token(self, force_check=False):
        """Validates the access token and retrieves its expiration time."""
        try:
            logger.info(f"Validating Instagram token (force_check={force_check})")
            logger.info(f"Using Instagram Account ID: {self.ig_user_id}")
            
            response = self._make_request(
                "GET",
                "debug_token",
                params={"input_token": self.access_token}
            )
            
            if response and 'data' in response and response['data'].get('is_valid'):
                logger.info("Token validated successfully")
                
                # Check scopes
                scopes = response['data'].get('scopes', [])
                if 'instagram_basic' not in scopes:
                    logger.warning("Token missing 'instagram_basic' permission")
                if 'instagram_content_publish' not in scopes:
                    logger.warning("Token missing 'instagram_content_publish' permission")
                
                # Store expiration
                self.token_expires_at = response['data'].get('expires_at')
                if self.token_expires_at:
                    from datetime import datetime
                    logger.info(f"Token expires at: {datetime.fromtimestamp(self.token_expires_at)}")
                
                return True
            else:
                logger.error("Token validation failed")
                raise AuthenticationError("Invalid or expired access token")
                
        except Exception as e:
            logger.error(f"Error validating token: {str(e)}")
            raise

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

    def _handle_rate_limit(self):
        """Handle rate limiting with exponential backoff"""
        delay = self._rate_limit_state.record_error()
        logger.warning(f"Rate limit hit. Backing off for {delay:.1f} seconds...")
        time.sleep(delay)

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
            
            # Update the .env file
            self._update_env_file("INSTAGRAM_API_KEY", self.access_token)
        except Exception as e:
            logger.error(f"Error refreshing token: {str(e)}")
            raise

    def _update_env_file(self, key: str, new_value: str):
        """Updates the .env file with the new token (use with caution)."""
        try:
            env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
            if not os.path.exists(env_path):
                logger.warning(f"No .env file found at {env_path}")
                return

            # Read current contents
            with open(env_path, 'r') as f:
                lines = f.readlines()

            # Update the specific key
            key_found = False
            for i, line in enumerate(lines):
                if line.startswith(f"{key}="):
                    lines[i] = f"{key}={new_value}\n"
                    key_found = True
                    break

            # Add key if not found
            if not key_found:
                lines.append(f"\n{key}={new_value}\n")

            # Write back
            with open(env_path, 'w') as f:
                f.writelines(lines)

            logger.info(f"Updated {key} in .env file")
        except Exception as e:
            logger.error(f"Failed to update .env file: {str(e)}")