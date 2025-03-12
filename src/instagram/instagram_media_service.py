from typing import List, Dict, Tuple, Optional
from .base_instagram_service import BaseInstagramService
from .exceptions import InstagramError, MediaError, ValidationError

class InstagramMediaService(BaseInstagramService):
    """
    Serviço unificado para gerenciar publicações de mídia no Instagram.
    Combina funcionalidades de publicação de fotos e carrossel.
    """

    # Configurações de mídia do Instagram
    MEDIA_CONFIG = {
        'aspect_ratio': {
            'min': 4.0/5.0,  # Instagram minimum (4:5)
            'max': 1.91      # Instagram maximum (1.91:1)
        },
        'resolution': {
            'min': 320,
            'max': 1440
        },
        'size_limit_mb': 8,
        'formats': ['jpg', 'jpeg', 'png']
    }

    async def publish_photo(self, image_path: str, caption: str) -> Tuple[bool, str, Optional[str]]:
        """Publica uma única foto no Instagram"""
        try:
            # Criar container
            container_id = await self._create_media_container(image_path, caption)
            if not container_id:
                raise MediaError("Falha ao criar container de mídia")

            # Publicar
            result = await self._publish_container(container_id)
            return True, "Publicado com sucesso", result.get("id")
        except InstagramError as e:
            return False, str(e), None

    async def publish_carousel(self, image_paths: List[str], caption: str) -> Tuple[bool, str, Optional[str]]:
        """Publica um carrossel de fotos no Instagram"""
        try:
            # Criar containers para cada imagem
            containers = []
            for image in image_paths:
                container = await self._create_media_container(image)
                if not container:
                    raise MediaError(f"Falha ao criar container para {image}")
                containers.append(container)

            # Criar carrossel
            carousel_id = await self._create_carousel_container(containers, caption)
            if not carousel_id:
                raise MediaError("Falha ao criar container do carrossel")

            # Publicar
            result = await self._publish_container(carousel_id)
            return True, "Carrossel publicado com sucesso", result.get("id")
        except InstagramError as e:
            return False, str(e), None

    async def _create_media_container(self, image_path: str, caption: str = None) -> Optional[str]:
        """Cria um container para uma única mídia"""
        try:
            response = await self._make_request(
                'POST',
                f'{self.ig_user_id}/media',
                data={
                    'image_url': image_path,
                    'caption': caption,
                    'access_token': self.access_token
                }
            )
            return response.get('id')
        except Exception as e:
            raise MediaError(f"Erro ao criar container: {str(e)}")

    async def _create_carousel_container(self, media_ids: List[str], caption: str) -> Optional[str]:
        """Cria um container para carrossel"""
        try:
            response = await self._make_request(
                'POST',
                f'{self.ig_user_id}/media',
                data={
                    'media_type': 'CAROUSEL',
                    'children': media_ids,
                    'caption': caption,
                    'access_token': self.access_token
                }
            )
            return response.get('id')
        except Exception as e:
            raise MediaError(f"Erro ao criar container do carrossel: {str(e)}")

    async def _publish_container(self, container_id: str) -> Dict:
        """Publica um container de mídia"""
        try:
            return await self._make_request(
                'POST',
                f'{self.ig_user_id}/media_publish',
                data={
                    'creation_id': container_id,
                    'access_token': self.access_token
                }
            )
        except Exception as e:
            raise MediaError(f"Erro ao publicar: {str(e)}")

    def validate_media(self, file_path: str) -> None:
        """Valida se um arquivo de mídia está adequado para publicação"""
        # Implementar validações
        pass