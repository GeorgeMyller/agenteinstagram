import os
import time
import json
import base64
import requests
import mimetypes
from PIL import Image
from src.utils.paths import Paths

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import tempfile
from dotenv import load_dotenv
from imgurpython import ImgurClient

class ImageUploader():
    def __init__(self):
        """
        Inicializa o cliente Imgur com as credenciais obtidas do arquivo .env.
        """
        load_dotenv()
        self.client_id = os.getenv("IMGUR_CLIENT_ID")
        self.client_secret = os.getenv("IMGUR_CLIENT_SECRET")

        if not self.client_id or not self.client_secret:
            raise ValueError("As credenciais do Imgur não foram configuradas corretamente.")

        self.client = ImgurClient(self.client_id, self.client_secret)
        


    def upload_from_path(self, image_path: str) -> dict:
        """
        Faz o upload de uma imagem localizada no sistema de arquivos.

        :param image_path: Caminho absoluto da imagem a ser enviada.
        :return: Dicionário contendo id, url, e deletehash da imagem enviada.
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"O arquivo especificado não foi encontrado: {image_path}")

        uploaded_image = self.client.upload_from_path(image_path, config=None, anon=True)
        return {
            "id": uploaded_image["id"],
            "url": uploaded_image["link"],
            "deletehash": uploaded_image["deletehash"],
            "image_path":image_path
        }

    def upload_from_base64(self, image_base64: str) -> dict:
        """
        Faz o upload de uma imagem fornecida como string Base64.

        :param image_base64: String contendo os dados da imagem em Base64.
        :return: Dicionário contendo id, url, e deletehash da imagem enviada.
        """
        try:
            # Decodificar Base64 para bytes
            image_data = base64.b64decode(image_base64)

            # Abrir a imagem em memória para verificar a qualidade
            image = Image.open(io.BytesIO(image_data))

            # Salvar a imagem como PNG sem compressão em um arquivo temporário
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_image:
                image.save(temp_image.name, format="PNG", optimize=False)
                temp_image_path = temp_image.name

            # Fazer o upload usando o caminho do arquivo temporário
            return self.upload_from_path(temp_image_path)
        except:
            
            print('Erro em enviar imagem ao IMGUR')
            # Garantir que o arquivo temporário seja excluído
            #if 'temp_image_path' in locals() and os.path.exists(temp_image_path):
            #    os.remove(temp_image_path)


    def delete_image(self, deletehash: str) -> bool:
        """
        Deleta uma imagem no Imgur usando o deletehash.

        :param deletehash: Código único fornecido pelo Imgur no momento do upload.
        :return: True se a imagem foi deletada com sucesso, False caso contrário.
        """
        try:
            self.client.delete_image(deletehash)
            return True
        except Exception as e:
            print(f"Erro ao deletar a imagem: {e}")
            return False

#filepath = os.path.join(Paths.ROOT_DIR, "temp", "temp-1733594830377.png")
#img = ImageUploader()
#imgs = img.upload_from_path(filepath)

#i=0