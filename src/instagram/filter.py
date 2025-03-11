import sys
import os
import time
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import os
from PIL import Image, ImageOps
import pilgram


class FilterImage:
    
    @staticmethod
    def process(image_path):
        """
        Processa a imagem aplicando um filtro (mayfair),
        depois salva a imagem resultante em ajuste.png.
        """
        im = Image.open(image_path)
        
        # Log original image attributes
        print(f"Original Image - Size: {im.size}, Format: {im.format}, Mode: {im.mode}")
        
        # Apply filter and save the image
        filtered_image = pilgram.mayfair(im)
        filtered_image.save(image_path)
        
        # Log filtered image attributes
        print(f"Filtered Image - Size: {filtered_image.size}, Format: {filtered_image.format}, Mode: {filtered_image.mode}")
        
        return image_path

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
        Aplica uma borda à imagem fornecida.

        Args:
            image_path (str): Caminho da imagem original.
            border_path (str): Caminho da imagem da borda.

        Returns:
            str: Caminho da imagem com a borda aplicada.
        """
        try:
            # Abrir a imagem original e a borda
            original_image = Image.open(image_path)
            border_image = Image.open(border_path)

            # Redimensionar a borda para corresponder ao tamanho da imagem original
            border_image = border_image.resize(original_image.size, Image.LANCZOS)

            # Aplicar a borda à imagem original
            bordered_image = ImageOps.fit(original_image, border_image.size)
            bordered_image.paste(border_image, (0, 0), border_image)

            # Salvar a imagem com a borda aplicada
            bordered_image_path = os.path.join(os.path.dirname(image_path), f"bordered_{os.path.basename(image_path)}")
            bordered_image.save(bordered_image_path)

            return bordered_image_path
        except Exception as e:
            print(f"Erro ao aplicar borda à imagem: {e}")
            raise

# Exemplo de uso:
# filepath = os.path.join(Paths.ROOT_DIR, "temp", "temp-1733594830377.png")
# image = FilterImage.process(filepath)
# FilterImage.clean_temp_directory(os.path.join(Paths.ROOT_DIR, "temp"))
