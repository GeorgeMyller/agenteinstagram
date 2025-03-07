import os
import requests
import time
import json
from dotenv import load_dotenv
from typing import Optional, List, Dict, Any

class RateLimitError(Exception):
    def __init__(self, message: str, retry_seconds: int = 300):
        super().__init__(message)
        self.retry_seconds = retry_seconds

class InstagramCarouselService:
    """Classe para gerenciar o upload e publicação de carrosséis no Instagram."""
    
    API_VERSION = "v22.0"  # Latest stable version
    SUPPORTED_MEDIA_TYPES = ["image/jpeg", "image/png"]
    MAX_MEDIA_SIZE = 8 * 1024 * 1024  # 8MB in bytes
    
    def __init__(self):
        """Inicializa o serviço com as credenciais do Instagram."""
        load_dotenv()
        self.instagram_account_id = os.getenv("INSTAGRAM_ACCOUNT_ID")
        if not self.instagram_account_id:
            raise ValueError("INSTAGRAM_ACCOUNT_ID environment variable is not set")
            
        self.access_token = os.getenv('INSTAGRAM_API_KEY')
        if not self.access_token:
            raise ValueError("INSTAGRAM_API_KEY environment variable is not set")
            
        self.base_url = f'https://graph.facebook.com/{self.API_VERSION}/{self.instagram_account_id}'
        self.session = requests.Session()
        self.rate_limit_window = 3600  # 1 hour
        self.rate_limit_max_calls = 200  # Default safe limit
        self.last_request_time = 0
        self.min_request_interval = 1.0  # Minimum seconds between requests

    def _validate_media(self, media_url: str) -> bool:
        """Validates media URL and type before uploading."""
        try:
            # Check if URL is accessible
            response = requests.head(media_url, timeout=10)
            if response.status_code != 200:
                print(f"Media URL not accessible: {media_url}")
                return False
                
            # Check content type
            content_type = response.headers.get('content-type', '').lower()
            if content_type not in self.SUPPORTED_MEDIA_TYPES:
                print(f"Unsupported media type: {content_type}")
                return False
                
            # Check file size
            content_length = int(response.headers.get('content-length', 0))
            if content_length > self.MAX_MEDIA_SIZE:
                print(f"Media file too large: {content_length} bytes")
                return False
                
            return True
        except Exception as e:
            print(f"Error validating media: {str(e)}")
            return False

    def _respect_rate_limits(self):
        """Ensures requests respect rate limits."""
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        
        if elapsed < self.min_request_interval:
            sleep_time = self.min_request_interval - elapsed
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()

    def _make_request(self, method: str, url: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Faz uma requisição HTTP com melhor tratamento de erros."""
        self._respect_rate_limits()
        
        try:
            response = self.session.request(method, url, timeout=30, **kwargs)
            self._log_rate_limit_info(response)
            
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 300))
                raise RateLimitError(f"Rate limit exceeded", retry_after)
                
            response.raise_for_status()
            
            if not response.content:
                return None
                
            data = response.json()
            
            if 'error' in data:
                error = data['error']
                error_code = error.get('code')
                error_message = error.get('message', '')
                
                if error_code in [4, 17, 32, 613]:  # Rate limit error codes
                    retry_seconds = self._get_retry_time_from_error(error)
                    raise RateLimitError(error_message, retry_seconds)
                    
                print(f"API Error: {error_message} (Code: {error_code})")
                return None
                
            return data
            
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {str(e)}")
            return None

    def _log_rate_limit_info(self, response):
        """Extrai e loga informações de rate limit dos cabeçalhos da resposta"""
        if 'x-business-use-case-usage' in response.headers:
            usage_info = response.headers['x-business-use-case-usage']
            try:
                usage_data = json.loads(usage_info)
                print("Rate limit data from x-business-use-case-usage:")
                print(f"  Business Usage: {usage_data}")
                
                # Processar cada app ID
                for app_id, metrics in usage_data.items():
                    if isinstance(metrics, list) and metrics:
                        rate_data = metrics[0]
                        print(f"  {app_id}: {rate_data}")
                        if 'estimated_time_to_regain_access' in rate_data:
                            print(f"  Business estimated time to regain access: {rate_data['estimated_time_to_regain_access']}s")
                        if 'call_count' in rate_data:
                            print(f"  call_count: {rate_data['call_count']}%")
                        if 'total_cputime' in rate_data:
                            print(f"  total_cputime: {rate_data['total_cputime']}%") 
                        if 'total_time' in rate_data:
                            print(f"  total_time: {rate_data['total_time']}%")
            except json.JSONDecodeError:
                print(f"Erro ao decodificar informações de rate limit: {usage_info}")
    
    def _get_retry_time_from_error(self, error):
        """Extrai o tempo de espera recomendado a partir de um erro de rate limit"""
        # Tenta obter o tempo de retry dos dados de erro
        if 'error_data' in error and 'error_subcode' in error:
            if error['error_subcode'] == 2207051:  # Application request limit reached
                return 900  # 15 minutos
                
        return 300  # Default: 5 minutos

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

    def create_carousel_container(self, media_urls: List[str], caption: str) -> Optional[str]:
        """Cria um contêiner de carrossel no Instagram."""
        # Validate all media first
        for media_url in media_urls:
            if not self._validate_media(media_url):
                return None
        
        # Create children containers with improved error handling
        children = []
        for media_url in media_urls:
            child_id = self._create_child_container(media_url)
            if not child_id:
                print(f"Failed to create child container for {media_url}")
                return None
            children.append(child_id)
            
            # Respect rate limits between child creation
            time.sleep(2)
        
        if not children:
            print("No child containers were created")
            return None
            
        params = {
            'media_type': 'CAROUSEL',
            'caption': caption[:2200],  # Instagram caption limit
            'children': ','.join(children),
            'access_token': self.access_token
        }
        
        try:
            data = self._make_request('POST', f'{self.base_url}/media', data=params)
            if data and 'id' in data:
                print(f"Carousel container created successfully: {data['id']}")
                return data['id']
            return None
        except Exception as e:
            print(f"Error creating carousel container: {str(e)}")
            return None

    def wait_for_container_status(self, container_id: str, max_attempts: int = 30, delay: int = 5) -> str:
        """Verifica o status do container até estar pronto ou falhar."""
        url = f'{self.base_url}/{container_id}'
        params = {
            'fields': 'status_code,status',
            'access_token': self.access_token
        }
        
        for attempt in range(max_attempts):
            try:
                data = self._make_request('GET', url, params=params)
                if not data:
                    print(f"Failed to get container status (attempt {attempt + 1}/{max_attempts})")
                    time.sleep(delay)
                    continue
                    
                status = data.get('status_code', '')
                print(f"Container status (attempt {attempt + 1}/{max_attempts}): {status}")
                
                if status == 'FINISHED':
                    return status
                elif status in ['ERROR', 'EXPIRED']:
                    print(f"Container failed with status: {status}")
                    return status
                
                time.sleep(delay)
                
            except RateLimitError as e:
                print(f"Rate limit hit while checking status. Waiting {e.retry_seconds}s...")
                time.sleep(e.retry_seconds)
            except Exception as e:
                print(f"Error checking container status: {str(e)}")
                time.sleep(delay)
        
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
            
        except RateLimitError as e:
            print(f"Rate limit excedido ao publicar carrossel: {e}")
            print(f"Recomendado aguardar {e.retry_seconds} segundos antes de tentar novamente.")
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