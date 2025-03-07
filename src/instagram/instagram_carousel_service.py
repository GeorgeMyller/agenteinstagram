import os
import requests
import time
import json
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
            # Logging para debug
            if method == 'POST' and 'data' in kwargs:
                print(f"Fazendo requisição para: {url}")
                # Cria uma cópia do payload para não mostrar tokens de acesso
                safe_payload = kwargs['data'].copy() if isinstance(kwargs['data'], dict) else {}
                if 'access_token' in safe_payload:
                    safe_payload['access_token'] = safe_payload['access_token'][:10] + '...'
                print(f"Payload: {safe_payload}")
                
            response = self.session.request(method, url, **kwargs)
            
            # Obter informações de rate limit dos cabeçalhos
            self._log_rate_limit_info(response)
            
            # Verificar se tem conteúdo JSON na resposta
            if response.content:
                json_response = response.json()
                print(f"Resposta da API: {json_response}")
                
                # Verificar se há erro na resposta
                if 'error' in json_response:
                    error = json_response['error']
                    print("API Error Details:")
                    print(f"  Code: {error.get('code')}")
                    print(f"  Subcode: {error.get('error_subcode', 'N/A')}")
                    print(f"  Type: {error.get('type', 'N/A')}")
                    print(f"  Message: {error.get('message', 'N/A')}")
                    print(f"  Trace ID: {error.get('fbtrace_id', 'N/A')}")
                    
                    # Verificar se é rate limit
                    if error.get('code') == 4 or error.get('message', '').lower().find('rate') >= 0:
                        retry_seconds = self._get_retry_time_from_error(error)
                        print(f"Rate limit detectado. Recomendado aguardar {retry_seconds} segundos.")
                        raise RateLimitError(f"Rate limit excedido", retry_seconds=retry_seconds)
                    
                    return None
                
                return json_response
            return {}
            
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
            
            # Verificar se é rate limit
            if response and response.status_code == 429:
                retry_seconds = 300  # Default: 5 minutos
                if 'error' in error_data and 'message' in error_data['error']:
                    if 'rate' in error_data['error']['message'].lower():
                        retry_seconds = self._get_retry_time_from_error(error_data['error'])
                raise RateLimitError(f"Rate limit excedido", retry_seconds=retry_seconds)
                
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

class RateLimitError(Exception):
    """Exceção lançada quando um rate limit é atingido."""
    def __init__(self, message, retry_seconds=300):
        super().__init__(message)
        self.retry_seconds = retry_seconds