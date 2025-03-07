# src/instagram/carousel_poster.py

import os
import time
import requests
import logging
from typing import List, Tuple, Callable, Dict, Any, Optional
from dotenv import load_dotenv
from src.instagram.instagram_carousel_service import InstagramCarouselService, RateLimitError
from src.instagram.image_uploader import ImageUploader  # Para upload das imagens

# Configure logging
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# --- Exceções Personalizadas (Opcional, mas recomendado) ---
class CarouselError(Exception):
    """Base class for carousel-related errors."""
    def __init__(self, message, error_code=None, error_subcode=None, fb_trace_id=None, is_retriable=False):
        super().__init__(message)
        self.error_code = error_code
        self.error_subcode = error_subcode
        self.fb_trace_id = fb_trace_id
        self.is_retriable = is_retriable
    
    def __str__(self):
        details = []
        if self.error_code:
            details.append(f"Code: {self.error_code}")
        if self.error_subcode:
            details.append(f"Subcode: {self.error_subcode}")
        if self.fb_trace_id:
            details.append(f"FB Trace ID: {self.fb_trace_id}")
        
        if details:
            return f"{super().__str__()} ({', '.join(details)})"
        return super().__str__()

class AuthenticationError(CarouselError):
    """Raised when there's an issue with authentication (codes 102, 190, etc)."""
    pass

class PermissionError(CarouselError):
    """Raised when there's an issue with permissions (codes 10, 200, 203, etc)."""
    pass

class ThrottlingError(CarouselError):
    """Raised when API rate limits are hit (codes 4, 17, 32, 613, etc)."""
    def __init__(self, message, error_code=None, error_subcode=None, fb_trace_id=None, retry_after=None):
        super().__init__(message, error_code, error_subcode, fb_trace_id, True)
        self.retry_after = retry_after or 300  # Default to 5 minutes if not specified

class ImageValidationError(CarouselError):
    """Raised when an image fails validation."""
    pass

class ImageUploadError(CarouselError):
    """Raised when an image fails to upload."""
    pass

class CarouselCreationError(CarouselError):
    """Raised when the carousel container fails to be created."""
    pass

class CarouselPublishError(CarouselError):
    """Raised when the carousel fails to publish."""
    pass

class ServerError(CarouselError):
    """Raised when Instagram/Facebook server errors occur (codes 1, 2, etc)."""
    def __init__(self, message, error_code=None, error_subcode=None, fb_trace_id=None):
        super().__init__(message, error_code, error_subcode, fb_trace_id, True)  # Server errors are generally retriable
# --- Fim das Exceções ---

def validate_carousel_images(image_paths: List[str], validator_func: Callable[[str], bool]) -> Tuple[List[str], List[str]]:
    """Valida uma lista de imagens para o carrossel.

    Args:
        image_paths: Uma lista de caminhos de arquivos de imagem.
        validator_func: Uma função que recebe um caminho de imagem e retorna True se a imagem for válida, False caso contrário.

    Returns:
        Uma tupla contendo duas listas: imagens válidas e imagens inválidas.
    """
    valid_images = []
    invalid_images = []
    for image_path in image_paths:
        if validator_func(image_path):
            valid_images.append(image_path)
        else:
            invalid_images.append(image_path)
    return valid_images, invalid_images

def upload_carousel_images(image_paths: List[str], progress_callback: Callable[[int, int], None] = None) -> Tuple[bool, List[Dict[str, str]], List[str]]:
    """Faz upload de uma lista de imagens para o Imgur (ou outro serviço).

    Args:
        image_paths: Uma lista de caminhos de arquivos de imagem.
        progress_callback: Uma função opcional que será chamada a cada imagem enviada,
                           recebendo o índice atual e o total de imagens como argumentos.

    Returns:
        Uma tupla: (sucesso, lista de resultados do upload, lista de URLs das imagens).
        'sucesso' é True se *todas* as imagens foram enviadas com sucesso, False caso contrário.
        'lista de resultados' é uma lista de dicionários, cada um contendo informações sobre uma imagem enviada (id, url, deletehash).
        'lista de URLs' é uma lista de URLs das imagens enviadas.
    """
    uploader = ImageUploader()  # Instancia o ImageUploader
    uploaded_images = []
    uploaded_urls = []
    success = True

    total_images = len(image_paths)
    failed_images = []

    for index, image_path in enumerate(image_paths):
        if progress_callback:
            progress_callback(index + 1, total_images)  # Chama o callback de progresso
        try:
            result = uploader.upload_from_path(image_path)
            uploaded_images.append(result)
            uploaded_urls.append(result['url'])
            logger.info(f"Uploaded image {index+1}/{total_images}: {result['url']}")
        except Exception as e:
            failed_images.append(image_path)
            logger.error(f"Erro ao fazer upload da imagem {image_path}: {str(e)}")
            success = False  # Se *qualquer* upload falhar, define success como False
            # Não interrompe o loop, tenta enviar as outras imagens

    if failed_images:
        logger.error(f"Failed to upload {len(failed_images)} images: {failed_images}")
        
    return success, uploaded_images, uploaded_urls

