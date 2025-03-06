import sys
import os
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
        pilgram.mayfair(im).save(image_path)
        
        return image_path

# Exemplo de uso:
#filepath = os.path.join(Paths.ROOT_DIR, "temp", "temp-1733594830377.png")
#image = FilterImage.process(filepath)
