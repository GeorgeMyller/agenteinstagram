import os
import time
import requests
from dotenv import load_dotenv

class InstagramPostService:
    load_dotenv()

    def __init__(self):
        self.instagram_account_id = os.getenv("INSTAGRAM_ACCOUNT_ID")
        if not self.instagram_account_id:
            raise ValueError("INSTAGRAM_ACCOUNT_ID não configurado")
            
        self.access_token = os.getenv('INSTAGRAM_API_KEY')
        if not self.access_token:
            raise ValueError("INSTAGRAM_API_KEY não configurado")
            
        self.base_url = f'https://graph.facebook.com/v22.0/{self.instagram_account_id}'
        self.max_retries = 3
        self.base_delay = 5  # Base delay in seconds
        self.status_check_attempts = 5  # Number of status check attempts
        self.status_check_delay = 10  # Delay between status checks in seconds
        self.request_counter = 0
        self.rate_limit_threshold = 5
        self.rate_limit_delay = 60  # Wait 60 seconds after hitting threshold

    def _handle_error_response(self, response_data):
        """
        Handle different types of Instagram API errors
        """
        if 'error' not in response_data:
            return False, "Unknown error occurred"

        error = response_data['error']
        error_code = error.get('code')
        
        # These error codes often occur even when the post succeeds
        temporary_error_codes = [1, 2, 4, 24, 32, 33]  # Added more error codes
        instagram_business_error = 10  # Specific error for business accounts
        
        if error_code in temporary_error_codes:  
            return True, f"Temporary API error: {error.get('message')}"
        elif error_code == 190:  # Invalid access token
            return False, "Invalid access token"
        elif error_code == instagram_business_error:
            return False, "Configuração de conta business necessária"
        
        # For any other error, we'll retry but note it as potentially non-fatal
        return True, error.get('message', 'Unknown error occurred')

    def _verify_media_status(self, media_id, max_attempts=None, delay=None):
        """
        Verify if a media post exists and is published with multiple attempts
        """
        max_attempts = max_attempts or self.status_check_attempts
        delay = delay or self.status_check_delay

        for attempt in range(max_attempts):
            if attempt > 0:
                print(f"Verificando status (tentativa {attempt + 1}/{max_attempts})...")
                time.sleep(delay)
            
            # Endpoint correto para verificar o contêiner específico
            url = f'{self.base_url}/media/{media_id}'
            params = {
                'access_token': self.access_token,
                'fields': 'status_code,status,permalink'
            }
            
            try:
                response = requests.get(url, params=params)
                data = response.json()
                
                print(f"Resposta da API: {data}")  # Log detalhado
                
                if data.get('status_code') == 'FINISHED':
                    print(f"Post publicado! Status: {data.get('status', 'PUBLISHED')}")
                    return True, data.get('permalink')
                elif data.get('status_code') in ('IN_PROGRESS', 'PENDING'):
                    print(f"Processamento em andamento... (Status: {data.get('status')})")
                elif 'id' in data:
                    print(f"Post encontrado mas status não disponível.")
                    status = data.get('status', 'UNKNOWN')
                    print(f"Status atual: {status}")
                    if status == 'PUBLISHED':
                        return True, data.get('permalink')
                    
                if 'error' in data:
                    error_msg = data['error'].get('message', 'Erro desconhecido')
                    print(f"Erro ao verificar status: {error_msg}")
                    
                if attempt == max_attempts - 1:
                    print("Post não encontrado após todas as tentativas de verificação.")
                    
            except Exception as e:
                print(f"Erro ao verificar status: {str(e)}")
        
        return False, None

    def _rate_limit_check(self):
        """
        Check if we're approaching rate limits and pause if needed
        """
        self.request_counter += 1
        if self.request_counter >= self.rate_limit_threshold:
            print(f"Atingido limite de {self.rate_limit_threshold} requisições. Pausando por {self.rate_limit_delay} segundos.")
            time.sleep(self.rate_limit_delay)
            self.request_counter = 0

    def _make_request_with_retry(self, method, url, payload):
        """
        Make API request with exponential backoff retry logic
        """
        self._rate_limit_check()
        
        last_error = None
        response_data = None
        
        for attempt in range(self.max_retries):
            try:
                print(f"Fazendo requisição para: {url}")
                print(f"Payload: {payload}")
                
                response = method(url, data=payload)
                response_data = response.json()
                
                print(f"Resposta da API: {response_data}")  # Log detalhado

                if 'error' in response_data:
                    should_retry, error_msg = self._handle_error_response(response_data)
                    last_error = error_msg
                    
                    if should_retry and attempt < self.max_retries - 1:
                        delay = self.base_delay * (2 ** attempt)
                        print(f"Tentativa {attempt + 1} falhou. Tentando novamente em {delay} segundos...")
                        time.sleep(delay)
                        continue
                    elif not should_retry:
                        print(f"Erro não recuperável: {error_msg}")
                        return None
                
                return response_data
                
            except requests.exceptions.RequestException as e:
                last_error = str(e)
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2 ** attempt)
                    print(f"Falha na requisição: {str(e)}. Tentando novamente em {delay} segundos...")
                    time.sleep(delay)
                else:
                    print(f"Todas as tentativas falharam: {str(e)}")
        
        if last_error:
            print(f"Erro: {last_error}")
        return response_data

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
            container_id = response_data['id']
            print(f"Container de mídia criado com ID: {container_id}")
            return container_id
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

        print(f"Media Container ID: {media_container_id}")  # Log crítico
        print("Enviando requisição de publicação...")
        response_data = self._make_request_with_retry(requests.post, url, payload)
        
        # Aumentar tempo de espera inicial para 30 segundos
        print("Aguardando processamento inicial (30 segundos)...")
        time.sleep(30)  
        
        # Even if we get an error, check if the post actually went through
        if response_data and 'id' in response_data:
            success, permalink = self._verify_media_status(response_data['id'])
            if success:
                print(f"Post publicado com sucesso! ID do Post: {response_data['id']}")
                if permalink:
                    print(f"Link do post: {permalink}")
                return response_data['id']
        
        # If we didn't get a success response, do an extended verification
        print("Realizando verificação estendida do status da publicação...")
        success, permalink = self._verify_media_status(
            media_container_id,
            max_attempts=8,  # Aumentado para 8 tentativas
            delay=20  # Intervalo maior entre verificações
        )
        
        if success:
            print("Post publicado com sucesso apesar dos erros iniciais!")
            if permalink:
                print(f"Link do post: {permalink}")
            return media_container_id
            
        return None

    def post_image(self, image_url, caption):
        """
        Faz todo o fluxo de criação e publicação de um post no Instagram.
        """
        print("Iniciando publicação de imagem no Instagram...")

        media_container_id = self.create_media_container(image_url, caption)
        if not media_container_id:
            print("Falha na criação do contêiner de mídia.")
            return None

        # Increased delay between creation and publishing to avoid rate limits
        print("Aguardando estabilização do container (10 segundos)...")
        time.sleep(10)  # Increased from 5 to 10 seconds

        post_id = self.publish_media(media_container_id)
        if not post_id:
            # Final verification with even longer delays
            print("Realizando verificação final do status da publicação...")
            time.sleep(20)  # Extended delay before final check
            success, permalink = self._verify_media_status(
                media_container_id,
                max_attempts=5,
                delay=20
            )
            
            if success:
                print("Post verificado e confirmado no Instagram!")
                if permalink:
                    print(f"Link do post: {permalink}")
                return media_container_id
            print("Não foi possível confirmar a publicação do post após múltiplas tentativas.")
            return None

        print(f"Processo concluído com sucesso! ID do Post: {post_id}")
        return post_id
        
    def test_post(self, test_image_url="https://i.imgur.com/exampleimage.jpg", test_caption="Teste de publicação 🚀"):
        """
        Método de teste para verificar a funcionalidade de postagem.
        Use apenas para testes e diagnósticos.
        """
        print("Executando teste de publicação...")
        result = self.post_image(test_image_url, test_caption)
        print(f"Resultado do teste: {result}")
        return result
