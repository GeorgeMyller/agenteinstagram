import os
import time
import json
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
        self.permalink_check_attempts = 3  # Specific attempts for permalink
        self.permalink_check_delay = 20  # Longer delay for permalink checks
        self.request_counter = 0
        self.rate_limit_threshold = 5
        self.rate_limit_delay = 60  # Default delay when hitting threshold
        self.rate_limit_reset_time = 0  # Time when rate limit resets
        self.usage_threshold = 80  # Percentage of quota at which to start backing off
        
        # Rate limit header tracking
        self.rate_limit_headers = {
            'call_count': 0,
            'total_time': 0,
            'total_cputime': 0,
            'app_usage': {},
            'business_usage': {}
        }

    def _handle_error_response(self, response_data):
        """
        Handle different types of Instagram API errors
        """
        if 'error' not in response_data:
            return False, "Unknown error occurred"

        error = response_data['error']
        error_code = error.get('code')
        error_subcode = error.get('error_subcode')
        error_msg = error.get('message', 'Unknown error')
        error_type = error.get('type', 'Unknown')
        
        # Log detailed error information
        print(f"API Error Details:")
        print(f"  Code: {error_code}")
        print(f"  Subcode: {error_subcode}")
        print(f"  Type: {error_type}")
        print(f"  Message: {error_msg}")
        
        # Handle specific error codes
        
        # Rate limit error (code 4, subcode 2207051)
        if error_code == 4 and error_subcode == 2207051:
            print("Taxa de requisições da aplicação atingida. Implementando backoff prolongado.")
            # Increase rate limit delay for more severe backoff
            self.rate_limit_delay = 300  # 5 minutes
            self.rate_limit_reset_time = time.time() + self.rate_limit_delay
            return True, f"Rate limit exceeded: {error_msg}"
            
        # Fatal error (code -1, subcode 2207001)
        if error_code == -1 and error_subcode == 2207001:
            print("Erro fatal da API detectado. Pode ser necessário verificar o container de mídia.")
            # Try with a longer delay, but mark as retriable
            self.rate_limit_delay = 600  # 10 minutes
            return True, f"Fatal API error: {error_msg}"
        
        # Handle specific permalink error
        if error_code == 100 and "nonexisting field (permalink)" in error_msg:
            print("Permalink ainda não está disponível (ShadowIGMediaBuilder). Isso é normal após criação recente.")
            return True, "Permalink not available yet"
            
        # These error codes often occur even when the post succeeds
        temporary_error_codes = [1, 2, 4, 24, 32, 33]  # Added more error codes
        instagram_business_error = 10  # Specific error for business accounts
        
        if error_code in temporary_error_codes:  
            return True, f"Temporary API error: {error_msg}"
        elif error_code == 190:  # Invalid access token
            return False, "Invalid access token"
        elif error_code == instagram_business_error:
            return False, "Configuração de conta business necessária"
        
        # For any other error, we'll retry but note it as potentially non-fatal
        return True, f"{error_msg}"

    def _verify_media_status(self, media_id, max_attempts=None, delay=None, check_permalink=True):
        """
        Verify if a media post exists and is published. Can separate status check from permalink check.
        
        Args:
            media_id: ID of the media to check
            max_attempts: Maximum number of check attempts
            delay: Delay between attempts in seconds
            check_permalink: Whether to include permalink in the checks
        
        Returns:
            tuple: (success_boolean, permalink_or_None)
        """
        max_attempts = max_attempts or self.status_check_attempts
        delay = delay or self.status_check_delay

        # Phase 1: Verify basic status without permalink
        print("Fase 1: Verificando status básico da publicação...")
        media_status = None
        
        for attempt in range(max_attempts):
            if attempt > 0:
                print(f"Verificando status (tentativa {attempt + 1}/{max_attempts})...")
                time.sleep(delay)
            
            # Endpoint para verificar o contêiner específico
            url = f'https://graph.facebook.com/v22.0/{media_id}'
            
            # Na fase inicial, não solicitar o permalink para evitar erro #100
            fields = 'id,status_code,status'
            
            params = {
                'access_token': self.access_token,
                'fields': fields
            }
            
            try:
                response = requests.get(url, params=params)
                data = response.json()
                
                print(f"Resposta da API (status check): {data}")
                
                # Verificar se há erros
                if 'error' in data:
                    error_msg = data['error'].get('message', 'Erro desconhecido')
                    print(f"Erro ao verificar status: {error_msg}")
                    continue
                    
                # Verificação de ID bem-sucedida
                if 'id' in data and data.get('id') == media_id:
                    # Verificar status
                    media_status = data.get('status_code') or data.get('status')
                    if media_status in ('FINISHED', 'PUBLISHED'):
                        print(f"Post encontrado com status: {media_status}")
                        break  # Status verificado com sucesso
                    elif media_status in ('IN_PROGRESS', 'PENDING'):
                        print(f"Processamento em andamento... (Status: {media_status})")
                    else:
                        print(f"Status inesperado: {media_status}")
                        
            except Exception as e:
                print(f"Erro ao verificar status: {str(e)}")
                
        # Se não conseguimos confirmar o status após todas as tentativas
        if media_status not in ('FINISHED', 'PUBLISHED'):
            print("Não foi possível confirmar status de publicação após múltiplas tentativas.")
            return False, None
            
        # Phase 2: Get permalink (only if requested and phase 1 was successful)
        permalink = None
        if check_permalink:
            print("Fase 2: Obtendo permalink da publicação...")
            for attempt in range(self.permalink_check_attempts):
                # Aguardar mais tempo para permalink
                time.sleep(self.permalink_check_delay)
                print(f"Verificando permalink (tentativa {attempt + 1}/{self.permalink_check_attempts})...")
                
                url = f'https://graph.facebook.com/v22.0/{media_id}'
                params = {
                    'access_token': self.access_token,
                    'fields': 'permalink'
                }
                
                try:
                    response = requests.get(url, params=params)
                    data = response.json()
                    
                    print(f"Resposta da API (permalink check): {data}")
                    
                    # Verificar se há erros específicos do permalink
                    if 'error' in data:
                        error_code = data['error'].get('code')
                        error_msg = data['error'].get('message', '')
                        
                        # Erro #100 sobre permalink pode ser normal nas primeiras tentativas
                        if error_code == 100 and "nonexisting field (permalink)" in error_msg:
                            print("Permalink ainda não disponível. Tentando novamente...")
                            continue
                            
                        print(f"Erro ao obter permalink: {error_msg}")
                        continue
                        
                    # Se temos permalink, sucesso!
                    if 'permalink' in data and data['permalink']:
                        permalink = data['permalink']
                        print(f"Permalink obtido com sucesso: {permalink}")
                        break
                        
                except Exception as e:
                    print(f"Erro ao obter permalink: {str(e)}")
            
            if not permalink:
                print("Aviso: Post publicado com sucesso, mas não foi possível obter o permalink.")
        
        # Retorna sucesso mesmo se permalink não foi obtido
        return True, permalink

    def _analyze_rate_limit_headers(self, response):
        """
        Analyze rate limit headers from the Instagram API response and 
        adjust rate limiting strategy accordingly
        """
        headers = response.headers
        rate_limited = False
        
        # Log all headers for debugging
        print("Response Headers:")
        for header_name, header_value in headers.items():
            if header_name.lower().startswith('x-'):
                print(f"  {header_name}: {header_value}")

        # Process Instagram/Facebook specific rate limit headers
        for header_name in ['x-app-usage', 'x-business-use-case-usage']:
            if header_name in headers:
                try:
                    usage_data = json.loads(headers[header_name])
                    print(f"Rate limit data from {header_name}:")
                    
                    if header_name == 'x-app-usage':
                        self.rate_limit_headers['app_usage'] = usage_data
                    else:
                        self.rate_limit_headers['business_usage'] = usage_data
                    
                    # Check usage percentages
                    for metric, value in usage_data.items():
                        print(f"  {metric}: {value}")
                        if isinstance(value, (int, float)) and value > self.usage_threshold:
                            print(f"⚠️ Rate limit approaching critical level for {metric}: {value}%")
                            
                            # Dynamic delay calculation based on usage percentage
                            if value > 90:  # Critical level
                                wait_seconds = 900  # 15 minutes
                            elif value > 80:  # High level
                                wait_seconds = 300  # 5 minutes
                            else:  # Moderate level
                                wait_seconds = 60  # 1 minute
                                
                            print(f"Implementing rate limit backoff: {wait_seconds} seconds")
                            self.rate_limit_delay = wait_seconds
                            self.rate_limit_reset_time = time.time() + wait_seconds
                            rate_limited = True
                except json.JSONDecodeError:
                    print(f"Could not parse {header_name} header: {headers[header_name]}")
                except Exception as e:
                    print(f"Error processing {header_name} header: {str(e)}")
        
        return rate_limited

    def _rate_limit_check(self):
        """
        Enhanced rate limit check with dynamic delays based on header data
        """
        current_time = time.time()
        
        # If we have a reset time and haven't reached it yet
        if self.rate_limit_reset_time > current_time:
            wait_time = self.rate_limit_reset_time - current_time
            print(f"Aguardando {int(wait_time)} segundos para reset de rate limit...")
            time.sleep(wait_time)
            self.rate_limit_reset_time = 0
            self.request_counter = 0
            return
        
        # Standard counter-based rate limiting (fallback if headers are not available)
        self.request_counter += 1
        if self.request_counter >= self.rate_limit_threshold:
            print(f"Limite de requisições atingido. Pausando por {self.rate_limit_delay} segundos...")
            time.sleep(self.rate_limit_delay)
            self.request_counter = 0

    def _make_request_with_retry(self, method, url, payload):
        """
        Make API request with exponential backoff retry logic and header analysis
        """
        self._rate_limit_check()
        
        last_error = None
        response_data = None
        
        for attempt in range(self.max_retries):
            try:
                print(f"Fazendo requisição para: {url}")
                print(f"Payload: {payload}")
                
                response = method(url, data=payload)
                
                # First analyze headers before processing response body
                rate_limited = self._analyze_rate_limit_headers(response)
                
                # Now process the response body
                response_data = response.json()
                print(f"Resposta da API: {response_data}")
                
                if rate_limited:
                    print("Rate limiting detectado nos headers. Aplicando backoff.")
                    if attempt < self.max_retries - 1:
                        delay = self.rate_limit_delay
                        print(f"Tentativa {attempt + 1} pausada devido a rate limits. Aguardando {delay} segundos...")
                        time.sleep(delay)
                        continue

                if 'error' in response_data:
                    should_retry, error_msg = self._handle_error_response(response_data)
                    last_error = error_msg
                    
                    if should_retry and attempt < self.max_retries - 1:
                        # Use exponential backoff for retries
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
        
        # Verificar se temos uma resposta positiva com ID
        post_id = None
        if response_data and 'id' in response_data:
            post_id = response_data['id']
            print(f"Publicação iniciada com ID: {post_id}")
        else:
            print("Não recebemos ID na resposta da publicação. Usando container ID para verificação.")
            post_id = media_container_id
            
        # Aumentar tempo de espera inicial para 40 segundos
        print("Aguardando processamento inicial (40 segundos)...")
        time.sleep(40)
        
        # Fase 1: Verificar apenas status básico (sem permalink)
        print("Verificando status básico da publicação...")
        success, _ = self._verify_media_status(
            post_id,
            max_attempts=8,
            delay=15,
            check_permalink=False  # Não verificar permalink ainda
        )
        
        if not success:
            # Tente com o container ID se o post_id falhar
            if post_id != media_container_id:
                print("Tentando verificar com o container ID original...")
                success, _ = self._verify_media_status(
                    media_container_id,
                    max_attempts=5,
                    delay=15,
                    check_permalink=False
                )
            
            if not success:
                print("Não foi possível confirmar publicação após verificação do status.")
                return None
        
        # Fase 2: Apenas se o status for bem-sucedido, tente obter permalink
        print("Publicação confirmada! Tentando obter permalink...")
        success, permalink = self._verify_media_status(
            post_id,
            max_attempts=2,  # Menos tentativas para verificação básica
            delay=20,
            check_permalink=True  # Agora sim, verificar permalink
        )
        
        if permalink:
            print(f"Link da publicação: {permalink}")
        else:
            print("Publicação bem-sucedida, mas permalink não disponível.")
        
        return post_id

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
        print("Aguardando estabilização do container (15 segundos)...")
        time.sleep(15)  # Increased from 10 to 15 seconds

        post_id = self.publish_media(media_container_id)
        if post_id:
            print(f"Processo concluído com sucesso! ID do Post: {post_id}")
            return post_id
        
        # Final verification with even longer delays
        print("Realizando verificação final do status da publicação...")
        time.sleep(30)  # Extended delay before final check
        
        # Uma última tentativa com o container ID
        success, _ = self._verify_media_status(
            media_container_id,
            max_attempts=3,
            delay=25,
            check_permalink=False  # Não precisamos do permalink na verificação final
        )
        
        if success:
            print("Post verificado e confirmado no Instagram!")
            return media_container_id
            
        print("Não foi possível confirmar a publicação do post após múltiplas tentativas.")
        return None
        
    def test_post(self, test_image_url="https://i.imgur.com/exampleimage.jpg", test_caption="Teste de publicação 🚀"):
        """
        Método de teste para verificar a funcionalidade de postagem.
        Use apenas para testes e diagnósticos.
        """
        print("Executando teste de publicação...")
        result = self.post_image(test_image_url, test_caption)
        print(f"Resultado do teste: {result}")
        return result
