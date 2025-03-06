import sys
import os
import shutil
import time
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import os
from PIL import Image
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

# Exemplo de uso:
# filepath = os.path.join(Paths.ROOT_DIR, "temp", "temp-1733594830377.png")
# image = FilterImage.process(filepath)
# FilterImage.clean_temp_directory(os.path.join(Paths.ROOT_DIR, "temp"))
