import os
import time
import json
import logging
import random
import requests
import traceback
from datetime import datetime
from dotenv import load_dotenv
from src.instagram.base_instagram_service import (
    BaseInstagramService, AuthenticationError, PermissionError,
    RateLimitError, MediaError, TemporaryServerError, InstagramAPIError
)
from src.instagram.base_instagram_service import RateLimitHandler
from typing import Dict, Optional, Any
from pathlib import Path
from .image_validator import InstagramImageValidator
from .exceptions import InstagramError, RateLimitError
from ..utils.config import Config  # Added missing import


logger = logging.getLogger('InstagramPostService')

class InstagramPostService(BaseInstagramService):
    """Service for posting single images to Instagram"""
    
    def __init__(self):
        super().__init__()
        self.validator = InstagramImageValidator()
        
    async def post_image(
        self,
        image_path: str,
        caption: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Post a single image to Instagram
        
        Args:
            image_path: Path to image file
            caption: Caption for the image
            **kwargs: Additional options (location, user tags, etc)
            
        Returns:
            Dict containing post result or error details
        """
        try:
            # Validate and process image
            validation = self.validator.process_single_photo(image_path)
            if validation["status"] == "error":
                raise InstagramError(validation["message"])
                
            processed_path = validation["image_path"]
            
            # Upload the image
            container = await self._upload_photo(processed_path)
            if not container or "id" not in container:
                raise InstagramError("Failed to upload image")
                
            # Update the container with caption and other metadata
            container = await self._update_container(
                container["id"],
                caption,
                **kwargs
            )
            
            if not container or "id" not in container:
                raise InstagramError("Failed to update media container")
                
            # Publish the post
            result = await self._publish_post(container["id"])
            if not result or "id" not in result:
                raise InstagramError("Failed to publish post")
                
            return {
                "status": "success",
                "id": result["id"],
                "media_type": "IMAGE",
                "permalink": result.get("permalink")
            }
            
        except RateLimitError:
            raise  # Re-raise rate limit errors
        except Exception as e:
            logger.error(f"Error posting image: {e}")
            raise InstagramError(f"Failed to post image: {str(e)}")
            
    async def _update_container(
        self,
        container_id: str,
        caption: str,
        **kwargs
    ) -> Optional[Dict]:
        """Update a media container with metadata"""
        try:
            endpoint = f"/{container_id}"
            
            params = {
                "caption": caption
            }
            
            # Add optional parameters
            if "location_id" in kwargs:
                params["location_id"] = kwargs["location_id"]
                
            if "user_tags" in kwargs:
                params["user_tags"] = kwargs["user_tags"]
                
            result = await self._make_request("POST", endpoint, params=params)
            return result
            
        except Exception as e:
            logger.error(f"Error updating container: {e}")
            return None
            
    async def _publish_post(self, container_id: str) -> Optional[Dict]:
        """Publish a prepared media container"""
        try:
            endpoint = f"/{self.instagram_account_id}/media_publish"
            
            params = {
                "creation_id": container_id
            }
            
            result = await self._make_request("POST", endpoint, params=params)
            return result
            
        except Exception as e:
            logger.error(f"Error publishing post: {e}")
            return None

    # Singleton and cache settings
    _instance = None
    _state_cache = None
    _last_state_save = 0
    _state_save_interval = 60  # Save state every 60 seconds max

    # Rate limiting settings
    _rate_limit_cache = {}
    _rate_limit_window = 3600  # 1 hour window
    _max_requests_per_window = 200
    _min_request_interval = 2  # Minimum seconds between requests

    # Published containers tracking
    _published_containers = set()
    _last_verification_time = 0
    _verification_interval = 300  # Verify published posts every 5 minutes

    def __new__(cls, access_token=None, ig_user_id=None, skip_token_validation=False):
        # Padrão Singleton para evitar múltiplas instanciações e carregamentos de estado
        if cls._instance is None:
            cls._instance = super(InstagramPostService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, access_token=None, ig_user_id=None, skip_token_validation=False):
        # Evita reinicialização se já inicializado
        if getattr(self, '_initialized', False):
            return

        load_dotenv()
        # Store these values to update Config before calling super().__init__()
        access_token = access_token or (
            os.getenv('INSTAGRAM_API_KEY') or
            os.getenv('INSTAGRAM_ACCESS_TOKEN') or
            os.getenv('FACEBOOK_ACCESS_TOKEN')
        )
        ig_user_id = ig_user_id or os.getenv("INSTAGRAM_ACCOUNT_ID")

        if not access_token or not ig_user_id:
            raise ValueError(
                "Credenciais incompletas. Defina INSTAGRAM_API_KEY e "
                "INSTAGRAM_ACCOUNT_ID nas variáveis de ambiente ou forneça-os diretamente."
            )

        # Update Config with provided credentials
        config = Config.get_instance()
        config.INSTAGRAM_ACCESS_TOKEN = access_token
        config.INSTAGRAM_ACCOUNT_ID = ig_user_id

        # Now call super().__init__() which will use the updated Config
        super().__init__()
        
        self.state_file = 'api_state.json'
        self.pending_containers = {}
        self.published_containers_file = 'published_containers.json'
        self.stats = {
            'successful_posts': 0,
            'failed_posts': 0,
            'rate_limited_posts': 0
        }
        self.skip_token_validation = skip_token_validation
        self._load_state()
        self._load_published_containers()

        self._initialized = True

    def _load_state(self):
        """Load persisted state from file"""
        # Use o cache se disponível
        if self.__class__._state_cache is not None:
            self.pending_containers = self.__class__._state_cache.get('pending_containers', {})
            self.stats = self.__class__._state_cache.get('stats', {
                'successful_posts': 0,
                'failed_posts': 0,
                'rate_limited_posts': 0
            })
            return

        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    self.pending_containers = state.get('pending_containers', {})
                    self.stats = state.get('stats', {
                        'successful_posts': 0,
                        'failed_posts': 0,
                        'rate_limited_posts': 0
                    })
                    # Armazenar no cache
                    self.__class__._state_cache = {
                        'pending_containers': self.pending_containers,
                        'stats': self.stats
                    }
                    logger.info(f"Loaded {len(self.pending_containers)} pending containers from state file")
        except Exception as e:
            logger.error(f"Error loading state: {e}")
            self.pending_containers = {}
            self.stats = {
                'successful_posts': 0,
                'failed_posts': 0,
                'rate_limited_posts': 0
            }
            # Inicializar o cache com valores vazios
            self.__class__._state_cache = {
                'pending_containers': self.pending_containers,
                'stats': self.stats
            }

    def _load_published_containers(self):
        """Load list of already published containers"""
        try:
            if os.path.exists(self.published_containers_file):
                with open(self.published_containers_file, 'r') as f:
                    published_data = json.load(f)
                    self.__class__._published_containers = set(published_data.get('containers', []))
                    logger.info(f"Loaded {len(self.__class__._published_containers)} published container IDs")
        except Exception as e:
            logger.error(f"Error loading published containers: {e}")
            self.__class__._published_containers = set()

    def _save_published_containers(self):
        """Save list of published containers to prevent duplicates"""
        try:
            published_data = {
                'containers': list(self.__class__._published_containers),
                'last_updated': datetime.now().isoformat()
            }

            with open(self.published_containers_file, 'w') as f:
                json.dump(published_data, f, indent=2)

            logger.info(f"Saved {len(self.__class__._published_containers)} published container IDs")
        except Exception as e:
            logger.error(f"Error saving published containers: {e}")

    def _save_state(self):
        """Save current state to file"""
        current_time = time.time()

        # Só salva o estado se passou tempo suficiente desde o último salvamento
        if current_time - self.__class__._last_state_save < self.__class__._state_save_interval:
            # Atualiza o cache sem salvar no disco
            self.__class__._state_cache = {
                'pending_containers': self.pending_containers,
                'stats': self.stats
            }
            return

        try:
            state = {
                'pending_containers': self.pending_containers,
                'stats': self.stats,
                'last_updated': datetime.now().isoformat()
            }

            # Atualiza o cache
            self.__class__._state_cache = {
                'pending_containers': self.pending_containers,
                'stats': self.stats
            }

            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)

            # Atualiza o timestamp do último salvamento
            self.__class__._last_state_save = current_time
            logger.info(f"Saved state with {len(self.pending_containers)} pending containers")
        except Exception as e:
            logger.error(f"Error saving state: {e}")

    def _update_stats(self, success=False, rate_limited=False):
        """Update posting statistics"""
        if success:
            self.stats['successful_posts'] += 1
        elif rate_limited:
            self.stats['rate_limited_posts'] += 1
        else:
            self.stats['failed_posts'] += 1
        # Só atualiza o cache, não salva no disco a cada atualização
        self.__class__._state_cache = {
            'pending_containers': self.pending_containers,
            'stats': self.stats
        }

    def _is_container_published(self, container_id):
        """Check if a container has already been published"""
        # First check our in-memory set
        if container_id in self.__class__._published_containers:
            logger.warning(f"Container {container_id} already marked as published! Skipping publication.")
            return True
            
        # For most cases, we'll rely on our local tracking
        # We'll only check Instagram for verification in special situations
        # This avoids unnecessary API calls that might hit rate limits
        
        try:
            # Use our enhanced verification system that can detect recent publications
            from src.instagram.publication_verifier import InstagramPublicationVerifier
            verifier = InstagramPublicationVerifier(self)
            is_published, post_id = verifier.verify_publication(container_id)
            
            if is_published:
                # Add to our published set
                logger.warning(f"Container {container_id} was already published on Instagram! Marking as published.")
                self.__class__._published_containers.add(container_id)
                self._save_published_containers()
                return True
        except Exception as e:
            logger.error(f"Error verifying publication status: {str(e)}")
            # Continue with local check on verification failure
            
            # If this container is in the pending list with retry attempts, we should 
            # be more cautious about potential duplicates
            if container_id in self.pending_containers:
                retry_count = self.pending_containers[container_id].get('retry_count', 0)
                if retry_count >= 2:
                    logger.warning(f"Container {container_id} has been retried {retry_count} times. Being cautious and marking as published to prevent duplicates.")
                    self.__class__._published_containers.add(container_id)
                    self._save_published_containers()
                    return True

        # Default to not published
        return False

    def _process_pending_containers(self, limit=5):
        """Process any pending containers from previous runs with limit para evitar bloqueios longos"""
        if not self.pending_containers:
            return

        logger.info(f"Found {len(self.pending_containers)} pending containers to process")
        processed_containers = []
        processed_count = 0

        # Ordenar por próxima tentativa para processar primeiro os que já estão prontos
        sorted_containers = sorted(
            self.pending_containers.items(),
            key=lambda x: float(x[1].get('next_attempt_time', 0))
        )

        for container_id, container_data in sorted_containers:
            # Limitar o número de containers processados de uma vez
            if processed_count >= limit:
                logger.info(f"Reached limit of {limit} containers to process at once")
                break

            # Skip containers that are already published
            if self._is_container_published(container_id):
                logger.info(f"Container {container_id} already published, removing from pending list")
                processed_containers.append(container_id)
                continue

            try:
                # Check if we're still within the backoff period
                if container_data.get('next_attempt_time'):
                    next_attempt_time = float(container_data['next_attempt_time'])
                    if time.time() < next_attempt_time:
                        wait_time = next_attempt_time - time.time()
                        logger.info(f"Container {container_id} still in backoff period. Next attempt in {wait_time:.1f}s")
                        continue

                # Check container status first
                status = self.check_container_status(container_id)
                if status != 'FINISHED':
                    logger.warning(f"Container {container_id} not ready for publishing, status: {status}")
                    if status in ['ERROR', 'EXPIRED', 'TIMEOUT']:
                        processed_containers.append(container_id)
                    continue

                # Attempt to publish
                logger.info(f"Attempting to publish pending container: {container_id}")
                post_id = self._attempt_publish_media(container_id)
                processed_count += 1

                if post_id:
                    logger.info(f"Successfully published pending container! ID: {post_id}")
                    processed_containers.append(container_id)

                    # Mark as published to prevent duplicates
                    self.__class__._published_containers.add(container_id)
                    self._save_published_containers()

                    # Get permalink
                    permalink = self.get_post_permalink(post_id)

                    # If we have a callback URL in the container data, notify it
                    if container_data.get('callback_url'):
                        try:
                            # Simplified callback, implement as needed
                            pass
                        except Exception as callback_err:
                            logger.error(f"Error calling callback: {callback_err}")

            except RateLimitError as e:
                # Update next attempt time and retry count
                retry_count = container_data.get('retry_count', 0) + 1
                next_attempt_time = time.time() + e.retry_seconds

                self.pending_containers[container_id].update({
                    'retry_count': retry_count,
                    'next_attempt_time': next_attempt_time,
                    'last_error': str(e),
                    'last_attempt': datetime.now().isoformat()
                })
                logger.warning(f"Rate limit hit for container {container_id}. Will retry after {e.retry_seconds}s (attempt {retry_count})")

                # If we've retried too many times, give up
                if retry_count >= 5:
                    logger.error(f"Too many retry attempts for container {container_id}, giving up")
                    processed_containers.append(container_id)

            except Exception as e:
                # Registra detalhes completos do erro para diagnóstico
                error_details = traceback.format_exc()
                logger.error(f"Error processing pending container {container_id}: {e}\n{error_details}")

                # Verifica se, apesar do erro, a publicação foi bem-sucedida
                try:
                    # Tenta verificar se o container ainda existe no Instagram
                    status = self.check_container_status(container_id)

                    # Check if it's already published despite the error
                    if self._is_container_published(container_id):
                        processed_containers.append(container_id)
                        continue

                    # Se o status for None ou um código de erro, considera que falhou
                    if status is None or status in ['ERROR', 'EXPIRED', 'TIMEOUT']:
                        logger.error(f"Container {container_id} falhou e será removido da lista de pendentes.")
                        processed_containers.append(container_id)
                    else:
                        # Se o status for FINISHED, talvez tenha sido publicado com sucesso mas tivemos um erro depois
                        # ou se o status for IN_PROGRESS, podemos deixar para uma próxima tentativa
                        logger.info(f"Apesar do erro, o container {container_id} ainda tem status {status}. Será mantido na lista de pendentes.")

                        # Incrementa o contador de tentativas para não tentar indefinidamente
                        retry_count = container_data.get('retry_count', 0) + 1
                        self.pending_containers[container_id].update({
                            'retry_count': retry_count,
                            'last_error': str(e),
                            'last_attempt': datetime.now().isoformat()
                        })

                        # Se já tentamos muitas vezes, remove de qualquer forma
                        if retry_count >= 5:
                            logger.error(f"Too many retry attempts for container {container_id}, giving up")
                            processed_containers.append(container_id)
                except Exception as check_err:
                    # Se não conseguimos nem verificar o status, é melhor remover
                    logger.error(f"Falha ao verificar status do container {container_id} após erro: {check_err}")
                    processed_containers.append(container_id)

        # Remove processed containers from pending list
        if processed_containers:
            for container_id in processed_containers:
                self.pending_containers.pop(container_id, None)

            # Save updated state
            self._save_state()

        return len(processed_containers)

    def create_media_container(self, image_url, caption):
        """Creates a media container for the post."""
        params = {
            'image_url': image_url,
            'caption': caption[:2200] if caption else '',  # Instagram caption limit
            'media_type': 'IMAGE'
        }

        # Validate URL before attempting to create container
        try:
            import requests
            from PIL import Image
            import io

            # Add headers to mimic browser request
            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'image/jpeg, image/png, */*'
            }
            
            # First check if URL is accessible
            response = requests.head(image_url, timeout=10, headers=headers)
            if response.status_code != 200:
                logger.error(f"Image URL not accessible: {image_url}")
                return None

            content_type = response.headers.get('content-type', '').lower()
            if not any(supported in content_type for supported in ['image/jpeg', 'image/png']):
                logger.error(f"Unsupported media type: {content_type}")
                return None

            # Download and validate the actual image
            img_response = requests.get(image_url, timeout=10, headers=headers)
            img = Image.open(io.BytesIO(img_response.content))
            
            # Check dimensions
            width, height = img.size
            if width < 320 or height < 320:
                logger.error(f"Image too small: {width}x{height}")
                return None
                
            # Check aspect ratio
            aspect_ratio = width / height
            if aspect_ratio < 0.8 or aspect_ratio > 1.91:
                logger.error(f"Invalid aspect ratio: {aspect_ratio:.2f}")
                return None

        except Exception as e:
            logger.error(f"Failed to validate image URL: {e}")
            return None

        retry_count = 0
        max_retries = 3
        base_delay = 5

        while retry_count < max_retries:
            try:
                logger.info(f"Creating media container with params: {params}")
                result = self._make_request('POST', f"{self.ig_user_id}/media", data=params)
                
                if result and 'id' in result:
                    container_id = result['id']
                    logger.info(f"Media container created with ID: {container_id}")
                    return container_id
                
                logger.error(f"Failed to create container, response: {result}")
                
            except RateLimitError as e:
                retry_after = getattr(e, 'retry_seconds', base_delay * (2 ** retry_count))
                if retry_count < max_retries - 1:
                    logger.warning(f"Rate limit hit. Waiting {retry_after}s before retry...")
                    time.sleep(retry_after)
                else:
                    raise
                    
            except InstagramAPIError as e:
                if hasattr(e, 'error_code') and e.error_code == 400:
                    logger.error(f"Bad Request error: {str(e)}")
                    return None
                raise
                    
            retry_count += 1
            if retry_count < max_retries:
                delay = base_delay * (2 ** retry_count)
                logger.info(f"Retrying container creation in {delay}s...")
                time.sleep(delay)

        logger.error("Failed to create media container after all retries")
        return None

    def check_container_status(self, container_id):
        """Verifica o status do container de mídia."""
        params = {
            'fields': 'status_code,status'
        }

        try:
            result = self._make_request('GET', f"{container_id}", params=params)
            if result:
                status = result.get('status_code')
                logger.info(f"Status do container: {status}")
                if status == 'ERROR' and 'status' in result:
                    logger.error(f"Detalhes do erro: {result['status']}")
                return status
            return None
        except InstagramAPIError as e:
            logger.error(f"Failed to check container status: {e}")
            raise

    def wait_for_container_status(self, container_id, max_attempts=10, delay=10):
        """Aguarda o container estar pronto, com backoff exponencial."""
        for attempt in range(max_attempts):
            try:
                status = self.check_container_status(container_id)
                if status == 'FINISHED':
                    logger.info(f"Container pronto para publicação após {attempt+1} verificações")
                    return status
                elif status in ['ERROR', 'EXPIRED']:
                    logger.error(f"Container falhou com status: {status}")
                    return status

                # Usar backoff exponencial com tempo máximo reduzido para não bloquear por muito tempo
                backoff_time = min(delay * (1.5 ** attempt) + random.uniform(0, 3), 30)

                logger.info(f"Tentativa {attempt + 1}/{max_attempts}. Aguardando {backoff_time:.1f}s...")
                time.sleep(backoff_time)

            except RateLimitError as e:
                logger.warning(f"Rate limit hit while checking status. Waiting {e.retry_seconds}s...")
                time.sleep(min(e.retry_seconds, 30))  # Limitar o tempo máximo de espera para não bloquear a thread
            except Exception as e:
                logger.error(f"Error checking container status: {str(e)}")
                time.sleep(min(delay, 10))  # Tempo máximo limitado

        logger.error(f"Container status check timed out after {max_attempts} attempts.")
        return 'TIMEOUT'

    def _attempt_publish_media(self, container_id):
        """Internal method to attempt media publication without duplicate checking"""
        params = {
            'creation_id': container_id,
        }

        try:
            logger.info(f"Publishing media with params: {params}")
            result = self._make_request('POST', f"{self.ig_user_id}/media_publish", data=params)

            if result and 'id' in result:
                post_id = result['id']
                logger.info(f"Publication initiated with ID: {post_id}")
                self._update_stats(success=True)
                return post_id

            logger.error(f"Could not publish media. Response: {result}")
            self._update_stats(success=False)
            return None

        except RateLimitError as e:
            logger.warning(f"Rate limit hit. Retrying after {e.retry_seconds} seconds.")
            time.sleep(e.retry_seconds)
            return self._attempt_publish_media(container_id)

        except InstagramAPIError as e:
            logger.error(f"Error publishing media: {e}")
            self._update_stats(success=False)
            raise

    def publish_media(self, container_id):
        return self._attempt_publish_media(container_id)

    # ...
    # other unchanged methods now come here...
    
    def _make_request(self, method, endpoint, params=None, data=None, headers=None, retry_attempt=0):
        """Make an API request with enhanced rate limiting and error handling"""
        url = f"{self.base_url}/{endpoint}"

        # Add access token to params
        if params is None:
            params = {}
        params['access_token'] = self.access_token

        # Check rate limits
        current_time = time.time()
        if not self._check_rate_limits(current_time):
            retry_after = self._get_rate_limit_reset_time() - current_time
            raise RateLimitError(
                "Rate limit exceeded",
                retry_seconds=retry_after,
                error_code="API_LIMIT",
                error_subcode="HOURLY_LIMIT"
            )

        # Respect minimum interval between requests
        elapsed = current_time - self.last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)

        try:
            logger.info(f"Making {method} request to {endpoint}")
            if data:
                logger.info(f"With data: {data}")

            response = self.session.request(method, url, params=params, data=data, headers=headers)
            self.last_request_time = time.time()
            self._update_rate_limits(response.headers)

            response.raise_for_status()
            result = response.json() if response.content else None

            if result and 'error' in result:
                error = result['error']
                error_code = error.get('code')
                error_message = error.get('message', '')
                error_subcode = error.get('error_subcode')
                fb_trace_id = error.get('fbtrace_id')

                if error_code in [190, 104]:  # Token errors
                    raise AuthenticationError(error_message, error_code, error_subcode, fb_trace_id)
                elif error_code in [200, 10, 803]:  # Permission errors
                    raise PermissionError(error_message, error_code, error_subcode, fb_trace_id)
                elif self._is_rate_limit_error(error_code, error_subcode):
                    retry_seconds = self._get_retry_after(error)
                    if retry_attempt < 3:  # Max 3 retries
                        backoff_time = min(retry_seconds * (2 ** retry_attempt), 3600)
                        logger.warning(f"Rate limit hit. Backing off for {backoff_time:.2f}s")
                        time.sleep(backoff_time)
                        return self._make_request(method, endpoint, params, data, headers, retry_attempt + 1)
                    raise RateLimitError(error_message, retry_seconds, error_code, error_subcode, fb_trace_id)
                else:
                    raise InstagramAPIError(error_message, error_code, error_subcode, fb_trace_id)

            return result

        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            if retry_attempt < 3 and isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
                backoff_time = self._min_request_interval * (2 ** retry_attempt)
                logger.info(f"Retrying after {backoff_time}s due to connection error")
                time.sleep(backoff_time)
                return self._make_request(method, endpoint, params, data, headers, retry_attempt + 1)
            raise InstagramAPIError(f"Request failed: {str(e)}")

    def _check_rate_limits(self, current_time: float) -> bool:
        """Check if we're within rate limits"""
        window_start = current_time - self._rate_limit_window
        # Clean up old entries
        self._rate_limit_cache = {
            ts: count for ts, count in self._rate_limit_cache.items()
            if ts > window_start
        }
        # Count requests in current window
        request_count = sum(self._rate_limit_cache.values())
        return request_count < self._max_requests_per_window

    def _update_rate_limits(self, headers: dict):
        """Update rate limit tracking based on response headers"""
        current_time = time.time()
        self._rate_limit_cache[current_time] = 1
        
        # Process Instagram's rate limit headers if present
        if 'x-app-usage' in headers:
            try:
                usage = json.loads(headers['x-app-usage'])
                if usage.get('call_count', 0) > 95:  # Over 95% of limit
                    logger.warning("Approaching API rate limit")
            except:
                pass

    def _get_rate_limit_reset_time(self) -> float:
        """Get when the current rate limit window will reset"""
        if not self._rate_limit_cache:
            return time.time()
        oldest_request = min(self._rate_limit_cache.keys())
        return oldest_request + self._rate_limit_window

    def _is_rate_limit_error(self, error_code: int, error_subcode: int) -> bool:
        """Check if an error is rate-limit related"""
        rate_limit_codes = [4, 17, 32, 613]
        rate_limit_subcodes = [2207001, 2207003]
        return (error_code in rate_limit_codes or 
                error_subcode in rate_limit_subcodes or
                'rate limit' in str(error_code).lower())

    def _get_retry_after(self, error: dict) -> int:
        """Extract retry after time from error response"""
        # Try to get from error response
        retry_after = error.get('retry_after')
        if retry_after:
            return int(retry_after)
        
        # Default backoff times based on error type
        error_code = error.get('code')
        if error_code in [4, 17]:  # Application-level rate limit
            return 3600  # 1 hour
        elif error_code in [32, 613]:  # User-level rate limit
            return 600  # 10 minutes
        return 60  # Default 1 minute

