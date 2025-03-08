import os
import time
import json
import logging
import random
import requests
from datetime import datetime
from dotenv import load_dotenv
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from src.instagram.instagram_video_uploader import VideoUploader
from src.instagram.instagram_video_processor import InstagramVideoProcessor
#Import Base Class and exceptions:
from src.instagram.instagram_post_service import BaseInstagramService, AuthenticationError, PermissionError, RateLimitError, MediaError, TemporaryServerError, InstagramAPIError
from imgurpython import ImgurClient

logger = logging.getLogger('ReelsPublisher')

class ReelsPublisher(BaseInstagramService): # Inherit from BaseInstagramService
    """
    Classe especializada para publicação de Reels no Instagram.
    Implementa o fluxo completo de publicação conforme documentação oficial da Meta.
    """
    # API_VERSION and BASE_URL are already defined in the Base Class
    REELS_CONFIG = {
        'aspect_ratio': '9:16',     # Proporção de aspecto padrão para Reels (vertical)
        'min_duration': 3,           # Duração mínima em segundos
        'max_duration': 90,          # Duração máxima em segundos (Reels mais curtos têm melhor desempenho)
        'recommended_duration': 30,  # Duração recomendada pela Meta
        'min_width': 500,            # Largura mínima em pixels
        'recommended_width': 1080,   # Largura recomendada em pixels
        'recommended_height': 1920,  # Altura recomendada em pixels
        'video_formats': ['mp4'],    # Formatos suportados
        'video_codecs': ['h264'],    # Codecs de vídeo recomendados
        'audio_codecs': ['aac'],     # Codecs de áudio recomendados
    }
    REELS_ERROR_CODES = { # This might be better as a class variable in BaseInstagramService
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

        super().__init__(access_token, ig_user_id) # Initialize Base Class
        self.token_expires_at = None  # Initialize token expiration time
        self._validate_token()  # Validate on initialization

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
                    logger.warning("Token may not have necessary permissions")
                # Store the token expiration time, if available
                self.token_expires_at = response['data'].get('expires_at')
                if self.token_expires_at:
                    logger.info(f"Token will expire at: {datetime.fromtimestamp(self.token_expires_at)}")
            else:
                logger.error("Access token is invalid or expired.")
                raise AuthenticationError("Access token is invalid or expired.")

        except InstagramAPIError as e:
            logger.error(f"Error validating token: {e}")
            raise  # Re-raise the exception

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
                    "client_secret": os.getenv("INSTAGRAM_CLIENT_SECRET"),  # Use client secret
                    "access_token": self.access_token,
                },
            )

            self.access_token = response['access_token']
            self.token_expires_at = time.time() + response['expires_in']
            logger.info(f"Token refreshed. New expiration: {datetime.fromtimestamp(self.token_expires_at)}")

            # Update the .env file (DANGEROUS - see notes)
            self._update_env_file("INSTAGRAM_API_KEY", self.access_token)

        except InstagramAPIError as e:
            logger.error(f"Error refreshing token: {e}")
            raise  # Re-raise to handle the error higher up

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
            # Don't raise - better to continue with the (potentially) old value

    def create_reels_container(self, video_url, caption, share_to_feed=True,
                               audio_name=None, thumbnail_url=None, user_tags=None):
        """
        Cria um container para Reels.
        """
        if self.token_expires_at and time.time() > self.token_expires_at - 60:
            self._refresh_token()
        endpoint = f"{self.ig_user_id}/media"
        params = {
            'media_type': 'REELS',
            'video_url': video_url,
            'caption': caption,
            'share_to_feed': 'true' if share_to_feed else 'false',
        }
        if audio_name:
            params['audio_name'] = audio_name
        if thumbnail_url:
            params['thumbnail_url'] = thumbnail_url
        if user_tags:
            if isinstance(user_tags, list) and user_tags:
                params['user_tags'] = json.dumps(user_tags)
        try:
          result = self._make_request('POST', endpoint, data=params) # Use the base class method
          if result and 'id' in result:
              container_id = result['id']
              logger.info(f"Container de Reels criado com sucesso: {container_id}")
              return container_id
          else:
              logger.error("Falha ao criar container de Reels")
              return None
        except InstagramAPIError as e:
          logger.error(f"Failed to create reels container: {e}")
          raise


    def check_container_status(self, container_id):
        """
        Verifica o status do container de mídia.
        """
        if self.token_expires_at and time.time() > self.token_expires_at - 60:
            self._refresh_token()
        endpoint = f"{container_id}"
        params = {
            'fields': 'status_code,status'
        }
        try:
          result = self._make_request('GET', endpoint, params=params) # Use the base class method.
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
        """
        Publica o Reels usando o container criado.
        """
        if self.token_expires_at and time.time() > self.token_expires_at - 60:
            self._refresh_token()

        endpoint = f"{self.ig_user_id}/media_publish"
        params = {
            'creation_id': container_id
        }
        try:
          result = self._make_request('POST', endpoint, data=params) # Use base class method
          if result and 'id' in result:
              post_id = result['id']
              logger.info(f"Reels publicado com sucesso: {post_id}")
              return post_id
          else:
            logger.error(f"Failed to publish reels")
            return None

        except InstagramAPIError as e:
            logger.error(f"Error publishing reels: {e}")
            raise

    def get_reels_permalink(self, post_id):
        """
        Obtém o link permanente (URL) para o Reels publicado.
        """

        if self.token_expires_at and time.time() > self.token_expires_at - 60:
            self._refresh_token()

        endpoint = f"{post_id}"
        params = {
            'fields': 'permalink'
        }
        try:
          result = self._make_request('GET', endpoint, params=params) # Use base class method.
          if result and 'permalink' in result:
              permalink = result['permalink']
              logger.info(f"Permalink do Reels: {permalink}")
              return permalink
          logger.warning("Não foi possível obter permalink do Reels")
          return None
        except InstagramAPIError as e:
          logger.error(f"Error getting permalink for reels {post_id}: {e}")
          raise

    def post_reels(self, video_url, caption, share_to_feed=True,
                  audio_name=None, thumbnail_url=None, user_tags=None,
                  max_retries=30, retry_interval=10):
        """
        Fluxo completo para postar um Reels.
        """
        if self.token_expires_at and time.time() > self.token_expires_at - 60:
            self._refresh_token()

        container_id = self.create_reels_container(
            video_url, caption, share_to_feed, audio_name, thumbnail_url, user_tags
        )
        if not container_id:
            return None  # Error already logged by create_reels_container

        logger.info(f"Aguardando processamento do Reels... (máx. {max_retries} tentativas)")
        status = self.wait_for_container_status(container_id, max_attempts=max_retries, delay=retry_interval)
        if status != 'FINISHED':
            logger.error(f"Processamento do vídeo falhou com status: {status}")
            return None

        post_id = self.publish_reels(container_id)
        if not post_id:
            return None

        permalink = self.get_reels_permalink(post_id)
        result = {
            'id': post_id,
            'permalink': permalink,
            'container_id': container_id,
            'media_type': 'REELS'
        }
        logger.info("Reels publicado com sucesso!")
        logger.info(f"ID: {post_id}")
        logger.info(f"Link: {permalink or 'Não disponível'}")
        return result


    def upload_local_video_to_reels(self, video_path, caption, hashtags=None,
                                    optimize=True, thumbnail_path=None,
                                    share_to_feed=True, audio_name=None):
        """
        Envia um vídeo local para o Instagram como Reels.
        """
        if not os.path.exists(video_path):
            logger.error(f"Arquivo de vídeo não encontrado: {video_path}")
            return None

        final_caption = self._format_caption_with_hashtags(caption, hashtags)

        processor = InstagramVideoProcessor()
        uploader = VideoUploader()

        video_to_upload = video_path
        thumbnail_url = None
        is_video_optimized = False

        try:
            is_valid, message = uploader.validate_video(video_path)
            if not is_valid and optimize:
                logger.info(f"Vídeo não atende aos requisitos: {message}")
                logger.info("Otimizando vídeo para Reels...")
                optimized_video = processor.process_video(
                    video_path,
                    post_type='reel'  # Keep as 'reel' for Reels
                )
                if optimized_video:
                    logger.info(f"Vídeo otimizado: {optimized_video}")
                    video_to_upload = optimized_video
                    is_video_optimized = True
                else:
                    logger.warning("Falha na otimização automática. Tentando upload do vídeo original.")


            is_valid, message = uploader.validate_video(video_to_upload)
            if not is_valid:
                logger.error(f"Vídeo ainda não atende aos requisitos após otimização: {message}")
                return None

            if thumbnail_path and os.path.exists(thumbnail_path):
                logger.info(f"Enviando thumbnail personalizada: {thumbnail_path}")
                thumb_result = uploader.upload_from_path(thumbnail_path)  # Assuming you have an uploader
                if thumb_result and thumb_result.get('url'):
                    thumbnail_url = thumb_result.get('url')
                    logger.info(f"Thumbnail enviada: {thumbnail_url}")

            logger.info(f"Enviando vídeo para Imgur...")
            # Now, upload using ImgurClient:
            imgur_client = ImgurClient(os.getenv('IMGUR_CLIENT_ID'), os.getenv('IMGUR_CLIENT_SECRET'))
            imgur_response = imgur_client.upload_from_path(video_to_upload, config=None, anon=True)
            video_url = imgur_response['link']
            logger.info(f"Vídeo disponível em: {video_url}")

            result = self.post_reels(
                video_url=video_url,
                caption=final_caption,
                share_to_feed=share_to_feed,
                audio_name=audio_name,
                thumbnail_url=thumbnail_url
            )
            # Clean up the optimized video, if created
            if is_video_optimized and os.path.exists(video_to_upload) and video_to_upload != video_path:
                try:
                    os.remove(video_to_upload)
                    logger.info(f"Arquivo temporário removido: {video_to_upload}")
                except Exception as e:
                    logger.warning(f"Não foi possível remover arquivo temporário: {e}")

            return result


        except Exception as e:
            logger.exception(f"Erro na publicação do Reels: {e}")  # Use logger.exception
            return None
    def _format_caption_with_hashtags(self, caption, hashtags=None):
        """
        Formata a legenda com hashtags.
        """
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

    def get_account_info(self):
        """
        Obtém informações sobre a conta do Instagram associada.
        """
        if self.token_expires_at and time.time() > self.token_expires_at - 60:
            self._refresh_token()
        endpoint = f"{self.ig_user_id}"
        params = {
            'fields': 'id,username,name,profile_picture_url,biography,follows_count,followers_count,media_count'
        }
        try:
          result = self._make_request('GET', endpoint, params=params)  # Use base class method.
          return result
        except InstagramAPIError as e:
          logger.error(f"Error getting account info: {e}")
          raise

    def delete_reels(self, media_id):
        """
        Remove um Reels publicado.
        """
        if self.token_expires_at and time.time() > self.token_expires_at - 60:
            self._refresh_token()
        endpoint = f"{media_id}"
        try:
          result = self._make_request('DELETE', endpoint)  # Use base class method.
          if result and result.get('success') is True:
              logger.info(f"Reels {media_id} removido com sucesso")
              return True
          logger.error(f"Erro ao remover Reels {media_id}")
          return False
        except InstagramAPIError as e:
          logger.error(f"Error deleting reels {media_id}: {e}")
          raise

    def wait_for_container_status(self, container_id: str, max_attempts: int = 30, delay: int = 5) -> str:
        """Verifica o status do container até estar pronto ou falhar."""
        if self.token_expires_at and time.time() > self.token_expires_at - 60:
            self._refresh_token()

        endpoint = f"{container_id}"  # Removed BASE_URL, using _make_request
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
                    return status  # Return immediately on error

                time.sleep(delay)

            except RateLimitError as e:
                logger.warning(f"Rate limit hit while checking status. Waiting {e.retry_after}s...")
                time.sleep(e.retry_after)
            except Exception as e:
                logger.error(f"Error checking container status: {str(e)}")
                time.sleep(delay)

        logger.error(f"Container status check timed out after {max_attempts} attempts.")
        return 'TIMEOUT'