import os
import time
import requests
from dotenv import load_dotenv

class InstagramPostService:
    load_dotenv()

    def __init__(self):
        self.instagram_account_id = os.getenv("INSTAGRAM_ACCOUNT_ID")
        self.base_url = f'https://graph.facebook.com/v22.0/{self.instagram_account_id}'
        self.access_token = os.getenv('INSTAGRAM_API_KEY')
        self.max_retries = 3
        self.base_delay = 5  # Base delay in seconds

    def _handle_error_response(self, response_data):
        """
        Handle different types of Instagram API errors
        """
        if 'error' not in response_data:
            return False, "Unknown error occurred"

        error = response_data['error']
        error_code = error.get('code')
        error_subcode = error.get('error_subcode')

        if error_code == 4:  # Application request limit reached
            return True, "Rate limit reached"
        elif error_code == 190:  # Invalid access token
            return False, "Invalid access token"
        elif error_code in [24, 1, 2]:  # Generic API errors
            return True, f"Generic API error: {error.get('message')}"
        
        return False, error.get('message', 'Unknown error occurred')

    def _make_request_with_retry(self, method, url, payload):
        """
        Make API request with exponential backoff retry logic
        """
        for attempt in range(self.max_retries):
            try:
                response = method(url, data=payload)
                response_data = response.json()

                if 'error' in response_data:
                    should_retry, error_msg = self._handle_error_response(response_data)
                    if should_retry and attempt < self.max_retries - 1:
                        delay = self.base_delay * (2 ** attempt)  # Exponential backoff
                        print(f"Attempt {attempt + 1} failed. Retrying in {delay} seconds...")
                        time.sleep(delay)
                        continue
                    else:
                        print(f"Error: {error_msg}")
                        return None
                return response_data
            except requests.exceptions.RequestException as e:
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2 ** attempt)
                    print(f"Request failed: {str(e)}. Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    print(f"All retry attempts failed: {str(e)}")
                    return None
        return None

    def create_media_container(self, image_url, caption):
        """
        Cria um contêiner de mídia para o post com retry logic.
        """
        url = f'{self.base_url}/media'
        payload = {
            'image_url': image_url,
            'caption': caption,
            'access_token': self.access_token
        }

        response_data = self._make_request_with_retry(requests.post, url, payload)
        if response_data and 'id' in response_data:
            return response_data['id']
        return None

    def publish_media(self, media_container_id):
        """
        Publica o contêiner de mídia no Instagram com retry logic.
        """
        url = f'{self.base_url}/media_publish'
        payload = {
            'creation_id': media_container_id,
            'access_token': self.access_token
        }

        response_data = self._make_request_with_retry(requests.post, url, payload)
        if response_data and 'id' in response_data:
            print(f"Post publicado com sucesso! ID do Post: {response_data['id']}")
            return response_data['id']
        return None

    def post_image(self, image_url, caption):
        """
        Faz todo o fluxo de criação e publicação de um post no Instagram.
        """
        print("Iniciando publicação de imagem no Instagram...")

        media_container_id = self.create_media_container(image_url, caption)
        if not media_container_id:
            print("Falha na criação do contêiner de mídia. Interrompendo o processo.")
            return None