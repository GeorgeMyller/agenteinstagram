import os
import time
import json
import logging
import random
import requests
import traceback
from datetime import datetime
from dotenv import load_dotenv
from imgurpython import ImgurClient
from src.instagram.base_instagram_service import (
    BaseInstagramService, AuthenticationError, PermissionError,
    RateLimitError, MediaError, TemporaryServerError, InstagramAPIError
)
from src.instagram.base_instagram_service import RateLimitHandler


logger = logging.getLogger('InstagramPostService')

class InstagramPostService(BaseInstagramService):
    """Service for posting images to Instagram."""

    # Cache para evitar operações de I/O frequentes
    _instance = None
    _state_cache = None
    _last_state_save = 0
    _state_save_interval = 60  # Salvar estado a cada 60 segundos no máximo

    # Track published containers to prevent duplicates
    _published_containers = set()
    _last_verification_time = 0
    _verification_interval = 300  # Verify published posts every 5 minutes

    def __new__(cls, access_token=None, ig_user_id=None):
        # Padrão Singleton para evitar múltiplas instanciações e carregamentos de estado
        if cls._instance is None:
            cls._instance = super(InstagramPostService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, access_token=None, ig_user_id=None):
        # Evita reinicialização se já inicializado
        if getattr(self, '_initialized', False):
            return

        load_dotenv()
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

        super().__init__(access_token, ig_user_id)
        self.state_file = 'api_state.json'
        self.pending_containers = {}
        self.published_containers_file = 'published_containers.json'
        self.stats = {
            'successful_posts': 0,
            'failed_posts': 0,
            'rate_limited_posts': 0
        }
        self._load_state()
        self._load_published_containers()

        # Processamento de containers pendentes sob demanda em vez de automático
        # (será chamado explicitamente quando necessário)
        # self._process_pending_containers()

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
            'caption': caption,
            'media_type': 'IMAGE'  # Explicitamente definindo como IMAGE
        }

        try:
            logger.info(f"Creating media container with params: {params}")  # Log params
            result = self._make_request('POST', f"{self.ig_user_id}/media", data=params)
            if result and 'id' in result:
                container_id = result['id']
                logger.info(f"Media container created with ID: {container_id}")
                return container_id
            logger.error("Failed to create media container")
            return None
        except InstagramAPIError as e:
            logger.error(f"Failed to create media container: {e}")
            raise

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

        # Respect rate limits with minimum interval between requests
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)

        try:
            logger.info(f"Making {method} request to {endpoint}")
            if data:
                logger.info(f"With data: {data}")

            response = self.session.request(method, url, params=params, data=data, headers=headers)
            self.last_request_time = time.time()

            # Process rate limit headers if present
            if 'x-business-use-case-usage' in response.headers:
                self._process_rate_limit_headers(response.headers)

            # Log response status
            logger.info(f"Response status: {response.status_code}")

            if response.status_code == 403:
                try:
                    error_json = response.json()
                    if 'error' in error_json:
                        error = error_json['error']
                        error_code = error.get('code')
                        error_subcode = error.get('error_subcode')
                        error_message = error.get('message', '')
                        fb_trace_id = error.get('fbtrace_id')

                        logger.error(f"{error_code} {error_message} (Subcode: {error_subcode})")

                        # Handle application request limit specifically
                        if error_subcode == 2207051:
                            retry_seconds = self._get_retry_after(error)
                            if retry_attempt < RateLimitHandler.MAX_ATTEMPTS:
                                backoff_time = RateLimitHandler.calculate_backoff_time(retry_attempt, retry_seconds)
                                logger.warning(f"Application request limit reached. Backing off for {backoff_time:.2f} seconds. Attempt {retry_attempt+1}/{RateLimitHandler.MAX_ATTEMPTS}")
                                time.sleep(backoff_time)
                                return self._make_request(method, endpoint, params, data, headers, retry_attempt + 1)

                            raise RateLimitError(error_message, retry_seconds, error_code, error_subcode, fb_trace_id)

                        raise PermissionError(error_message, error_code, error_subcode, fb_trace_id)

                except ValueError:
                    raise InstagramAPIError("Failed to parse error response")

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
                elif RateLimitHandler.is_rate_limit_error(error_code, error_subcode):
                    retry_seconds = self._get_retry_after(error)
                    if retry_attempt < RateLimitHandler.MAX_ATTEMPTS:
                        backoff_time = RateLimitHandler.calculate_backoff_time(retry_attempt, retry_seconds)
                        logger.warning(f"Rate limit hit. Backing off for {backoff_time:.2f} seconds. Attempt {retry_attempt+1}/{RateLimitHandler.MAX_ATTEMPTS}")
                        time.sleep(backoff_time)
                        return self._make_request(method, endpoint, params, data, headers, retry_attempt + 1)
                    raise RateLimitError(error_message, retry_seconds, error_code, error_subcode, fb_trace_id)
                elif error_code in [1, 2]:  # Temporary server errors
                    raise TemporaryServerError(error_message, error_code, error_subcode, fb_trace_id)
                else:
                    raise InstagramAPIError(error_message, error_code, error_subcode, fb_trace_id)

            return result

        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            raise InstagramAPIError(f"Request failed: {str(e)}")

    def _get_retry_after(self, error):
        """Extract retry after time from error response"""
        retry_seconds = 300  # Default retry time increased to 5 minutes for application request limit

        # Check for specific error subcodes
        if error.get('error_subcode') == 2207051:  # Application request limit
            retry_seconds = 900  # 15 minutes

        # Try to extract time from error message
        message = error.get('message', '').lower()
        if 'minutes' in message:
            try:
                import re
                time_match = re.search(r'(\d+)\s*minutes?', message)
                if time_match:
                    retry_seconds = int(time_match.group(1)) * 60
            except:
                pass

        return retry_seconds

