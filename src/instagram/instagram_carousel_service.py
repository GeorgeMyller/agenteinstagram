import os
import requests
import time
from dotenv import load_dotenv

class InstagramCarouselService:
    """Classe para gerenciar o upload e publicação de carrosséis no Instagram."""
    
    def __init__(self):
        """Inicializa o serviço com as credenciais do Instagram."""
        load_dotenv()
        self.instagram_account_id = os.getenv("INSTAGRAM_ACCOUNT_ID")
        self.base_url = f'https://graph.facebook.com/v22.0/{self.instagram_account_id}'
        self.access_token = os.getenv('INSTAGRAM_API_KEY')
        self.session = requests.Session()

    def _make_request(self, method, url, **kwargs):
        """Faz uma requisição HTTP com melhor tratamento de erros."""
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            error_msg = f"Erro na requisição HTTP: {e}"
            if response := getattr(e, 'response', None):
                try:
                    error_data = response.json()
                    if 'error' in error_data:
                        error = error_data['error']
                        error_msg += f"\nCódigo: {error.get('code')}"
                        error_msg += f"\nMensagem: {error.get('message')}"
                        error_msg += f"\nTipo: {error.get('type')}"
                        if 'error_subcode' in error:
                            error_msg += f"\nSubcódigo: {error.get('error_subcode')}"
                except:
                    error_msg += f"\nResposta da API: {response.text}"
            print(error_msg)
            return None

    def _create_child_container(self, media_url):
        """Cria um contêiner filho para uma imagem do carrossel."""
        url = f'{self.base_url}/media'
        params = {
            'image_url': media_url,
            'is_carousel_item': 'true',
            'access_token': self.access_token
        }
        
        try:
            data = self._make_request('POST', url, data=params)
            
            if not data or 'id' not in data:
                print(f"Erro ao criar container filho: {data}")
                return None
                
            return data['id']
            
        except Exception as e:
            print(f"Erro ao criar container filho: {e}")
            return None

    def create_carousel_container(self, media_urls, caption):
        """Cria um contêiner de carrossel no Instagram."""
        url = f'{self.base_url}/media'
        
        # Create children containers first
        children = []
        for media_url in media_urls:
            child_container = self._create_child_container(media_url)
            if child_container:
                children.append(child_container)
            else:
                print(f"Falha ao criar container filho para: {media_url}")
                return None
        
        if not children:
            print("Nenhum container filho foi criado.")
            return None
        
        # Create carousel container
        params = {
            'media_type': 'CAROUSEL',
            'caption': caption,
            'children': ','.join(children),
            'access_token': self.access_token
        }
        
        try:
            data = self._make_request('POST', url, data=params)
            
            if not data or 'id' not in data:
                print(f"Erro ao criar container do carrossel: {data}")
                return None
                
            print(f"Container do carrossel criado com sucesso: {data['id']}")
            return data['id']
            
        except Exception as e:
            print(f"Erro ao criar container do carrossel: {e}")
            return None

    def wait_for_container_status(self, container_id, max_attempts=20, delay=5):
        """Verifica o status do container até estar pronto ou falhar."""
        url = f'{self.base_url}/{container_id}'
        
        for attempt in range(max_attempts):
            try:
                params = {
                    'fields': 'status_code,status',
                    'access_token': self.access_token
                }
                
                data = self._make_request('GET', url, params=params)
                
                if not data:
                    print("Erro ao verificar status do container")
                    return 'ERROR'
                
                if 'error' in data:
                    print(f"Erro ao verificar status do container: {data['error']}")
                    return 'ERROR'
                
                status = data.get('status_code', '')
                print(f"Status do container (tentativa {attempt + 1}/{max_attempts}): {status}")
                
                if status == 'FINISHED':
                    print("Processamento do carrossel concluído!")
                    return status
                elif status in ['ERROR', 'EXPIRED']:
                    print(f"Erro no processamento do carrossel: {status}")
                    if 'status' in data:
                        print(f"Detalhes do status: {data['status']}")
                    return status
                elif status in ['IN_PROGRESS', 'PROCESSING']:
                    print("Carrossel ainda em processamento...")
                elif status == 'SCHEDULED':
                    print("Carrossel agendado para publicação...")
                
                time.sleep(delay)
                
            except Exception as e:
                print(f"Erro ao verificar status: {e}")
                return 'ERROR'
        
        print("Tempo limite de processamento excedido")
        return 'TIMEOUT'

    def publish_carousel(self, container_id):
        """Publica o carrossel no Instagram."""
        url = f'{self.base_url}/media_publish'
        params = {
            'creation_id': container_id,
            'access_token': self.access_token
        }
        
        try:
            data = self._make_request('POST', url, data=params)
            
            if not data:
                return None
                
            if 'id' in data:
                print(f"Carrossel publicado com sucesso! ID: {data['id']}")
                return data['id']
            elif 'error' in data:
                error = data['error']
                print(f"Erro ao publicar carrossel:")
                print(f"Código: {error.get('code')}")
                print(f"Mensagem: {error.get('message')}")
                print(f"Mensagem para usuário: {error.get('error_user_msg', 'N/A')}")
            
            return None
                
        except Exception as e:
            print(f"Erro ao publicar carrossel: {e}")
            return None

    def post_carousel(self, media_urls, caption):
        """Realiza todo o processo de publicação de um carrossel."""
        # Create carousel container
        container_id = self.create_carousel_container(media_urls, caption)
        if not container_id:
            return None
            
        # Wait for container to be ready
        status = self.wait_for_container_status(container_id)
        if status != 'FINISHED':
            print(f"Container não ficou pronto. Status final: {status}")
            return None
            
        # Publish carousel
        return self.publish_carousel(container_id)