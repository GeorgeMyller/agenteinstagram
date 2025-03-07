# src/instagram/carousel_poster.py

import os
import time
import requests
from typing import List, Tuple, Callable, Dict, Any, Optional
from dotenv import load_dotenv
from src.instagram.instagram_carousel_service import InstagramCarouselService  # Importe a classe
from src.instagram.image_uploader import ImageUploader  # Para upload das imagens

# --- Exceções Personalizadas (Opcional, mas recomendado) ---
class CarouselError(Exception):
    """Base class for carousel-related errors."""
    pass

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
    for index, image_path in enumerate(image_paths):
        if progress_callback:
            progress_callback(index + 1, total_images)  # Chama o callback de progresso
        try:
            result = uploader.upload_from_path(image_path)
            uploaded_images.append(result)
            uploaded_urls.append(result['url'])
        except Exception as e:
            print(f"Erro ao fazer upload da imagem {image_path}: {e}")
            success = False  # Se *qualquer* upload falhar, define success como False
            # Não interrompe o loop, tenta enviar as outras imagens

    return success, uploaded_images, uploaded_urls

def cleanup_uploaded_images(uploaded_images: List[Dict[str, str]]):
    """Exclui imagens que foram enviadas para o Imgur (ou outro serviço)."""
    uploader = ImageUploader()
    for image_info in uploaded_images:
        if 'deletehash' in image_info:
            try:
                uploader.delete_image(image_info['deletehash'])
            except Exception as e:
                print(f"Erro ao excluir imagem {image_info.get('id', 'desconhecido')}: {e}")

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
    """
    if not image_urls or len(image_urls) < 2:
        print("Número insuficiente de URLs de imagens para criar um carrossel.")
        return None
    
    service = InstagramCarouselService()
    container_id = service.create_carousel_container(image_urls, caption)

    if not container_id:
        print("Falha ao criar o contêiner do carrossel.")
        return None

    # Aguarda o processamento (você pode querer adicionar um timeout aqui)
    status = service.wait_for_container_status(container_id)
    if status != 'FINISHED':
        print(f"Contêiner do carrossel não ficou pronto. Status: {status}")
        return None
    
    post_id = service.publish_carousel(container_id)
    if not post_id:
        print("Falha ao publicar o carrossel.")
        return None

    print(f"Carrossel publicado com sucesso! ID: {post_id}")
    return post_id