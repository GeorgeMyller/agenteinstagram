"""
Instagram Send - Wrapper de compatibilidade.

Este módulo serve como uma ponte entre o código antigo e a nova estrutura
arquitetural. Ele fornece uma interface retrocompatível com a implementação 
original de 'instagram_send.py', mas internamente utiliza a nova estrutura
de classes e serviços.

Isso permite que o sistema seja gradualmente migrado para a nova arquitetura
sem quebrar a funcionalidade existente.
"""

import logging
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
import os

# Importando serviços da nova arquitetura
from .instagram_facade import InstagramFacade
from .instagram_post_service import InstagramPostService
from .instagram_carousel_service import InstagramCarouselService
from .instagram_media_service import InstagramMediaService
from ..utils.config import Config

logger = logging.getLogger(__name__)

class InstagramSend:
    """
    Versão retrocompatível do serviço Instagram.
    
    Esta classe estática fornece compatibilidade com o código antigo,
    redirecionando as chamadas para os novos serviços estruturados.
    """
    
    @staticmethod
    def send_instagram(image_path: Union[str, Path], caption: str, **kwargs) -> Dict[str, Any]:
        """
        Envia uma única imagem para o Instagram.
        
        Args:
            image_path: Caminho da imagem
            caption: Legenda da imagem
            **kwargs: Parâmetros adicionais
            
        Returns:
            Dict com resultado da operação
        """
        try:
            logger.info(f"Enviando imagem para Instagram: {image_path}")
            
            # Obter configuração
            config = Config.get_instance()
            
            # Criar instância do façade
            facade = InstagramFacade()
            
            # Chamada ao novo serviço
            result = facade.post_single_image(
                image_path=image_path,
                caption=caption,
                **kwargs
            )
            
            # Adaptação do resultado para formato antigo
            return {
                "status": "success" if result.get("success") else "error",
                "id": result.get("media_id", ""),
                "message": result.get("message", "")
            }
            
        except Exception as e:
            logger.error(f"Erro ao enviar imagem para Instagram: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "message": str(e)
            }
    
    @staticmethod
    def send_instagram_carousel(image_paths: List[Union[str, Path]], caption: str, **kwargs) -> Dict[str, Any]:
        """
        Envia um carrossel de imagens para o Instagram.
        
        Args:
            image_paths: Lista de caminhos de imagens
            caption: Legenda do carrossel
            **kwargs: Parâmetros adicionais
            
        Returns:
            Dict com resultado da operação
        """
        try:
            logger.info(f"Enviando carrossel para Instagram: {len(image_paths)} imagens")
            
            # Criar instância do façade
            facade = InstagramFacade()
            
            # Chamada ao novo serviço
            result = facade.post_carousel(
                image_paths=image_paths,
                caption=caption,
                **kwargs
            )
            
            # Adaptação do resultado para formato antigo
            return {
                "status": "success" if result.get("success") else "error",
                "id": result.get("media_id", ""),
                "message": result.get("message", "")
            }
            
        except Exception as e:
            logger.error(f"Erro ao enviar carrossel para Instagram: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "message": str(e)
            }
    
    @staticmethod
    def send_instagram_video(video_path: Union[str, Path], caption: str, **kwargs) -> Dict[str, Any]:
        """
        Envia um vídeo para o Instagram.
        
        Args:
            video_path: Caminho do vídeo
            caption: Legenda do vídeo
            **kwargs: Parâmetros adicionais
            
        Returns:
            Dict com resultado da operação
        """
        try:
            logger.info(f"Enviando vídeo para Instagram: {video_path}")
            
            # Criar instância do façade
            facade = InstagramFacade()
            
            # Chamada ao novo serviço
            result = facade.post_video(
                video_path=video_path,
                caption=caption,
                **kwargs
            )
            
            # Adaptação do resultado para formato antigo
            return {
                "status": "success" if result.get("success") else "error",
                "id": result.get("media_id", ""),
                "message": result.get("message", "")
            }
            
        except Exception as e:
            logger.error(f"Erro ao enviar vídeo para Instagram: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "message": str(e)
            }