import os
import time
import json
import random  # Added the missing import for jitter functionality
import re  # Added the missing import for regex functionality
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
        self.status_check_delay = 20  # Increased from 10 to 20 seconds
        self.permalink_check_attempts = 3  # Specific attempts for permalink
        self.permalink_check_delay = 30  # Increased from 20 to 30 seconds
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
        self.last_successful_request_time = 0
        self.min_request_interval = 30  # Minimum 30 seconds between critical requests
        self.known_rate_limits = {
            'app': {'window_size': 3600, 'max_calls': 100},  # Example values
            'account': {'window_size': 3600, 'max_calls': 60}
        }
        # Store limits for both app ID and account ID
        self.id_rate_limits = {}  # Will store rate limit info for each ID found in headers
        
        # Container cache to avoid recreating containers
        self.container_cache = {}
        # Minimum wait time between ANY API calls to the same endpoint
        self.min_api_call_spacing = {
            'media': 120,      # 2 minutes between container creations (more conservative)
            'media_publish': 300,  # 5 minutes between publish attempts (much more conservative)
            'status_check': 30     # 30 seconds between status checks (less frequent polling)
        }
        self.last_api_call_time = {
            'media': 0,
            'media_publish': 0,
            'status_check': 0
        }
        
        self.retry_delay = 5
        self.error_log = []
        self._save_api_state()


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
                # Use progressive backoff - wait longer for later attempts
                adjusted_delay = delay * (1 + (attempt * 0.5))
                print(f"Aguardando {adjusted_delay:.1f}s antes da próxima verificação")
                time.sleep(adjusted_delay)
            
            # Respect minimum API spacing for status checks
            self._respect_api_spacing('status_check')
            
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
                    
                    # Process specific rate limit data
                    if header_name == 'x-app-usage':
                        # Track overall app usage
                        self._process_app_usage(usage_data)
                    
                    elif header_name == 'x-business-use-case-usage':
                        # Track per-ID usage
                        self._process_business_usage(usage_data)
                    
                    # Common processing for any wait times in headers
                    if 'estimated_time_to_regain_access' in usage_data:
                        wait_seconds = int(usage_data['estimated_time_to_regain_access'])
                        print(f"Header {header_name} indica espera de {wait_seconds}s")
                        
                        # If headers say wait=0 but we have rate limit error, use backoff
                        if wait_seconds == 0 and self.app_level_backoff > 300:
                            wait_seconds = self.app_level_backoff
                            print(f"⚠️ Header mostra 0s mas temos erros de rate limit. Usando backoff: {wait_seconds}s")
                        
                        if wait_seconds > 0:
                            self.rate_limit_reset_time = time.time() + wait_seconds
                            self.rate_limit_delay = wait_seconds
                            rate_limited = True
                    
                except Exception as e:
                    print(f"Error processing {header_name} header: {str(e)}")
        
        # After processing all headers, save state to persist rate limits
        self._save_api_state()
        
        return rate_limited

    def _process_app_usage(self, usage_data):
        """Process app-level usage data from x-app-usage header"""
        # Store app usage metrics
        self.rate_limit_headers['app_usage'] = usage_data
        
        # Calculate if we're approaching limits
        approaching_limit = False
        
        for metric, value in usage_data.items():
            if isinstance(value, (int, float)) and metric != 'estimated_time_to_regain_access':
                print(f"  {metric}: {value}%")
                # Store the percentage for this metric
                if value > self.usage_threshold:
                    approaching_limit = True
                    print(f"⚠️ App usage approaching limit for {metric}: {value}%")
        
        # If we're approaching limits, adjust our backoff strategy
        if approaching_limit:
            new_backoff = max(self.app_level_backoff, 300)  # At least 5 minutes
            highest_value = max([v for k, v in usage_data.items() 
                               if isinstance(v, (int, float)) and k != 'estimated_time_to_regain_access'], 
                              default=0)
            
            # Scale backoff based on highest usage percentage
            if highest_value > 90:
                new_backoff = 900  # 15 minutes
            elif highest_value > 80:
                new_backoff = 600  # 10 minutes
            elif highest_value > 70:
                new_backoff = 300  # 5 minutes
            
            self.app_level_backoff = new_backoff
            print(f"Ajustando backoff global para {new_backoff}s devido ao uso elevado")

    def _process_business_usage(self, usage_data):
        """Process account-level usage data from x-business-use-case-usage header"""
        self.rate_limit_headers['business_usage'] = usage_data
        
        # Process each ID separately (Facebook app ID and Instagram account ID)
        for id_key, usage_list in usage_data.items():
            print(f"  Processing usage for ID: {id_key}")
            
            # Initialize rate limit tracking for this ID if not exists
            if id_key not in self.id_rate_limits:
                self.id_rate_limits[id_key] = {
                    'last_call_time': 0,
                    'call_count': 0,
                    'window_start': time.time(),
                    'backoff_until': 0
                }
            
            # Process all usages for this ID
            if isinstance(usage_list, list):
                for usage in usage_list:
                    # Check if this usage contains estimated time
                    if isinstance(usage, dict):
                        if 'estimated_time_to_regain_access' in usage and usage['estimated_time_to_regain_access'] > 0:
                            wait_time = int(usage['estimated_time_to_regain_access'])
                            print(f"  ID {id_key} needs to wait {wait_time}s")
                            self.id_rate_limits[id_key]['backoff_until'] = time.time() + wait_time
                        
                        # Check other metrics for this ID
                        highest_metric = 0
                        for metric, value in usage.items():
                            if isinstance(value, (int, float)) and metric != 'estimated_time_to_regain_access':
                                print(f"  {id_key} - {metric}: {value}%")
                                highest_metric = max(highest_metric, value)
                        
                        # If any metric is high, set backoff for this specific ID
                        if highest_metric > self.usage_threshold:
                            backoff_time = 0
                            if highest_metric > 90:
                                backoff_time = 900  # 15 minutes
                            elif highest_metric > 80:
                                backoff_time = 300  # 5 minutes
                            else:
                                backoff_time = 60  # 1 minute
                            
                            current_backoff = self.id_rate_limits[id_key].get('backoff_until', 0) - time.time()
                            if current_backoff < backoff_time:
                                print(f"  Setting backoff for ID {id_key}: {backoff_time}s due to high usage")
                                self.id_rate_limits[id_key]['backoff_until'] = time.time() + backoff_time
                    
                    # Increment call count for rate limiting purposes
                    self.id_rate_limits[id_key]['call_count'] += 1
                    self.id_rate_limits[id_key]['last_call_time'] = time.time()

    def _check_id_rate_limits(self):
        """Check if any ID has reached its rate limit"""
        current_time = time.time()
        wait_time = 0
        
        for id_key, limits in self.id_rate_limits.items():
            # Check if we need to wait due to backoff
            if limits.get('backoff_until', 0) > current_time:
                id_wait = limits['backoff_until'] - current_time
                print(f"ID {id_key} em backoff por mais {int(id_wait)}s")
                wait_time = max(wait_time, id_wait)
            
            # Check window-based rate limits
            window_size = self.known_rate_limits.get('account' if id_key == self.instagram_account_id else 'app', {}).get('window_size', 3600)
            window_start = limits.get('window_start', 0)
            
            # Reset window if needed
            if current_time - window_start > window_size:
                limits['window_start'] = current_time
                limits['call_count'] = 0
            
            # Check call count against max allowed
            max_calls = self.known_rate_limits.get('account' if id_key == self.instagram_account_id else 'app', {}).get('max_calls', 60)
            if limits.get('call_count', 0) >= max_calls:
                window_wait = window_size - (current_time - window_start)
                if window_wait > 0:
                    print(f"ID {id_key} atingiu o limite de chamadas ({max_calls}). Aguardando {int(window_wait)}s")
                    wait_time = max(wait_time, window_wait)
        
        return wait_time

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

    def _forced_rate_limit_backoff(self):
        """
        Force backoff between critical API calls regardless of headers
        """
        current_time = time.time()
        time_since_last_request = current_time - self.last_successful_request_time
        
        if time_since_last_request < self.min_request_interval:
            wait_time = self.min_request_interval - time_since_last_request
            print(f"Aplicando backoff forçado de {wait_time:.1f}s entre requisições críticas")
            time.sleep(wait_time)
        
        self.last_successful_request_time = current_time

    def _make_request_with_retry(self, method, url, payload):
        """
        Make API request with exponential backoff retry logic and rate limit handling
        """
        # First check basic rate limit (old implementation)
        self._rate_limit_check()
        
        # Then check ID-specific rate limits (new implementation)
        id_wait_time = self._check_id_rate_limits()
        if id_wait_time > 0:
            print(f"Aguardando {int(id_wait_time)}s devido a limites de ID específicos")
            time.sleep(id_wait_time)

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
        """Load extended rate limit state"""
        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)
                self.rate_limit_reset_time = state.get('rate_limit_reset_time', 0)
                self.rate_limit_multiplier = state.get('rate_limit_multiplier', 1)
                self.app_level_backoff = state.get('app_level_backoff', 300)
                
                # Load ID-specific rate limits
                self.id_rate_limits = state.get('id_rate_limits', {})
                
                # Reset if last error was too long ago
                last_error_time = state.get('last_error_time', 0)
                if time.time() - last_error_time > 3600:
                    print("Resetando limites de taxa pois o último erro foi há mais de 1 hora")
                    self.app_level_backoff = 300
                    self.id_rate_limits = {}
        except:
            pass

    def _save_api_state(self):
        """Save extended rate limit state"""
        state = {
            'rate_limit_reset_time': self.rate_limit_reset_time,
            'rate_limit_multiplier': self.rate_limit_multiplier,
            'app_level_backoff': self.app_level_backoff,
            'last_error_time': time.time(),
            'id_rate_limits': self.id_rate_limits  # Save ID-specific limits
        }
        with open(self.state_file, 'w') as f:
            json.dump(state, f)

    def _respect_api_spacing(self, endpoint_type):
        """Ensure minimum spacing between API calls to the same endpoint"""
        current_time = time.time()
        last_call = self.last_api_call_time.get(endpoint_type, 0)
        min_spacing = self.min_api_call_spacing.get(endpoint_type, 10)
        
        if last_call > 0:
            elapsed = current_time - last_call
            if elapsed < min_spacing:
                wait_time = min_spacing - elapsed
                print(f"Respeitando intervalo mínimo para {endpoint_type}. Aguardando {wait_time:.1f}s...")
                time.sleep(wait_time)
        
        # Update last call time
        self.last_api_call_time[endpoint_type] = time.time()

    def create_media_container(self, image_url, caption):
        """
        Cria um contêiner de mídia para o post com retry logic.
        """
        # Check container cache first
        cache_key = f"{image_url}:{caption[:50]}"  # Use URL and start of caption as key
        if cache_key in self.container_cache and time.time() - self.container_cache[cache_key]['timestamp'] < 3600:
            container_id = self.container_cache[cache_key]['id']
            print(f"Reusing cached container ID: {container_id} (created within the last hour)")
            return container_id
            
        # Respect minimum spacing between container creation calls
        self._respect_api_spacing('media')
        
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
            
            # Cache the container ID
            self.container_cache[cache_key] = {
                'id': container_id,
                'timestamp': time.time()
            }
            
            return container_id
        return None

    def publish_media(self, media_container_id):
        """
        Publica o contêiner de mídia no Instagram com retry logic.
        """
        # Respect minimum spacing between publish calls
        self._respect_api_spacing('media_publish')
        
        # Apply forced backoff between container creation and publishing
        self._forced_rate_limit_backoff()
        
        # Much longer wait before publishing in high backoff scenarios
        if self.app_level_backoff > 300:
            # Calculate a progressive delay based on backoff level
            extra_wait = min(900, self.app_level_backoff * 0.75)  # Up to 15 minutes
            print(f"Modo de backoff progressivo: aguardando {extra_wait:.1f}s adicionais antes da publicação")
            time.sleep(extra_wait)
        
        # Extended pre-check with more attempts and longer delays
        if self.app_level_backoff > 300:
            print(f"Nível de backoff alto: verificando se o container já está publicado")
            # Try verification before making a new API call
            for i in range(5):  # Increased from 3 to 5 attempts
                wait_before_check = 45 * (i + 1)  # Progressive wait: 45s, 90s, 135s, 180s, 225s
                print(f"Aguardando {wait_before_check}s antes da verificação {i+1}/5...")
                time.sleep(wait_before_check)
                
                print(f"Tentativa de verificação direta {i+1}/5...")
                success, permalink = self._verify_media_status(
                    media_container_id, 
                    max_attempts=3,
                    delay=30,  # Increased delay between checks
                    check_permalink=False
                )
                if success:
                    print("Publicação já confirmada! Evitando chamada API adicional.")
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

        # Significantly longer delay between creation and publishing (3 minutes)
        base_delay = 20  # 
        if self.app_level_backoff > 300:
            base_delay = 300  # Increased from 45s to 300s when in backoff mode
        
        print(f"Aguardando estabilização do container ({base_delay} segundos)...")
        time.sleep(base_delay)

        # Sleep for a random short time to avoid pattern detection
        jitter = random.uniform(1, 5)
        time.sleep(jitter)

        post_id = self.publish_media(media_container_id)
        if post_id:
            # Reset backoff after successful posting
            if self.app_level_backoff > 300:
                print("Publicação bem-sucedida, reduzindo nível de backoff")
                self.app_level_backoff = max(300, self.app_level_backoff / 2)
                self._save_api_state()
            
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
