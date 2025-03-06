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
        self.rate_limit_multiplier = 1  # Multiplicador dinâmico
        self.app_level_backoff = 300  # Começa com 5 minutos
        self.state_file = 'api_state.json'
        self._load_api_state()
        self.endpoint_limits = {
            'media_creation': {'counter': 0, 'limit': 20},
            'media_publish': {'counter': 0, 'limit': 30}
        }
        self.media_status_cache = {}

    def _handle_error_response(self, response_data):
        """
        Handle different types of Instagram API errors
        """
        if 'error' not in response_data:
            return False, 0, "Unknown error occurred"

        error = response_data['error']
        error_code = error.get('code')
        error_subcode = error.get('error_subcode')
        error_msg = error.get('message', 'Unknown error')
        error_type = error.get('type', 'Unknown')
        fb_trace_id = error.get('fbtrace_id', 'N/A')
        
        # Log detailed error information
        print(f"API Error Details:")
        print(f"  Code: {error_code}")
        print(f"  Subcode: {error_subcode}")
        print(f"  Type: {error_type}")
        print(f"  Message: {error_msg}")
        print(f"  Trace ID: {fb_trace_id}")
        
        # Erros de autenticação (190, 104, etc)
        if error_code in [190, 104]:
            error_msg += "\n\nErro de autenticação. Ações recomendadas:"
            error_msg += "\n1. Verifique se o token não expirou"
            error_msg += "\n2. Gere um novo token de acesso"
            error_msg += "\n3. Confirme se o token tem as permissões necessárias"
            return False, 0, error_msg
        
        # Erros de permissão (200, 10, 803)
        elif error_code in [200, 10, 803]:
            error_msg += "\n\nErro de permissão. Ações recomendadas:"
            error_msg += "\n1. Verifique se a conta é Business/Creator"
            error_msg += "\n2. Confirme as permissões do app no Facebook Developer"
            return False, 0, error_msg
        
        # Erros de limite de taxa (4, 17, 32, 613)
        elif error_code in [4, 17, 32, 613]:
            wait_time = 300  # 5 minutos padrão
            if 'minutes' in error_msg.lower():
                try:
                    # Tentar extrair tempo de espera da mensagem
                    import re
                    time_match = re.search(r'(\d+)\s*minutes?', error_msg.lower())
                    if time_match:
                        wait_time = int(time_match.group(1)) * 60
                except:
                    pass
            error_msg += f"\n\nLimite de taxa atingido. Aguardando {wait_time/60:.0f} minutos."
            return True, wait_time, error_msg
        
        # Erros de formato de mídia (2207026)
        elif error_code == 2207026:
            error_msg += "\n\nErro no formato da mídia. Requisitos para Reels:"
            error_msg += "\n- Formato: MP4/MOV"
            error_msg += "\n- Codec Vídeo: H.264"
            error_msg += "\n- Codec Áudio: AAC"
            error_msg += "\n- Resolução: Mínimo 500x500, recomendado 1080x1920"
            error_msg += "\n- Duração: 3-90 segundos"
            error_msg += "\n- Tamanho: Máximo 100MB"
            return False, 0, error_msg
        
        # Erros de servidor (1, 2, 500, etc)
        elif error_code in [1, 2] or error_type == 'OAuthException':
            error_msg += "\n\nErro temporário do servidor. Tentando novamente..."
            return True, 30, error_msg
        
        # Handle specific error codes
        
        # Rate limit error (code 4, subcode 2207051)
        if error_code == 4 and error_subcode == 2207051:
            print("Limite GLOBAL do aplicativo atingido. Backoff exponencial ativado.")
            # Use app_level_backoff instead of rate_limit_multiplier
            self.app_level_backoff *= 2
            if self.app_level_backoff > 3600:  # Máximo 1 hora
                self.app_level_backoff = 3600
            
            calculated_delay = self.app_level_backoff
            self.rate_limit_delay = calculated_delay
            self.rate_limit_reset_time = time.time() + calculated_delay
            self._save_api_state()
            
            return True, calculated_delay, f"Rate limit exceeded: {error_msg}"
            
        # Fatal error (code -1, subcode 2207001)
        if error_code == -1 and error_subcode == 2207001:
            print("Erro fatal da API detectado. Pode ser necessário verificar o container de mídia.")
            # Try with a longer delay, but mark as retriable
            self.rate_limit_delay = 600  # 10 minutes
            return True, self.rate_limit_delay, f"Fatal API error: {error_msg}"
        
        # Handle specific permalink error
        if error_code == 100 and "nonexisting field (permalink)" in error_msg:
            print("Permalink ainda não está disponível (ShadowIGMediaBuilder). Isso é normal após criação recente.")
            return True, 20, "Permalink not available yet"
            
        # These error codes often occur even when the post succeeds
        temporary_error_codes = [1, 2, 4, 24, 32, 33]  # Added more error codes
        instagram_business_error = 10  # Specific error for business accounts
        
        if error_code in temporary_error_codes:  
            return True, 30, f"Temporary API error: {error_msg}"
        elif error_code == 190:  # Invalid access token
            return False, 0, "Invalid access token"
        elif error_code == instagram_business_error:
            return False, 0, "Configuração de conta business necessária"
        
        # For any other error, we'll retry but note it as potentially non-fatal
        return True, 30, f"{error_msg}"

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
        # Verifica cache primeiro
        if media_id in self.media_status_cache:
            cached = self.media_status_cache[media_id]
            if time.time() - cached['timestamp'] < 30:
                print(f"Retornando status do cache para {media_id}")
                return cached['status'], cached['permalink']

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
        success = media_status in ('FINISHED', 'PUBLISHED')
        
        # Update cache with actual values
        self.media_status_cache[media_id] = {
            'status': success,
            'permalink': permalink,
            'timestamp': time.time()
        }
        
        return success, permalink

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
                    print(f"Processando {header_name}: {usage_data}")
                    if 'estimated_time_to_regain_access' in usage_data:
                        wait_seconds = int(usage_data['estimated_time_to_regain_access'])
                        print(f"Header {header_name} indica espera de {wait_seconds}s")
                        self.rate_limit_reset_time = time.time() + wait_seconds
                        self.rate_limit_delay = wait_seconds
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
        Make API request with exponential backoff retry logic and rate limit handling
        """
        self._rate_limit_check() # Keep the basic check

        last_error = None
        response_data = None

        endpoint_type = 'media_creation' if '/media' in url else 'media_publish'
        if self.endpoint_limits[endpoint_type]['counter'] >= self.endpoint_limits[endpoint_type]['limit']:
            print(f"Limite horário atingido para {endpoint_type}. Aguardando 1 hora.")
            time.sleep(3600)
            self.endpoint_limits[endpoint_type]['counter'] = 0

        for attempt in range(self.max_retries):
            try:
                print(f"Fazendo requisição para: {url}")
                print(f"Payload: {payload}")

                response = method(url, data=payload)
                response_data = response.json()

                print(f"Resposta da API: {response_data}")  # Log detalhado

                # --- Rate Limiting Header Handling ---
                wait_time = 0
                for header_name in ['x-app-usage', 'x-business-use-case-usage']:
                    if header_name in response.headers:
                        print(f"Rate limit data from {header_name}:")
                        try:
                            usage_data = json.loads(response.headers[header_name])
                            # Process headers based on their structure
                            if header_name == 'x-app-usage':
                                # x-app-usage is a dict with estimated_time_to_regain_access
                                print(f"  App Usage: {usage_data}")
                                if 'estimated_time_to_regain_access' in usage_data:
                                    wait_seconds = int(usage_data['estimated_time_to_regain_access'])
                                    wait_time = max(wait_time, wait_seconds)
                                    print(f"  Estimated time to regain access: {wait_seconds}s")
                                
                                # Check usage percentages
                                for metric, value in usage_data.items():
                                    if isinstance(value, (int, float)) and metric not in ['estimated_time_to_regain_access']:
                                        print(f"  {metric}: {value}%")
                                        if value > self.usage_threshold:
                                            backoff_time = 60
                                            if value > 90:  # Critical level
                                                backoff_time = 900  # 15 minutes
                                            elif value > 80:  # High level
                                                backoff_time = 300  # 5 minutes
                                            
                                            wait_time = max(wait_time, backoff_time)
                                            print(f"  High usage detected ({value}%). Setting wait time to {wait_time}s.")
                            
                            elif header_name == 'x-business-use-case-usage':
                                # This is typically a dict with lists
                                print(f"  Business Usage: {usage_data}")
                                for key, usage_list in usage_data.items():
                                    if isinstance(usage_list, list):
                                        for usage in usage_list:
                                            print(f"  {key}: {usage}")
                                            if isinstance(usage, dict) and 'estimated_time_to_regain_access' in usage:
                                                wait_seconds = int(usage['estimated_time_to_regain_access'])
                                                wait_time = max(wait_time, wait_seconds)
                                                print(f"  Business estimated time to regain access: {wait_seconds}s")
                                            
                                            # Also check usage percentages in the business header
                                            for metric, value in usage.items():
                                                if isinstance(value, (int, float)) and metric not in ['estimated_time_to_regain_access']:
                                                    print(f"  {metric}: {value}%")
                                                    if value > self.usage_threshold:
                                                        backoff_time = 60
                                                        if value > 90:  # Critical level
                                                            backoff_time = 900  # 15 minutes
                                                        elif value > 80:  # High level
                                                            backoff_time = 300  # 5 minutes
                                                        
                                                        wait_time = max(wait_time, backoff_time)
                                                        print(f"  High usage detected ({value}%). Setting wait time to {wait_time}s.")

                        except json.JSONDecodeError:
                            print(f"  Erro ao decodificar JSON do header {header_name}: {response.headers[header_name]}")
                            continue

                if wait_time > 0:
                    print(f"Aguardando {wait_time} segundos devido ao rate limiting (header)")
                    self.rate_limit_reset_time = time.time() + wait_time
                    time.sleep(wait_time)
                # --- End Rate Limiting Header Handling ---

                if 'error' in response_data:
                    should_retry, retry_delay, error_msg = self._handle_error_response(response_data)
                    last_error = error_msg

                    if should_retry and attempt < self.max_retries - 1:
                        delay = self.base_delay * (2 ** attempt)
                        delay = max(delay, retry_delay)
                        print(f"Tentativa {attempt + 1} falhou. Tentando novamente em {delay} segundos...")
                        time.sleep(delay)
                        continue
                    elif not should_retry:
                        print(f"Erro não recuperável: {error_msg}")
                        return None

                # On successful response, reset multiplier to mitigate prolonged backoff on future calls.
                if response.status_code == 200:
                    self.rate_limit_multiplier = 1  # Reset multiplier after success
                    endpoint_type = 'media_creation' if '/media' in url else 'media_publish'
                    self.endpoint_limits[endpoint_type]['counter'] += 1

                self._save_api_state()
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

    def _load_api_state(self):
        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)
                self.rate_limit_reset_time = state.get('rate_limit_reset_time', 0)
                self.rate_limit_multiplier = state.get('rate_limit_multiplier', 1)
                self.app_level_backoff = state.get('app_level_backoff', 300)
                last_error_time = state.get('last_error_time', 0)
                if time.time() - last_error_time > 3600:
                    self.app_level_backoff = 300  # Reset se o último erro foi há mais de 1 hora
        except:
            pass

    def _save_api_state(self):
        state = {
            'rate_limit_reset_time': self.rate_limit_reset_time,
            'rate_limit_multiplier': self.rate_limit_multiplier,
            'app_level_backoff': self.app_level_backoff,
            'last_error_time': time.time()
        }
        with open(self.state_file, 'w') as f:
            json.dump(state, f)

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
        # Pre-check for rate limits before attempting publish
        if self.app_level_backoff > 300:
            print(f"Nível de backoff alto detectado ({self.app_level_backoff}s). Pulando chamada API e verificando direto.")
            # Skip API call, go straight to verification
            success, permalink = self._verify_media_status(
                media_container_id, 
                max_attempts=10,  # Increased attempts
                delay=30,         # Longer delay between attempts
                check_permalink=True
            )
            if success:
                print("Publicação confirmada através de verificação direta!")
                return media_container_id
        
        # Continue with normal flow if pre-check doesn't verify
        endpoint = f'{self.base_url}/media_publish'
        params = {
            'creation_id': media_container_id,
            'access_token': self.access_token
        }
        
        max_retries = 3
        retry_delay = 10
        
        for attempt in range(max_retries):
            try:
                print(f"Media Container ID: {media_container_id}")  # Log crítico
                print("Enviando requisição de publicação...")
                response_data = self._make_request_with_retry(requests.post, endpoint, params)
                
                # Se a resposta for None (por exemplo, devido a erro de rate limit), tenta verificação final
                if response_data is None or ('error' in response_data and 
                   response_data['error'].get('code') == 4 and 
                   response_data['error'].get('error_subcode') == 2207051):
                    print("Falha na publicação devido a rate limit; tentando verificação estendida...")
                    
                    # Try multiple verification attempts with increasing delays
                    for verify_attempt in range(5):
                        wait_time = 30 * (verify_attempt + 1)
                        print(f"Aguardando {wait_time}s antes da verificação {verify_attempt + 1}/5...")
                        time.sleep(wait_time)
                        
                        success, _ = self._verify_media_status(
                            media_container_id, 
                            max_attempts=3,
                            delay=15,
                            check_permalink=False
                        )
                        
                        if success:
                            print(f"Publicação confirmada na tentativa {verify_attempt + 1}!")
                            return media_container_id
                    
                    print("Todas as verificações estendidas falharam.")
                    return None
                
                # Se temos uma resposta positiva com ID
                post_id = response_data.get('id', media_container_id)
                print(f"Publicação iniciada com ID: {post_id}")
                
                # Aguardar processamento e verificar status
                print("Aguardando processamento inicial (40 segundos)...")
                time.sleep(40)
                print("Verificando status básico da publicação...")
                success, _ = self._verify_media_status(post_id, max_attempts=8, delay=15, check_permalink=False)
                if not success and post_id != media_container_id:
                    print("Tentando verificar com o container ID original...")
                    success, _ = self._verify_media_status(media_container_id, max_attempts=5, delay=15, check_permalink=False)
                    if not success:
                        print("Não foi possível confirmar publicação após verificação do status.")
                        return None

                print("Publicação confirmada! Tentando obter permalink...")
                success, permalink = self._verify_media_status(post_id, max_attempts=2, delay=20, check_permalink=True)
                if permalink:
                    print(f"Link da publicação: {permalink}")
                else:
                    print("Publicação bem-sucedida, mas permalink não disponível.")
                
                return post_id
            
            except Exception as e:
                print(f"Erro na publicação (tentativa {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (2 ** attempt))
        
        print("Todas as tentativas de publicação falharam")
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
