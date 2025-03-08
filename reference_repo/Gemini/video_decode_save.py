import os
import base64
import time
import logging  # Import logging
from src.utils.paths import Paths

logger = logging.getLogger(__name__) # Consistent logging


class VideoDecodeSaver:
    """
    Classe para decodificar e salvar vídeos em base64 recebidos via webhook
    """
    @staticmethod
    def process(video_base64):
        """
        Processa um vídeo em formato base64, salvando-o como um arquivo MP4
        """
        try:
            if "base64," in video_base64:
                video_base64 = video_base64.split("base64,")[1]
            video_data = base64.b64decode(video_base64)
            temp_dir = os.path.join(Paths.ROOT_DIR, "temp_videos")
            os.makedirs(temp_dir, exist_ok=True)
            filename = f"temp-{int(time.time() * 1000)}.mp4"
            filepath = os.path.join(temp_dir, filename)
            with open(filepath, "wb") as f:
                f.write(video_data)
            logger.info(f"Vídeo base64 salvo em: {filepath}")  # Use logger
            return filepath
        except Exception as e:
            logger.exception(f"Erro ao processar vídeo base64: {str(e)}")  # Use logger.exception
            raise  # Re-raise the exception

    @staticmethod
    def cleanup_old_videos(max_age_hours=24):
        """
        Remove vídeos temporários antigos para gerenciar espaço em disco
        """
        try:
            temp_dir = os.path.join(Paths.ROOT_DIR, "temp_videos")
            if not os.path.exists(temp_dir):
                return
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600
            for file in os.listdir(temp_dir):
                if file.startswith("temp-") and file.endswith(".mp4"):
                    file_path = os.path.join(temp_dir, file)
                    file_age = current_time - os.path.getmtime(file_path)
                    if file_age > max_age_seconds:
                        os.remove(file_path)
                        logger.info(f"Removido vídeo antigo: {file_path}") # Use logger
        except Exception as e:
            logger.error(f"Erro ao limpar vídeos antigos: {str(e)}") # Use logger