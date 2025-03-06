import os
import requests
import time
from dotenv import load_dotenv
# from your_upload_service import YourUploadClient  # Substitua pelo seu cliente

class VideoUploader:
    def __init__(self):
        load_dotenv()
        # self.client = YourUploadClient(...)  # Inicialize seu cliente aqui

    def upload_from_path(self, video_path):
        # Lógica para upload a partir do caminho do arquivo
        pass

    def upload_from_url(self, video_url):
        # Lógica para upload a partir de URL (download e upload)
        pass

    def upload_thumbnail(self, thumbnail_path):
        # Lógica para upload de thumbnail (opcional)
        pass

    def delete_video(self, deletehash):
        # Lógica para exclusão
        pass
    
    def validate_video(self, video_path):
        from src.instagram.instagram_video_processor import VideoProcessor  # Importe aqui para evitar circular imports
        video_info = VideoProcessor.get_video_info(video_path)
        if not video_info:
            return False, "Não foi possível obter informações do vídeo."
        
        duration = float(video_info['duration'])
        width = video_info['width']
        height = video_info['height']
        video_codec = video_info.get('codec', '')
        audio_codec = video_info.get('audio_codec', '')
        
        is_valid = True
        messages = []
        if not VideoProcessor.check_duration(duration, 'reels'):  # Exemplo: validando para Reels
            is_valid = False
            messages.append("Duração do vídeo inválida.")
        if not VideoProcessor.check_resolution(width, height, 'reels'):
            is_valid = False
            messages.append("Resolução do vídeo inválida.")
        if not VideoProcessor.check_codec(video_codec, audio_codec):
            is_valid = False
            messages.append("Codec de vídeo ou áudio inválido")
        if not VideoProcessor.check_aspect_ratio(width, height, 'reels'):
            is_valid = False
            messages.append("Proporção do vídeo inválida")
        return is_valid, ", ".join(messages)