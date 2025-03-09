"""
Módulo especializado para publicação de Reels no Instagram
Implementado com base nos exemplos oficiais da Meta para publicação de Reels
Fonte: https://github.com/fbsamples/reels_publishing_apis

Este módulo implementa as melhores práticas e parâmetros específicos
para a publicação de Reels no Instagram.
"""

import os
import time
import json
import logging
import random
from datetime import datetime
from dotenv import load_dotenv
from imgurpython import ImgurClient
from moviepy.editor import VideoFileClip
from src.instagram.base_instagram_service import (
    BaseInstagramService, AuthenticationError, PermissionError, 
    RateLimitError, MediaError, TemporaryServerError, InstagramAPIError
)

logger = logging.getLogger('ReelsPublisher')

class ReelsPublisher(BaseInstagramService):
    """
    Classe especializada para publicação de Reels no Instagram.
    Implementa o fluxo completo de publicação conforme documentação oficial da Meta.
    """
    
    REELS_CONFIG = {
        'aspect_ratio': '9:16',     # Proporção de aspecto padrão para Reels (vertical)
        'min_duration': 3,          # Duração mínima em segundos
        'max_duration': 90,         # Duração máxima em segundos
        'recommended_duration': 30,  # Duração recomendada pela Meta
        'min_width': 500,           # Largura mínima em pixels
        'recommended_width': 1080,  # Largura recomendada em pixels
        'recommended_height': 1920, # Altura recomendada em pixels
        'video_formats': ['mp4'],   # Formatos suportados
        'video_codecs': ['h264'],   # Codecs de vídeo recomendados
        'audio_codecs': ['aac'],    # Codecs de áudio recomendados
    }
    
    REELS_ERROR_CODES = {
        2207026: "Formato de vídeo não suportado para Reels",
        2207014: "Duração de vídeo não compatível com Reels",
        2207013: "Proporção de aspecto do vídeo não é compatível com Reels",
        9007: "Permissão de publicação de Reels negada",
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
                "INSTAGRAM_ACCOUNT_ID nas variáveis de ambiente ou forneça-os diretamente."
            )
            
        super().__init__(access_token, ig_user_id)

    def create_reels_container(self, video_url, caption, share_to_feed=True,
                             audio_name=None, thumbnail_url=None, user_tags=None):
        """Cria um container para Reels."""
        params = {
            'media_type': 'REELS',
            'video_url': video_url,
            'caption': caption,
            'share_to_feed': 'true' if share_to_feed else 'false'
        }
        
        if audio_name:
            params['audio_name'] = audio_name
        if thumbnail_url:
            params['thumbnail_url'] = thumbnail_url
        if user_tags:
            if isinstance(user_tags, list) and user_tags:
                params['user_tags'] = json.dumps(user_tags)

        try:
            result = self._make_request('POST', f"{self.ig_user_id}/media", data=params)
            if result and 'id' in result:
                container_id = result['id']
                logger.info(f"Container de Reels criado com sucesso: {container_id}")
                return container_id
            logger.error("Falha ao criar container de Reels")
            return None
        except InstagramAPIError as e:
            logger.error(f"Failed to create reels container: {e}")
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

    def publish_reels(self, container_id):
        """Publica o Reels usando o container criado."""
        params = {
            'creation_id': container_id
        }
        
        try:
            result = self._make_request('POST', f"{self.ig_user_id}/media_publish", data=params)
            if result and 'id' in result:
                post_id = result['id']
                logger.info(f"Reels publicado com sucesso: {post_id}")
                return post_id
            logger.error("Failed to publish reels")
            return None
        except InstagramAPIError as e:
            logger.error(f"Error publishing reels: {e}")
            raise

    def wait_for_container_status(self, container_id, max_attempts=30, delay=10):
        """Aguarda o container estar pronto."""
        for attempt in range(max_attempts):
            try:
                status = self.check_container_status(container_id)
                if status == 'FINISHED':
                    return status
                elif status in ['ERROR', 'EXPIRED']:
                    logger.error(f"Container failed with status: {status}")
                    return status
                
                backoff_time = delay * (2 ** attempt) + random.uniform(0, 5)
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

    def post_reels(self, video_url, caption, share_to_feed=True,
                  audio_name=None, thumbnail_url=None, user_tags=None,
                  max_retries=30, retry_interval=10):
        """Fluxo completo para postar um Reels."""
        container_id = self.create_reels_container(
            video_url, caption, share_to_feed, audio_name, thumbnail_url, user_tags
        )
        
        if not container_id:
            return None

        logger.info(f"Aguardando processamento do Reels... (máx. {max_retries} tentativas)")
        status = self.wait_for_container_status(container_id, max_attempts=max_retries, delay=retry_interval)
        
        if status != 'FINISHED':
            logger.error(f"Processamento do vídeo falhou com status: {status}")
            return None

        post_id = self.publish_reels(container_id)
        if not post_id:
            return None

        result = {
            'id': post_id,
            'container_id': container_id,
            'media_type': 'REELS'
        }
        
        logger.info("Reels publicado com sucesso!")
        logger.info(f"ID: {post_id}")
        
        return result

    def upload_local_video_to_reels(self, video_path, caption, hashtags=None,
                                  optimize=True, thumbnail_path=None,
                                  share_to_feed=True, audio_name=None):
        """Envia um vídeo local para o Instagram como Reels."""
        if not os.path.exists(video_path):
            logger.error(f"Arquivo de vídeo não encontrado: {video_path}")
            return None

        final_caption = self._format_caption_with_hashtags(caption, hashtags)
        thumbnail_url = None
        
        try:
            # Upload video to Imgur
            imgur_client = ImgurClient(
                os.getenv('IMGUR_CLIENT_ID'),
                os.getenv('IMGUR_CLIENT_SECRET')
            )
            
            # Upload thumbnail if provided
            if thumbnail_path and os.path.exists(thumbnail_path):
                logger.info(f"Enviando thumbnail personalizada: {thumbnail_path}")
                thumb_result = imgur_client.upload_from_path(thumbnail_path)
                if thumb_result and 'link' in thumb_result:
                    thumbnail_url = thumb_result['link']
                    logger.info(f"Thumbnail enviada: {thumbnail_url}")

            logger.info(f"Enviando vídeo para Imgur...")
            video_result = imgur_client.upload_from_path(video_path)
            if not video_result or 'link' not in video_result:
                logger.error("Falha no upload do vídeo para Imgur")
                return None
                
            video_url = video_result['link']
            logger.info(f"Vídeo disponível em: {video_url}")

            result = self.post_reels(
                video_url=video_url,
                caption=final_caption,
                share_to_feed=share_to_feed,
                audio_name=audio_name,
                thumbnail_url=thumbnail_url
            )
            
            return result
            
        except Exception as e:
            logger.exception(f"Erro na publicação do Reels: {e}")
            return None

    def _format_caption_with_hashtags(self, caption, hashtags=None):
        """Formata a legenda com hashtags."""
        if not hashtags:
            return caption
            
        if isinstance(hashtags, str):
            hashtag_list = [tag.strip() for tag in hashtags.split(',')]
        else:
            hashtag_list = hashtags
            
        hashtag_text = ' '.join([f"#{tag}" for tag in hashtag_list if tag])
        
        if caption:
            return f"{caption}\n\n{hashtag_text}"
        else:
            return hashtag_text

