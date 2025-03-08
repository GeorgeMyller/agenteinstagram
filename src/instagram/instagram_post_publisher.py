from src.instagram.base_instagram_service import BaseInstagramService
import logging
import os
from dotenv import load_dotenv
import json

logger = logging.getLogger('PostPublisher')

class PostPublisher(BaseInstagramService):
    """
    Classe especializada para publicação de fotos no Instagram.
    """
    
    POST_CONFIG = {
        'aspect_ratio_min': 4.0/5.0,  # Instagram minimum (4:5)
        'aspect_ratio_max': 1.91,     # Instagram maximum (1.91:1)
        'min_resolution': 320,
        'recommended_resolution': 1080,
        'max_file_size_mb': 8,
        'supported_formats': ['jpg', 'jpeg', 'png']
    }

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
                "Credenciais incompletas. Defina INSTAGRAM_ACCESS_TOKEN e "
                "INSTAGRAM_ACCOUNT_ID nas variáveis de ambiente."
            )
            
        super().__init__(access_token, ig_user_id)

    def create_container(self, image_url, caption):
        """Cria um container para a foto."""
        params = {
            'image_url': image_url,
            'caption': caption,
            'media_type': 'IMAGE'
        }
        
        try:
            result = self._make_request('POST', f"{self.ig_user_id}/media", data=params)
            if result and 'id' in result:
                container_id = result['id']
                logger.info(f"Container criado com sucesso: {container_id}")
                return container_id
            logger.error("Falha ao criar container")
            return None
        except Exception as e:
            logger.error(f"Erro ao criar container: {e}")
            return None

    def publish_photo(self, container_id):
        """Publica a foto usando o container criado."""
        params = {
            'creation_id': container_id
        }
        
        try:
            result = self._make_request('POST', f"{self.ig_user_id}/media_publish", data=params)
            if result and 'id' in result:
                post_id = result['id']
                logger.info(f"Foto publicada com sucesso: {post_id}")
                return post_id
            logger.error("Falha ao publicar foto")
            return None
        except Exception as e:
            logger.error(f"Erro ao publicar foto: {e}")
            return None

    def upload_photo(self, photo_path, caption):
        """Fluxo completo para postar uma foto."""
        if not os.path.exists(photo_path):
            logger.error(f"Arquivo não encontrado: {photo_path}")
            return None

        try:
            # Upload photo to temporary storage/CDN
            image_url = self._upload_to_cdn(photo_path)
            if not image_url:
                return None

            # Create container
            container_id = self.create_container(image_url, caption)
            if not container_id:
                return None

            # Wait for container processing
            status = self.wait_for_container_status(container_id)
            if status != 'FINISHED':
                logger.error(f"Processamento falhou: {status}")
                return None

            # Publish photo
            post_id = self.publish_photo(container_id)
            if not post_id:
                return None

            # Get permalink
            permalink = self.get_post_permalink(post_id)

            return {
                'id': post_id,
                'permalink': permalink,
                'media_type': 'IMAGE'
            }

        except Exception as e:
            logger.error(f"Erro ao postar foto: {e}")
            return None

    def _upload_to_cdn(self, photo_path):
        """Upload photo to CDN/temporary storage."""
        try:
            # Implement CDN upload logic here
            # For now, using imgur as temporary solution
            imgur_client = self._get_imgur_client()
            if not imgur_client:
                return None
                
            result = imgur_client.upload_from_path(photo_path)
            return result.get('link')
        except Exception as e:
            logger.error(f"Erro no upload para CDN: {e}")
            return None
