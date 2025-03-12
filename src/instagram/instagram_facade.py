from typing import List, Optional, Tuple, Dict, Any
import os
from .base_instagram_service import BaseInstagramService
from .instagram_post_service import InstagramPostService
from .carousel_normalizer import CarouselNormalizer
from .describe_carousel_tool import CarouselDescriber
from .crew_post_instagram import InstagramPostCrew
from .exceptions import InstagramError
from .instagram_carousel_service import InstagramCarouselService
from .instagram_reels_publisher import ReelsPublisher
from .carousel_poster import upload_carousel_images, post_carousel_to_instagram
from .instagram_video_processor import VideoProcessor
from .image_validator import InstagramImageValidator
import logging
from dotenv import load_dotenv
from urllib.parse import urlparse
load_dotenv()

logger = logging.getLogger(__name__)

class InstagramFacade:
    """
    Fachada para simplificar as interações com a API do Instagram.
    Encapsula a complexidade das diferentes funcionalidades em uma interface única.
    """
    
    def __init__(self, access_token: str, ig_user_id: str, skip_token_validation: bool = False):
        access_token = access_token or (
            os.getenv('INSTAGRAM_API_KEY') or
            os.getenv('INSTAGRAM_ACCESS_TOKEN') or
            os.getenv('FACEBOOK_ACCESS_TOKEN')
        )
        ig_user_id = ig_user_id or os.getenv("INSTAGRAM_ACCOUNT_ID")

        self.skip_token_validation = skip_token_validation
        
        # Inicializar os serviços com a opção de ignorar validação de token
        self.service = BaseInstagramService(access_token, ig_user_id)
        self.post_service = InstagramPostService(access_token, ig_user_id, skip_token_validation)
        self.carousel_service = InstagramCarouselService(access_token, ig_user_id, skip_token_validation)
        self.reels_service = ReelsPublisher(access_token, ig_user_id, skip_token_validation)
        
        self.normalizer = CarouselNormalizer()
        self.describer = CarouselDescriber()
        self.crew = InstagramPostCrew()

    def post_carousel(self, image_paths: List[str], caption: str = None) -> Dict[str, Any]:
        """Posta um carrossel de fotos no Instagram com validação aprimorada"""
        try:
            logger.info(f"Iniciando postagem de carrossel com {len(image_paths)} imagens")
            
            # Input validation
            if not image_paths or len(image_paths) < 2:
                return {'status': 'error', 'message': 'Mínimo de 2 imagens necessário para carrossel'}
            if len(image_paths) > 10:
                return {'status': 'error', 'message': 'Máximo de 10 imagens permitido para carrossel'}
            
            # Normalize and validate images
            valid_images = []
            for image_path in image_paths:
                is_valid, message = self.validate_media(image_path)
                if not is_valid:
                    logger.warning(f"Imagem inválida {image_path}: {message}")
                    continue
                valid_images.append(image_path)
            
            if len(valid_images) < 2:
                return {
                    'status': 'error',
                    'message': f'Número insuficiente de imagens válidas ({len(valid_images)}). Mínimo: 2'
                }

            # Normalize carousel images
            normalized_paths = self.normalizer.normalize_carousel_images(valid_images)
            
            # Upload to Imgur in parallel for better performance
            media_urls = []
            import asyncio
            import aiohttp
            import concurrent.futures

            async def upload_image(image_path):
                if urlparse(image_path).scheme in ('http', 'https'):
                    return image_path
                    
                try:
                    with open(image_path, 'rb') as img_file:
                        async with aiohttp.ClientSession() as session:
                            async with session.post(
                                'https://api.imgur.com/3/upload',
                                headers={'Authorization': f"Client-ID {os.getenv('IMGUR_CLIENT_ID', '546c25a59c58ad7')}"},
                                data={'image': img_file.read()}
                            ) as response:
                                data = await response.json()
                                if data.get('success'):
                                    return data['data']['link']
                except Exception as e:
                    logger.error(f"Erro ao fazer upload da imagem {image_path}: {str(e)}")
                return None

            # Run uploads in parallel with timeout
            with concurrent.futures.ThreadPoolExecutor() as executor:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    futures = [upload_image(path) for path in normalized_paths]
                    media_urls = [url for url in loop.run_until_complete(asyncio.gather(*futures)) if url]
                finally:
                    loop.close()

            if len(media_urls) < 2:
                return {
                    'status': 'error',
                    'message': f'Falha ao fazer upload das imagens. URLs válidas: {len(media_urls)}'
                }

            # Use carousel service with improved error handling
            result = self.carousel_service.post_carousel(media_urls, caption)
            logger.info(f"Resultado da postagem do carrossel: {result}")
            return result

        except Exception as e:
            logger.error(f"Erro ao postar carrossel: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'message': str(e)
            }

    def post_single_photo(self, image_path: str, caption: str = None) -> Dict[str, Any]:
        """Posta uma única foto no Instagram"""
        try:
            logger.info(f"Iniciando postagem de foto única: {image_path}")
            
            # Validate and optimize image first
            validator = InstagramImageValidator()
            is_valid, issues = validator.validate_single_photo(image_path)
            if not is_valid:
                logger.error(f"Image validation failed: {issues}")
                return {'status': 'error', 'message': f'Invalid image: {issues}'}
                
            # Optimize image before upload
            optimized_path = validator.optimize_for_instagram(image_path)
            if not optimized_path:
                return {'status': 'error', 'message': 'Failed to optimize image'}

            # Create container for the image
            import requests
            
            # Check if it's a URL or local path
            if urlparse(image_path).scheme in ('http', 'https'):
                image_url = image_path
            else:
                try:
                    with open(optimized_path, 'rb') as img_file:
                        response = requests.post(
                            'https://api.imgur.com/3/upload',
                            headers={'Authorization': 'Client-ID ' + os.getenv('IMGUR_CLIENT_ID', '546c25a59c58ad7')},
                            files={'image': img_file}
                        )
                        data = response.json()
                        if not data.get('success'):
                            logger.error(f"Failed to upload image: {data}")
                            return {'status': 'error', 'message': 'Failed to upload image'}
                        image_url = data['data']['link']
                except Exception as e:
                    logger.error(f"Error uploading image: {str(e)}")
                    return {'status': 'error', 'message': f'Error uploading image: {str(e)}'}
            
            # Create media container
            container_id = self.post_service.create_media_container(image_url, caption)
            if not container_id:
                return {'status': 'error', 'message': 'Failed to create media container'}
            
            # Wait for container to be ready
            status = self.post_service.wait_for_container_status(container_id)
            if status != 'FINISHED':
                return {'status': 'error', 'message': f'Container not ready. Status: {status}'}
            
            # Publish the container
            post_id = self.post_service.publish_media(container_id)
            
            if post_id:
                return {
                    'status': 'success',
                    'id': post_id
                }
            else:
                return {'status': 'error', 'message': 'Falha ao publicar imagem'}
                
        except Exception as e:
            logger.error(f"Erro ao postar foto: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    def post_reels(self, video_path: str, caption: str, share_to_feed: bool = True, hashtags: List[str] = None) -> Dict[str, Any]:
        """Posta um reels no Instagram"""
        try:
            logger.info(f"Iniciando postagem de reels: {video_path}")
            
            # Otimizar vídeo para formato reels
            optimized_video = VideoProcessor.optimize_for_instagram(video_path, post_type='reels')
            if not optimized_video:
                # Tentar otimização forçada se a normal falhar
                optimized_video = VideoProcessor.force_optimize_for_instagram(video_path, post_type='reels')
                if not optimized_video:
                    return {'status': 'error', 'message': 'Falha na otimização do vídeo'}
            
            # Usar o serviço de publicação de reels que já foi inicializado no construtor
            result = self.reels_service.upload_local_video_to_reels(
                video_path=optimized_video,
                caption=caption,
                hashtags=hashtags,
                share_to_feed=share_to_feed
            )
            
            if result and 'id' in result:
                return {
                    'status': 'success', 
                    'id': result['id'],
                    'permalink': result.get('permalink', None)
                }
            else:
                return {'status': 'error', 'message': 'Falha ao publicar reels'}
                
        except Exception as e:
            logger.error(f"Erro ao postar reels: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    def validate_media(self, file_path: str) -> Tuple[bool, str]:
        """Valida se um arquivo de mídia está adequado para publicação"""
        try:
            # Verificar extensão do arquivo
            _, ext = os.path.splitext(file_path)
            ext = ext.lower()
            
            if ext in ['.jpg', '.jpeg', '.png']:
                # Validar imagem
                self.normalizer.validate_image_file(file_path)
            elif ext in ['.mp4', '.mov']:
                # Validar vídeo
                is_valid, message = VideoProcessor.validate_video(file_path)
                if not is_valid:
                    return False, message
            else:
                return False, f"Formato de arquivo não suportado: {ext}"
                
            return True, "Arquivo válido"
        except Exception as e:
            return False, str(e)

    def get_account_status(self) -> dict:
        """Retorna o status atual da conta (rate limits, uso, etc)"""
        return self.service.get_app_usage_info()