class ReelsValidator:
    """Validates videos for Reels requirements"""
    
    # Reels requirements based on Meta documentation
    MIN_DURATION = 3  # seconds
    MAX_DURATION = 90  # seconds
    MIN_WIDTH = 500  # pixels
    MIN_HEIGHT = 889  # pixels for 9:16 ratio
    ALLOWED_FORMATS = ['mp4']
    MAX_SIZE_MB = 100  # MB
    
    @classmethod
    def validate(cls, video_path):
        """
        Validates a video for Reels requirements
        Returns: (is_valid, message)
        """
        if not os.path.exists(video_path):
            return False, "Video file not found"
            
        # Check file size
        file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
        if file_size_mb > cls.MAX_SIZE_MB:
            return False, f"Video size exceeds {cls.MAX_SIZE_MB}MB (actual: {file_size_mb:.2f}MB)"
        
        # Check file extension
        _, ext = os.path.splitext(video_path)
        if ext.lower().replace('.', '') not in cls.ALLOWED_FORMATS:
            return False, f"Video format not supported. Use: {', '.join(cls.ALLOWED_FORMATS)}"
            
        try:
            with VideoFileClip(video_path) as clip:
                # Check duration
                duration = clip.duration
                if duration < cls.MIN_DURATION:
                    return False, f"Video too short ({duration:.1f}s). Minimum duration is {cls.MIN_DURATION}s"
                if duration > cls.MAX_DURATION:
                    return False, f"Video too long ({duration:.1f}s). Maximum duration is {cls.MAX_DURATION}s"
                
                # Check dimensions
                width, height = clip.size
                if width < cls.MIN_WIDTH:
                    return False, f"Video width too small ({width}px). Minimum width is {cls.MIN_WIDTH}px"
                if height < cls.MIN_HEIGHT:
                    return False, f"Video height too small ({height}px). Recommended minimum height is {cls.MIN_HEIGHT}px"
                
                # Check aspect ratio
                aspect_ratio = width / height
                if aspect_ratio > 1.91 or aspect_ratio < 0.5:
                    return False, f"Video aspect ratio ({aspect_ratio:.2f}) outside of recommended range (0.5-1.91)"
                
                return True, "Video meets Reels requirements"
                
        except Exception as e:
            return False, f"Error analyzing video: {str(e)}"

# Update the publish method to include validation
def publish(self, video_path, caption=""):
    """Publish a video as an Instagram Reel"""
    logging.info("Starting process to publish a Reel...")
    
    # Validate the video first
    is_valid, validation_message = ReelsValidator.validate(video_path)
    if not is_valid:
        logging.error(f"Video validation failed: {validation_message}")
        raise ValueError(f"Video doesn't meet Reels requirements: {validation_message}")
    
    # ... rest of existing publish method ...