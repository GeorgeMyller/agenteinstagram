import os
import requests
from dotenv import load_dotenv

class InstagramPostService:
    load_dotenv()

    def __init__(self):
        self.instagram_account_id = os.getenv("INSTAGRAM_ACCOUNT_ID")
        self.base_url = f'https://graph.facebook.com/v22.0/{self.instagram_account_id}'
        self.access_token = os.getenv('INSTAGRAM_API_KEY')

    def create_media_container(self, image_url, caption):
        """
        Cria um contêiner de mídia para o post.
        :param image_url: URL da imagem a ser postada.
        :param caption: Legenda da postagem.
        :return: ID do contêiner de mídia ou None em caso de erro.
        """
        url = f'{self.base_url}/media'
        payload = {
            'image_url': image_url,
            'caption': caption,
            'access_token': self.access_token
        }

        response = requests.post(url, data=payload)
        response_data = response.json()

        if 'id' not in response_data:
            print(f"Erro ao criar contêiner de mídia: {response_data}")
            return None

        return response_data['id']

    def publish_media(self, media_container_id):
        """
        Publica o contêiner de mídia no Instagram.
        :param media_container_id: ID do contêiner de mídia.
        :return: ID do post publicado ou None em caso de erro.
        """
        url = f'{self.base_url}/media_publish'
        payload = {
            'creation_id': media_container_id,
            'access_token': self.access_token
        }

        response = requests.post(url, data=payload)
        response_data = response.json()

        if 'id' not in response_data:
            print(f"Erro ao publicar o post: {response_data}")
            return None

        print(f"Post publicado com sucesso! ID do Post: {response_data['id']}")
        return response_data['id']

    def post_image(self, image_url, caption):
        """
        Faz todo o fluxo de criação e publicação de um post no Instagram.
        :param image_url: URL da imagem a ser postada.
        :param caption: Legenda da postagem.
        :return: ID do post publicado ou None em caso de erro.
        """
        print("Iniciando publicação de imagem no Instagram...")

        media_container_id = self.create_media_container(image_url, caption)
        if not media_container_id:
            print("Falha na criação do contêiner de mídia. Interrompendo o processo.")
            return None

        post_id = self.publish_media(media_container_id)
        if not post_id:
            print("Falha na publicação do post.")
            return None

        print(f"Processo concluído com sucesso! ID do Post: {post_id}")
        return post_id
