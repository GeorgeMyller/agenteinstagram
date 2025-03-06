import base64
import os
import time
from src.utils.paths import Paths

class ImageDecodeSaver:

    @staticmethod
    def process(base64_str, directory='temp'):
        
        timestamp_ms = int(time.time() * 1000)
        timestamp_str_ms = str(timestamp_ms)
        
        file_name = f"temp-{timestamp_str_ms}.png"
        
        """
        Cria o diretório se necessário e salva a imagem no local especificado.
        
        Retorna o caminho completo do arquivo salvo.
        """
        
        # Garante que o diretório existe
        os.makedirs(directory, exist_ok=True)
        
        # Cria o caminho completo da imagem
        filepath = os.path.join(Paths.ROOT_DIR, directory, file_name)
        
        # Decodifica e salva a imagem
        image_data = base64.b64decode(base64_str)
        with open(filepath, 'wb') as f:
            f.write(image_data)

        return filepath



