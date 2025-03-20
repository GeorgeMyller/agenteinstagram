import sys
import os
import time
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import os
from PIL import Image, ImageOps
import pilgram


class FilterImage:
    # Instagram API requirements
    MIN_IMG_SIZE = 320  # Minimum size in pixels (each dimension)
    MAX_IMG_SIZE = 1080  # Maximum recommended size in pixels (each dimension)
    MAX_ABSOLUTE_SIZE = 1440  # Maximum allowed size in pixels (each dimension)
    MIN_ASPECT_RATIO = 0.8  # 4:5 portrait orientation
    MAX_ASPECT_RATIO = 1.91  # Landscape orientation
    
    @staticmethod
    def process(image_path):
        """
        Processa a imagem aplicando um filtro (mayfair),
        depois salva a imagem resultante no mesmo caminho.
        Agora também garante que a imagem esteja em conformidade com os requisitos do Instagram.
        """
        im = Image.open(image_path)
        
        # Log original image attributes
        print(f"Original Image - Size: {im.size}, Format: {im.format}, Mode: {im.mode}")
        
        # Apply filter
        filtered_image = pilgram.mayfair(im)
        
        # Ensure image meets Instagram requirements
        filtered_image = FilterImage.ensure_instagram_compatibility(filtered_image)
        
        # Log filtered image attributes
        print(f"Filtered Image - Size: {filtered_image.size}, Format: None, Mode: {filtered_image.mode}")
        
        # Save the image in JPEG format with high quality
        filtered_image.save(image_path, format="JPEG", quality=95)
        
        return image_path

    @staticmethod
    def ensure_instagram_compatibility(image):
        """
        Ensure the image meets Instagram's requirements:
        - Proper dimensions (not exceeding max size)
        - Proper aspect ratio
        - RGB mode
        
        Args:
            image (PIL.Image): The image to process
            
        Returns:
            PIL.Image: The processed image ready for Instagram
        """
        width, height = image.size
        aspect_ratio = width / height if height > 0 else 0
        needs_resize = False
        needs_crop = False
        
        # Check if dimensions need adjustment
        if width > FilterImage.MAX_IMG_SIZE or height > FilterImage.MAX_IMG_SIZE:
            needs_resize = True
            print(f"Image exceeds recommended size ({width}x{height}), will resize")
        
        # Check if aspect ratio is within acceptable range
        if aspect_ratio < FilterImage.MIN_ASPECT_RATIO:
            print(f"Aspect ratio too narrow ({aspect_ratio:.2f}), will crop to {FilterImage.MIN_ASPECT_RATIO}")
            needs_crop = True
        elif aspect_ratio > FilterImage.MAX_ASPECT_RATIO:
            print(f"Aspect ratio too wide ({aspect_ratio:.2f}), will crop to {FilterImage.MAX_ASPECT_RATIO}")
            needs_crop = True
        
        # First resize if needed
        if needs_resize:
            if width > height:
                # Landscape orientation
                new_width = min(width, FilterImage.MAX_IMG_SIZE)
                scale_factor = new_width / width
                new_height = int(height * scale_factor)
            else:
                # Portrait or square orientation
                new_height = min(height, FilterImage.MAX_IMG_SIZE)
                scale_factor = new_height / height
                new_width = int(width * scale_factor)
            
            # Ensure dimensions are within absolute limits
            if new_width > FilterImage.MAX_ABSOLUTE_SIZE:
                new_width = FilterImage.MAX_ABSOLUTE_SIZE
            if new_height > FilterImage.MAX_ABSOLUTE_SIZE:
                new_height = FilterImage.MAX_ABSOLUTE_SIZE
                
            try:
                image = image.resize((new_width, new_height), resample=Image.LANCZOS)
                print(f"Image resized to meet Instagram requirements: {new_width}x{new_height}")
                
                # Update width and height after resize
                width, height = image.size
                aspect_ratio = width / height if height > 0 else 0
                
                # Check if we still need to crop after resize
                if aspect_ratio < FilterImage.MIN_ASPECT_RATIO or aspect_ratio > FilterImage.MAX_ASPECT_RATIO:
                    needs_crop = True
            except AttributeError:
                # Fallback for older versions of PIL
                image = image.resize((new_width, new_height), Image.ANTIALIAS)
                print(f"Image resized to meet Instagram requirements: {new_width}x{new_height}")
                
                # Update width and height after resize
                width, height = image.size
                aspect_ratio = width / height if height > 0 else 0
                
                # Check if we still need to crop after resize
                if aspect_ratio < FilterImage.MIN_ASPECT_RATIO or aspect_ratio > FilterImage.MAX_ASPECT_RATIO:
                    needs_crop = True
        
        # Now crop if needed to fix aspect ratio
        if needs_crop:
            if aspect_ratio < FilterImage.MIN_ASPECT_RATIO:
                # Image is too tall - crop height
                new_height = int(width / FilterImage.MIN_ASPECT_RATIO)
                top_margin = (height - new_height) // 2
                bottom_margin = top_margin + new_height
                image = image.crop((0, top_margin, width, bottom_margin))
                print(f"Image cropped to fix aspect ratio: new size {width}x{new_height}, ratio: {FilterImage.MIN_ASPECT_RATIO}")
                
            elif aspect_ratio > FilterImage.MAX_ASPECT_RATIO:
                # Image is too wide - crop width
                new_width = int(height * FilterImage.MAX_ASPECT_RATIO)
                left_margin = (width - new_width) // 2
                right_margin = left_margin + new_width
                image = image.crop((left_margin, 0, right_margin, height))
                print(f"Image cropped to fix aspect ratio: new size {new_width}x{height}, ratio: {FilterImage.MAX_ASPECT_RATIO}")
            
        # Ensure RGB mode (Instagram doesn't accept RGBA)
        if image.mode != 'RGB':
            # If RGBA, convert to RGB with white background
            if image.mode == 'RGBA':
                background = Image.new('RGB', image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[3])  # 3 is the alpha channel
                image = background
            else:
                image = image.convert('RGB')
            print(f"Image converted to RGB mode from {image.mode}")
            
        return image

    @staticmethod
    def clean_temp_directory(temp_dir, max_age_seconds=3600):
        """
        Limpa o diretório temporário removendo arquivos mais antigos que max_age_seconds.
        """
        now = time.time()
        for filename in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, filename)
            if os.path.isfile(file_path):
                file_age = now - os.path.getmtime(file_path)
                if file_age > max_age_seconds:
                    os.remove(file_path)
                    print(f"Removed old temp file: {file_path}")

    @staticmethod
    def apply_border(image_path: str, border_path: str) -> str:
        """
        Aplica uma borda à imagem fornecida, ajustando a borda perfeitamente
        ao tamanho da imagem original sem distorção.

        Args:
            image_path (str): Caminho da imagem original.
            border_path (str): Caminho da imagem da borda.

        Returns:
            str: Caminho da imagem com a borda aplicada.
        """
        try:
            # Abrir a imagem original
            original_image = Image.open(image_path)
            print(f"Imagem original - Tamanho: {original_image.size}, Modo: {original_image.mode}")
            
            # Abrir a imagem da borda
            border_image = Image.open(border_path)
            print(f"Imagem de borda original - Tamanho: {border_image.size}, Modo: {border_image.mode}")
            
            # Converter a imagem original para RGBA se não estiver nesse formato
            if original_image.mode != "RGBA":
                original_image = original_image.convert("RGBA")
                
            # Redimensionar a borda para corresponder exatamente ao tamanho da imagem original
            try:
                # Tente usar LANCZOS (melhor qualidade) com fallback para ANTIALIAS (versões mais antigas do PIL)
                border_image = border_image.resize(original_image.size, resample=Image.LANCZOS)
            except AttributeError:
                border_image = border_image.resize(original_image.size, resample=Image.ANTIALIAS)
                
            print(f"Borda redimensionada para: {border_image.size}")
            
            # Criar uma nova imagem composta
            composite_image = Image.new("RGBA", original_image.size, (0, 0, 0, 0))
            
            # Primeiro colocar a imagem original na composição
            composite_image.paste(original_image, (0, 0))
            
            # Depois aplicar a borda por cima (preservando a transparência)
            if border_image.mode != "RGBA":
                border_image = border_image.convert("RGBA")
                
            composite_image.paste(border_image, (0, 0), border_image)
            
            # Apply Instagram compatibility resizing and format conversions
            composite_image = FilterImage.ensure_instagram_compatibility(composite_image)
            
            # Salvar a imagem com a borda aplicada
            bordered_image_path = os.path.join(os.path.dirname(image_path), f"bordered_{os.path.basename(image_path)}")
            
            # Save as JPEG for best compatibility with Instagram
            composite_image.save(bordered_image_path, format="JPEG", quality=95)
            print(f"Imagem com borda salva em: {bordered_image_path}")
            
            return bordered_image_path
        except Exception as e:
            print(f"Erro ao aplicar borda à imagem: {e}")
            raise

# Exemplo de uso:
# filepath = os.path.join(Paths.ROOT_DIR, "temp", "temp-1733594830377.png")
# image = FilterImage.process(filepath)
# FilterImage.clean_temp_directory(os.path.join(Paths.ROOT_DIR, "temp"))
