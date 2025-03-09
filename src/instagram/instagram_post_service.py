import os
import time
import json
import logging
import random
from datetime import datetime
from dotenv import load_dotenv
from imgurpython import ImgurClient
from src.instagram.base_instagram_service import (
    BaseInstagramService, AuthenticationError, PermissionError,
    RateLimitError, MediaError, TemporaryServerError, InstagramAPIError
)

logger = logging.getLogger('InstagramPostService')

class InstagramPostService(BaseInstagramService):
    """Service for posting images to Instagram."""

    def __init__(self, access_token=None, ig_user_id=None):
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
        self._load_state()
        
        # Attempt to process any pending containers from previous runs
        self._process_pending_containers()

    def _load_state(self):
        """Load persisted state from file"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    self.pending_containers = state.get('pending_containers', {})
                    logger.info(f"Loaded {len(self.pending_containers)} pending containers from state file")
        except Exception as e:
            logger.error(f"Error loading state: {e}")
            self.pending_containers = {}

    def _save_state(self):
        """Save current state to file"""
        try:
            state = {
                'pending_containers': self.pending_containers,
                'last_updated': datetime.now().isoformat()
            }
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
            logger.info(f"Saved state with {len(self.pending_containers)} pending containers")
        except Exception as e:
            logger.error(f"Error saving state: {e}")

    def _process_pending_containers(self):
        """Process any pending containers from previous runs"""
        if not self.pending_containers:
            return
            
        logger.info(f"Found {len(self.pending_containers)} pending containers to process")
        processed_containers = []
        
        for container_id, container_data in list(self.pending_containers.items()):
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
                post_id = self.publish_media(container_id)
                
                if post_id:
                    logger.info(f"Successfully published pending container! ID: {post_id}")
                    processed_containers.append(container_id)
                    
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
                logger.error(f"Error processing pending container {container_id}: {e}")
                processed_containers.append(container_id)
        
        # Remove processed containers from pending list
        for container_id in processed_containers:
            self.pending_containers.pop(container_id, None)
            
        # Save updated state
        self._save_state()

    def create_media_container(self, image_url, caption):
        """Creates a media container for the post."""
        params = {
            'image_url': image_url,
            'caption': caption,
            'media_type': 'IMAGE'  # Explicitamente definindo como IMAGE
        }

        try:
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

    def wait_for_container_status(self, container_id, max_attempts=30, delay=10):
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
                
                # Usar backoff exponencial como no ReelsPublisher
                backoff_time = delay * (1.5 ** attempt) + random.uniform(0, 3)
                max_backoff = 45  # Limitar o tempo máximo de espera
                backoff_time = min(backoff_time, max_backoff)
                
                logger.info(f"Tentativa {attempt + 1}/{max_attempts}. Aguardando {backoff_time:.1f}s...")
                time.sleep(backoff_time)
                
            except RateLimitError as e:
                logger.warning(f"Rate limit hit while checking status. Waiting {e.retry_seconds}s...")
                time.sleep(e.retry_seconds)
            except Exception as e:
                logger.error(f"Error checking container status: {str(e)}")
                time.sleep(delay)
        
        logger.error(f"Container status check timed out after {max_attempts} attempts.")
        return 'TIMEOUT'

    def publish_media(self, media_container_id):
        """Publishes the media container to Instagram."""
        params = {
            'creation_id': media_container_id,
        }

        try:
            result = self._make_request('POST', f"{self.ig_user_id}/media_publish", data=params)
            
            if result and 'id' in result:
                post_id = result['id']
                logger.info(f"Publication initiated with ID: {post_id}")
                
                # If this was a pending container, remove it from the list
                if media_container_id in self.pending_containers:
                    self.pending_containers.pop(media_container_id)
                    self._save_state()
                    
                return post_id
            
            logger.error("Could not publish media")
            return None
            
        except RateLimitError as e:
            # Save container to pending list with retry information
            self.pending_containers[media_container_id] = {
                'container_id': media_container_id,
                'retry_count': 1,
                'next_attempt_time': time.time() + e.retry_seconds,
                'last_error': str(e),
                'created_at': datetime.now().isoformat(),
                'last_attempt': datetime.now().isoformat()
            }
            self._save_state()
            
            logger.warning(f"Rate limit reached. Container {media_container_id} saved for later publishing. Will retry after {e.retry_seconds} seconds.")
            # Re-raise to allow caller to handle
            raise
            
        except InstagramAPIError as e:
            logger.error(f"Error publishing media: {e}")
            raise

    def get_post_permalink(self, post_id):
        """Obtém o permalink de um post."""
        params = {
            'fields': 'permalink'
        }
        
        try:
            result = self._make_request('GET', f"{post_id}", params=params)
            if result and 'permalink' in result:
                permalink = result['permalink']
                logger.info(f"Permalink: {permalink}")
                return permalink
            return None
        except Exception as e:
            logger.error(f"Erro ao obter permalink: {e}")
            return None

    def post_image(self, image_url, caption):
        """
        Versão reescrita do método post_image para usar uma abordagem mais
        similar ao upload_local_video_to_reels, que está funcionando corretamente.
        """
        logger.info("Starting Instagram image publication...")

        try:
            # 1. Criar container
            container_id = self.create_media_container(image_url, caption)
            if not container_id:
                logger.error("Failed to create media container.")
                return None

            # 2. Aguardar processamento do container com backoff exponencial
            logger.info("Aguardando processamento do container...")
            status = self.wait_for_container_status(container_id)
            
            if status != 'FINISHED':
                logger.error(f"Processamento da imagem falhou com status: {status}")
                return None

            # 3. Publicar a mídia
            try:
                post_id = self.publish_media(container_id)
                if not post_id:
                    logger.error("Failed to publish media")
                    return None
            except RateLimitError as e:
                # Return partial result to indicate container is saved and will be published later
                logger.info(f"Rate limit reached. Container {container_id} saved for later publishing.")
                return {
                    'container_id': container_id,
                    'status': 'pending',
                    'media_type': 'IMAGE',
                    'retry_after': e.retry_seconds,
                    'message': 'Rate limit reached. Post will be published automatically when limit allows.'
                }

            # 4. Obter permalink (se possível)
            permalink = self.get_post_permalink(post_id)
            
            # 5. Retornar resultado de sucesso
            result = {
                'id': post_id,
                'container_id': container_id,
                'permalink': permalink,
                'media_type': 'IMAGE',
                'status': 'published'
            }
            
            logger.info(f"Foto publicada com sucesso! ID: {post_id}")
            return result
            
        except Exception as e:
            logger.error(f"Error posting image to Instagram: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
            
    def get_pending_posts(self):
        """Returns a list of pending posts"""
        current_time = time.time()
        result = []
        
        for container_id, data in self.pending_containers.items():
            next_attempt_time = data.get('next_attempt_time', 0)
            wait_time = max(0, next_attempt_time - current_time)
            
            result.append({
                'container_id': container_id,
                'retry_count': data.get('retry_count', 0),
                'next_attempt_in': f"{wait_time:.1f}s",
                'next_attempt_time': datetime.fromtimestamp(next_attempt_time).isoformat() if next_attempt_time else None,
                'created_at': data.get('created_at'),
                'last_attempt': data.get('last_attempt'),
                'last_error': data.get('last_error')
            })
            
        return result

