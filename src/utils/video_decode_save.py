# src/utils/video_decode_save.py
import base64
import os
import time
from src.utils.paths import Paths  # Use Paths para consistência

class VideoDecodeSaver:

    @staticmethod
    def process(base64_str, mimetype, directory='temp_videos'):
        """Decodifica um vídeo base64 e salva em um arquivo temporário.

        Args:
            base64_str: O vídeo em formato base64.
            mimetype: O mimetype do vídeo (ex: 'video/mp4').
            directory: O diretório onde salvar o vídeo.

        Returns:
            O caminho completo do arquivo de vídeo salvo.
        """
        timestamp_ms = int(time.time() * 1000)
        timestamp_str_ms = str(timestamp_ms)

        # Determinar a extensão do arquivo com base no mimetype
        if mimetype == 'video/mp4':
            extension = '.mp4'
        elif mimetype == 'video/quicktime':
            extension = '.mov'
        # Adicione outros mimetypes conforme necessário
        else:
            extension = '.mp4'  # Extensão padrão
            print(f"Warning: Mimetype desconhecido: {mimetype}. Usando .mp4")

        file_name = f"temp-{timestamp_str_ms}{extension}"

        # Garante que o diretório existe
        os.makedirs(os.path.join(Paths.ROOT_DIR, directory), exist_ok=True)

        # Cria o caminho completo do vídeo
        filepath = os.path.join(Paths.ROOT_DIR, directory, file_name)

        # Decodifica e salva o vídeo
        video_data = base64.b64decode(base64_str)
        with open(filepath, 'wb') as f:
            f.write(video_data)

        return filepath