from typing import List, Optional, Tuple, Dict, Any
import os
from .base_instagram_service import BaseInstagramService
from .instagram_post_service import InstagramPostService  # Importando o serviço correto
from .carousel_normalizer import CarouselNormalizer
from .describe_carousel_tool import CarouselDescriber
from .crew_post_instagram import InstagramPostCrew
from .exceptions import InstagramError
from .instagram_carousel_service import InstagramCarouselService
from .instagram_reels_publisher import ReelsPublisher
from .carousel_poster import upload_carousel_images, post_carousel_to_instagram
from .instagram_video_processor import VideoProcessor
import logging

# Configurar logger
logger = logging.getLogger(__name__)

class InstagramFacade:
    """
    Fachada para simplificar as interações com a API do Instagram.
    Encapsula a complexidade das diferentes funcionalidades em uma interface única.
    """
    
    def __init__(self, access_token: str, ig_user_id: str, skip_token_validation: bool = False):
        self.access_token = access_token
        self.ig_user_id = ig_user_id
        self.skip_token_validation = skip_token_validation
        
        # Inicializar os serviços com a opção de ignorar validação de token
        self.service = BaseInstagramService(access_token, ig_user_id)
        self.post_service = InstagramPostService(access_token, ig_user_id, skip_token_validation)
        self.carousel_service = InstagramCarouselService(access_token, ig_user_id, skip_token_validation)
        self.reels_service = ReelsPublisher(access_token, ig_user_id, skip_token_validation)
        
        self.normalizer = CarouselNormalizer()
        self.describer = CarouselDescriber()
        self.crew = InstagramPostCrew()

    def post_single_photo(self, image_path: str, caption: str = None) -> Dict[str, Any]:
        """Posta uma única foto no Instagram"""
        try:
            # Usar o serviço específico de postagem
            logger.info(f"Iniciando postagem de foto única: {image_path}")
            
            # Criar container para a imagem
            import requests
            from urllib.parse import urlparse
            
            # Verificar se é um URL ou um caminho local
            if urlparse(image_path).scheme in ('http', 'https'):
                # É um URL
                image_url = image_path
            else:
                # É um caminho local, precisamos fazer upload para o Imgur
                from os.path import exists
                if not exists(image_path):
                    return {'status': 'error', 'message': f'Arquivo não encontrado: {image_path}'}
                
                try:
                    with open(image_path, 'rb') as img_file:
                        response = requests.post(
                            'https://api.imgur.com/3/upload',
                            headers={'Authorization': 'Client-ID ' + os.getenv('IMGUR_CLIENT_ID', '546c25a59c58ad7')},
                            files={'image': img_file}
                        )
                        data = response.json()
                        if not data.get('success'):
                            logger.error(f"Falha ao fazer upload da imagem: {data}")
                            return {'status': 'error', 'message': 'Falha ao fazer upload da imagem'}
                        image_url = data['data']['link']
                except Exception as e:
                    logger.error(f"Erro ao fazer upload da imagem: {str(e)}")
                    return {'status': 'error', 'message': f'Erro ao fazer upload da imagem: {str(e)}'}
            
            # Criar container de mídia
            container_id = self.post_service.create_media_container(image_url, caption)
            if not container_id:
                return {'status': 'error', 'message': 'Falha ao criar container de mídia'}
            
            # Aguardar o container ficar pronto
            status = self.post_service.wait_for_container_status(container_id)
            if status != 'FINISHED':
                return {'status': 'error', 'message': f'Container não ficou pronto. Status: {status}'}
            
            # Publicar o container
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

    def post_carousel(self, image_paths: List[str], caption: str = None) -> Dict[str, Any]:
        """Posta um carrossel de fotos no Instagram"""
        try:
            logger.info(f"Iniciando postagem de carrossel com {len(image_paths)} imagens")
            
            # Normalizar imagens se necessário usando o serviço existente
            normalized_paths = self.normalizer.normalize_carousel_images(image_paths)
            
            # Upload das imagens para URLs públicas
            import requests
            from urllib.parse import urlparse
            
            media_urls = []
            
            for image_path in normalized_paths:
                # Verificar se já é um URL
                if urlparse(image_path).scheme in ('http', 'https'):
                    media_urls.append(image_path)
                    continue
                
                # Upload da imagem para o Imgur
                try:
                    with open(image_path, 'rb') as img_file:
                        response = requests.post(
                            'https://api.imgur.com/3/upload',
                            headers={'Authorization': 'Client-ID ' + os.getenv('IMGUR_CLIENT_ID', '546c25a59c58ad7')},
                            files={'image': img_file}
                        )
                        data = response.json()
                        if not data.get('success'):
                            logger.error(f"Falha ao fazer upload da imagem: {data}")
                            continue
                        media_urls.append(data['data']['link'])
                except Exception as e:
                    logger.error(f"Erro ao fazer upload da imagem {image_path}: {str(e)}")
                    continue
            
            # Verificar se temos URLs suficientes
            if len(media_urls) < 2:
                return {
                    'status': 'error', 
                    'message': f'Número insuficiente de imagens válidas para carrossel. Encontradas: {len(media_urls)}, necessárias: pelo menos 2'
                }
            
            # Usar o serviço de carrossel para criar e publicar
            result = self.carousel_service.post_carousel(media_urls, caption)
            
            # Return the result directly since it now has the correct format
            return result
                
        except Exception as e:
            logger.error(f"Erro ao postar carrossel: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }

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