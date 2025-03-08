import sys
import os
import time
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import os
from PIL import Image
import pilgram
import logging

logger = logging.getLogger(__name__)

class FilterImage:
    @staticmethod
    def process(image_path):
        """
        Processa a imagem aplicando um filtro (mayfair),
        depois salva a imagem resultante em ajuste.png.
        """
        try:
            im = Image.open(image_path)
            logger.info(f"Original Image - Size: {im.size}, Format: {im.format}, Mode: {im.mode}") # Consistent logging
            filtered_image = pilgram.mayfair(im)
            filtered_image.save(image_path)
            logger.info(f"Filtered Image - Size: {filtered_image.size}, Format: {filtered_image.format}, Mode: {filtered_image.mode}") # Consistent logging
            return image_path
        except Exception as e:
            logger.exception(f"Erro ao processar imagem: {e}") # Use logger.exception
            raise

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
                    try:
                        os.remove(file_path)
                        logger.info(f"Removed old temp file: {file_path}") # Consistent logging
                    except Exception as e:
                        logger.warning(f"Erro ao remover arquivo temporário: {e}")