def cleanup_uploaded_images(uploaded_images: List[Dict[str, str]]):
    """Exclui imagens que foram enviadas para o Imgur (ou outro serviço)."""
    uploader = ImageUploader()
    success_count = 0
    fail_count = 0
    
    for image_info in uploaded_images:
        if 'deletehash' in image_info:
            try:
                uploader.delete_image(image_info['deletehash'])
                success_count += 1
            except Exception as e:
                fail_count += 1
                logger.error(f"Erro ao excluir imagem {image_info.get('id', 'desconhecido')}: {e}")
    
    logger.info(f"Image cleanup: {success_count} deleted, {fail_count} failed")

def post_carousel_to_instagram(image_paths: List[str], caption: str, image_urls: List[str] = None) -> Optional[str]:
    """
    Publica um carrossel no Instagram.  Esta função *não* faz upload das imagens,
    assume que elas já foram enviadas e que você tem as URLs.

    Args:
        image_paths: Lista de caminhos de arquivos de imagem (usado apenas para logging/debug, se necessário).
        caption: A legenda do carrossel.
        image_urls: Lista de URLs das imagens *já enviadas*.

    Returns:
        O ID da postagem do carrossel, se a publicação for bem-sucedida, ou None em caso de falha.

    Raises:
        CarouselError: Base exception for all carousel errors
        AuthenticationError: Issues with API tokens
        PermissionError: Issues with account permissions
        ThrottlingError: Rate limit issues
        CarouselCreationError: Specific error for container creation
        CarouselPublishError: Specific error for publishing
        ServerError: Facebook/Instagram server errors
    """
    if not image_urls or len(image_urls) < 2:
        error_msg = f"Número insuficiente de URLs de imagens para criar um carrossel. Encontrado: {len(image_urls or [])}, necessário: mínimo 2"
        logger.error(error_msg)
        raise CarouselCreationError(error_msg)
    
    service = InstagramCarouselService()
    
    # Criar container
    max_retries = 3
    retry_delay = 300  # 5 minutos
    container_id = None
    
    # Retry loop para criação do container
    for attempt in range(max_retries):
        try:
            logger.info(f"Tentativa {attempt+1}/{max_retries} de criar container do carrossel...")
            container_id = service.create_carousel_container(image_urls, caption)
            if container_id:
                logger.info(f"Container do carrossel criado com sucesso na tentativa {attempt+1}: {container_id}")
                break
            else:
                logger.warning(f"Tentativa {attempt+1} falhou. Container retornou nulo.")
                if attempt < max_retries - 1:
                    logger.info(f"Aguardando {retry_delay} segundos antes da próxima tentativa...")
                    time.sleep(retry_delay)
                    # Backoff exponencial
                    retry_delay = min(retry_delay * 2, 3600)  # Máximo de 1 hora
        except RateLimitError as e:
            # Capturar erro de rate limit para backoff específico
            retry_after = getattr(e, 'retry_seconds', retry_delay)
            logger.warning(f"Rate limit excedido ao criar container (tentativa {attempt+1}). Aguardando {retry_after}s...")
            
            if attempt < max_retries - 1:
                time.sleep(retry_after)
                # Ajusta o delay com base no retorno da API
                retry_delay = min(retry_after * 1.5, 3600)  # Máximo de 1 hora
            else:
                raise ThrottlingError(
                    f"Rate limit excedido após {max_retries} tentativas de criar container",
                    retry_after=retry_after
                )
        except Exception as e:
            error_msg = f"Erro ao criar container do carrossel (tentativa {attempt+1}): {e}"
            logger.error(error_msg)
            
            # Analisa os detalhes do erro, se disponíveis
            if hasattr(e, 'response') and hasattr(e.response, 'json'):
                try:
                    error_data = e.response.json().get('error', {})
                    error_code = error_data.get('code')
                    error_subcode = error_data.get('error_subcode')
                    fb_trace_id = error_data.get('fbtrace_id')
                    error_msg = error_data.get('message', error_msg)
                    
                    # Categoriza o erro com base no código
                    if error_code in [102, 190]:
                        if attempt >= max_retries - 1:
                            raise AuthenticationError(error_msg, error_code, error_subcode, fb_trace_id)
                    elif error_code in [10, 200, 203, 803]:
                        if attempt >= max_retries - 1:
                            raise PermissionError(error_msg, error_code, error_subcode, fb_trace_id)
                    elif error_code in [1, 2, 4, 17, 341]:
                        if attempt >= max_retries - 1:
                            raise ServerError(error_msg, error_code, error_subcode, fb_trace_id)
                    elif error_code == 2207024:  # Carousel validation error
                        if attempt >= max_retries - 1:
                            raise CarouselCreationError(error_msg, error_code, error_subcode, fb_trace_id)
                except:
                    pass
            
            # Continue com o retry se não for o último loop
            if attempt < max_retries - 1:
                logger.info(f"Aguardando {retry_delay} segundos antes da próxima tentativa...")
                time.sleep(retry_delay)
                # Backoff exponencial
                retry_delay = min(retry_delay * 2, 3600)  # Máximo de 1 hora
            else:
                raise CarouselCreationError(f"Falha ao criar o contêiner do carrossel após {max_retries} tentativas")
    
    if not container_id:
        raise CarouselCreationError(f"Falha ao criar o contêiner do carrossel após {max_retries} tentativas")

    # Aguardar processamento
    status = service.wait_for_container_status(container_id)
    if status != 'FINISHED':
        error_msg = f"Contêiner do carrossel não ficou pronto. Status final: {status}"
        logger.error(error_msg)
        raise CarouselCreationError(error_msg)
    
    # Publicar carrossel com retry
    post_id = None
    retry_delay = 300  # 5 minutos (reset para a publicação)
    
    # Retry loop para publicação
    for attempt in range(max_retries):
        try:
            logger.info(f"Tentativa {attempt+1}/{max_retries} de publicar o carrossel...")
            post_id = service.publish_carousel(container_id)
            if post_id:
                logger.info(f"Carrossel publicado com sucesso na tentativa {attempt+1}! ID: {post_id}")
                break
            else:
                logger.warning(f"Tentativa {attempt+1} falhou. Retorno nulo da API.")
                if attempt < max_retries - 1:
                    logger.info(f"Aguardando {retry_delay} segundos antes da próxima tentativa...")
                    time.sleep(retry_delay)
                    # Backoff exponencial
                    retry_delay = min(retry_delay * 2, 3600)  # Máximo de 1 hora
        except RateLimitError as e:
            # Similar ao tratamento para criação do container
            retry_after = getattr(e, 'retry_seconds', retry_delay)
            logger.warning(f"Rate limit excedido ao publicar (tentativa {attempt+1}). Aguardando {retry_after}s...")
            
            if attempt < max_retries - 1:
                time.sleep(retry_after)
                retry_delay = min(retry_after * 1.5, 3600)
            else:
                raise ThrottlingError(
                    f"Rate limit excedido após {max_retries} tentativas de publicar",
                    retry_after=retry_after
                )
        except Exception as e:
            error_msg = f"Erro ao publicar carrossel (tentativa {attempt+1}): {e}"
            logger.error(error_msg)
            
            # Análise similar de erros
            if hasattr(e, 'response') and hasattr(e.response, 'json'):
                try:
                    error_data = e.response.json().get('error', {})
                    error_code = error_data.get('code')
                    error_subcode = error_data.get('error_subcode')
                    fb_trace_id = error_data.get('fbtrace_id')
                    error_msg = error_data.get('message', error_msg)
                    
                    if error_code == 35001:  # Carousel publish error
                        if attempt >= max_retries - 1:
                            raise CarouselPublishError(error_msg, error_code, error_subcode, fb_trace_id)
                except:
                    pass
            
            if attempt < max_retries - 1:
                logger.info(f"Aguardando {retry_delay} segundos antes da próxima tentativa...")
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 3600)
            else:
                raise CarouselPublishError(f"Falha ao publicar o carrossel após {max_retries} tentativas")

    if not post_id:
        raise CarouselPublishError(f"Falha ao publicar o carrossel após {max_retries} tentativas")

    logger.info(f"Carrossel publicado com sucesso! ID: {post_id}")
    return post_id