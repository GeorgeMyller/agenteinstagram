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
        # Removendo o cache de containers que pode causar problemas
        # self.container_cache = {}
        # self._load_state()

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
                return post_id
            
            logger.error("Could not publish media")
            return None
            
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
            post_id = self.publish_media(container_id)
            if not post_id:
                logger.error("Failed to publish media")
                return None

            # 4. Obter permalink (se possível)
            permalink = self.get_post_permalink(post_id)
            
            # 5. Retornar resultado de sucesso
            result = {
                'id': post_id,
                'container_id': container_id,
                'permalink': permalink,
                'media_type': 'IMAGE'
            }
            
            logger.info(f"Foto publicada com sucesso! ID: {post_id}")
            return result
            
        except Exception as e:
            logger.error(f"Error posting image to Instagram: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

