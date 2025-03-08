# src/utils/video_decode_save.py
import os
import base64
import time
import logging
from src.utils.paths import Paths

class VideoDecodeSaver:
    """
    Classe para decodificar e salvar vídeos em base64 recebidos via webhook
    """
    
    @staticmethod
    def process(video_base64):
        """
        Processa um vídeo em formato base64, salvando-o como um arquivo MP4
        
        Args:
            video_base64 (str): String base64 do vídeo
            
        Returns:
            str: Caminho do arquivo salvo
        """
        try:
            # Remover cabeçalho do base64 se existir
            if "base64," in video_base64:
                video_base64 = video_base64.split("base64,")[1]
            
            # Decodificar base64
            video_data = base64.b64decode(video_base64)
            
            # Criar diretório de vídeos temporários se não existir
            temp_dir = os.path.join(Paths.ROOT_DIR, "temp_videos")
            os.makedirs(temp_dir, exist_ok=True)
            
            # Gerar nome de arquivo único
            filename = f"temp-{int(time.time() * 1000)}.mp4"
            filepath = os.path.join(temp_dir, filename)
            
            # Salvar o vídeo
            with open(filepath, "wb") as f:
                f.write(video_data)
            
            logging.info(f"Vídeo base64 salvo em: {filepath}")
            return filepath
            
        except Exception as e:
            logging.error(f"Erro ao processar vídeo base64: {str(e)}")
            raise Exception(f"Falha ao processar vídeo: {str(e)}")
    
    @staticmethod
    def cleanup_old_videos(max_age_hours=24):
        """
        Remove vídeos temporários antigos para gerenciar espaço em disco
        
        Args:
            max_age_hours (int): Idade máxima em horas antes da remoção
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
                        logging.info(f"Removido vídeo antigo: {file_path}")
                        
        except Exception as e:
            logging.error(f"Erro ao limpar vídeos antigos: {str(e)}")