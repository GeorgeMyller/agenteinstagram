import os
import time
from typing import List, Optional, Tuple
from src.utils.image_decode_save import ImageDecodeSaver
from src.services.instagram_send import InstagramSend
from src.instagram.describe_carousel_tool import CarouselDescriber
from src.instagram.crew_post_instagram import InstagramPostCrew
from src.instagram.image_validator import InstagramImageValidator
from src.instagram.carousel_normalizer import CarouselNormalizer
from src.instagram.filter import FilterImage
from src.services.send import sender

class CarouselModeHandler:
    """Handles the carousel mode functionality for Instagram posts"""
    
    TIMEOUT = 300  # 5 minutes in seconds
    MAX_IMAGES = 10
    
    def __init__(self):
        self.is_active = False
        self.images: List[str] = []
        self.caption: str = ""
        self.start_time: float = 0
        self.border_image_path: Optional[str] = None

    def activate(self, initial_caption: str = "", border_image_path: Optional[str] = None) -> str:
        """Activate carousel mode with optional initial caption"""
        self.is_active = True
        self.images = []
        self.caption = initial_caption.strip()
        self.start_time = time.time()
        self.border_image_path = border_image_path
        
        instructions = (
            "🎠 *Modo carrossel ativado!*\n\n"
            "- Envie as imagens que deseja incluir no carrossel (2-10 imagens)\n"
            "- Para definir uma legenda, envie \"legenda: sua legenda aqui\"\n"
            "- Quando terminar, envie \"postar\" para publicar o carrossel\n"
            "- Para cancelar, envie \"cancelar\"\n\n"
            "O modo carrossel será desativado automaticamente após 5 minutos de inatividade."
        )
        
        if self.caption:
            return f"{instructions}\n\nLegenda inicial definida: {self.caption}"
        return instructions

    def deactivate(self) -> None:
        """Deactivate carousel mode and clear state"""
        self.is_active = False
        self.images = []
        self.caption = ""
        self.start_time = 0

    def is_timed_out(self) -> bool:
        """Check if carousel mode has timed out"""
        return time.time() - self.start_time > self.TIMEOUT

    def add_image(self, image_base64: str) -> Tuple[bool, str]:
        """Add an image to the carousel. Returns (success, message)"""
        if len(self.images) >= self.MAX_IMAGES:
            return False, f"⚠️ Limite máximo de {self.MAX_IMAGES} imagens atingido! Envie \"postar\" para publicar."
            
        image_path = ImageDecodeSaver.process(image_base64)
        self.images.append(image_path)
        self.start_time = time.time()  # Reset timeout
        
        if len(self.images) >= 2:
            return True, f"✅ Imagem {len(self.images)} adicionada ao carrossel.\nVocê pode enviar mais imagens ou enviar \"postar\" para publicar."
        return True, f"✅ Imagem {len(self.images)} adicionada ao carrossel.\nEnvie pelo menos mais uma imagem para completar o carrossel."

    def set_caption(self, caption: str) -> str:
        """Set carousel caption. Returns confirmation message."""
        self.caption = caption.strip()
        self.start_time = time.time()  # Reset timeout
        return f"✅ Legenda definida: \"{self.caption}\""

    def can_post(self) -> bool:
        """Check if carousel has enough images to post"""
        return len(self.images) >= 2

    async def post(self) -> Tuple[bool, str, Optional[str]]:
        """
        Post the carousel to Instagram.
        Returns (success, message, job_id)
        """
        if not self.can_post():
            return False, f"⚠️ São necessárias pelo menos 2 imagens para criar um carrossel. Você tem apenas {len(self.images)} imagem.", None

        try:
            # Primeiro passo: redimensionar todas as imagens para garantir que estejam dentro dos limites do Instagram
            resized_images = []
            for image_path in self.images:
                try:
                    # Caso a imagem esteja em formato base64, usar ImageDecodeSaver para processar
                    if image_path.startswith("data:image") or ";base64," in image_path:
                        image_path = ImageDecodeSaver.process(image_path)
                        
                    # Garantir que a imagem tenha dimensões adequadas para o Instagram (máximo 1440x1440)
                    resized_path = InstagramImageValidator.resize_for_instagram(image_path)
                    resized_images.append(resized_path)
                except Exception as e:
                    print(f"Erro ao redimensionar imagem {image_path}: {str(e)}")
                    resized_images.append(image_path)  # Use original if resizing fails
            
            # Segundo passo: normalizar as imagens para terem a mesma proporção (requisito do Instagram)
            normalized_paths = CarouselNormalizer.normalize_carousel_images(resized_images)
            
            # Se a normalização falhar, use as imagens redimensionadas
            if not normalized_paths or len(normalized_paths) < 2:
                print("Aviso: Falha ao normalizar imagens do carrossel. Usando versões redimensionadas.")
                normalized_paths = resized_images
            
            # Process images (add borders)
            processed_images = []
            for image_path in normalized_paths:
                try:
                    # Apply border if available
                    if self.border_image_path and os.path.exists(self.border_image_path):
                        processed_image = FilterImage.apply_border(image_path, self.border_image_path)
                    else:
                        processed_image = image_path
                        
                    processed_images.append(processed_image)
                except Exception as e:
                    print(f"Erro ao processar imagem {image_path}: {str(e)}")
                    processed_images.append(image_path)  # Use original if processing fails

            # Generate caption if none provided
            caption_to_use = self.caption
            if not caption_to_use:
                try:
                    image_descriptions = CarouselDescriber.describe(processed_images)
                    crew = InstagramPostCrew()
                    inputs_dict = {
                        "genero": "Neutro",
                        "caption": image_descriptions,
                        "describe": image_descriptions,
                        "estilo": "Divertido, Alegre, Sarcástico e descontraído",
                        "pessoa": "Terceira pessoa do singular",
                        "sentimento": "Positivo",
                        "tamanho": "200 palavras",
                        "emojs": "sim",
                        "girias": "sim"
                    }
                    caption_to_use = crew.kickoff(inputs=inputs_dict)
                except Exception as e:
                    print(f"Erro ao gerar legenda automática: {str(e)}")
                    caption_to_use = "Carrossel de imagens publicado via webhook"

            # Queue the carousel for posting
            job_id = InstagramSend.queue_carousel(processed_images, caption_to_use)
            return True, f"✅ Carrossel enfileirado com sucesso!\nID do trabalho: {job_id}", job_id

        except Exception as e:
            error_msg = f"❌ Erro ao enfileirar carrossel: {str(e)}"
            print(error_msg)
            return False, error_msg, None