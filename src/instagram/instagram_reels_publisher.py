"""
Módulo especializado para publicação de Reels no Instagram
Implementado com base nos exemplos oficiais da Meta para publicação de Reels
Fonte: https://github.com/fbsamples/reels_publishing_apis

Este módulo implementa as melhores práticas e parâmetros específicos
para a publicação de Reels no Instagram.
"""

import os
import time
import json
import logging
import random
import requests
import traceback
import sys
from datetime import datetime
from urllib.parse import urlencode
from dotenv import load_dotenv
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from pathlib import Path
from src.instagram.instagram_video_processor import VideoProcessor
from src.instagram.instagram_video_uploader import VideoUploader
from src.instagram.instagram_video_processor import InstagramVideoProcessor
from imgurpython import ImgurClient

# Configurar logger
logger = logging.getLogger('ReelsPublisher')

class ReelsPublisher:
    """
    Classe especializada para publicação de Reels no Instagram.
    Implementa o fluxo completo de publicação conforme documentação oficial da Meta.
    """
    
    # API Graph do Instagram (versão atualizada)
    API_VERSION = 'v18.0'
    
    # Configurações específicas para Reels
    REELS_CONFIG = {
        'aspect_ratio': '9:16',     # Proporção de aspecto padrão para Reels (vertical)
        'min_duration': 3,           # Duração mínima em segundos
        'max_duration': 90,          # Duração máxima em segundos (Reels mais curtos têm melhor desempenho)
        'recommended_duration': 30,  # Duração recomendada pela Meta
        'min_width': 500,            # Largura mínima em pixels
        'recommended_width': 1080,   # Largura recomendada em pixels
        'recommended_height': 1920,  # Altura recomendada em pixels
        'video_formats': ['mp4'],    # Formatos suportados
        'video_codecs': ['h264'],    # Codecs de vídeo recomendados
        'audio_codecs': ['aac'],     # Codecs de áudio recomendados
    }
    
    # Códigos de erro específicos para Reels
    REELS_ERROR_CODES = {
        2207026: "Formato de vídeo não suportado para Reels",
        2207014: "Duração de vídeo não compatível com Reels",
        2207013: "Proporção de aspecto do vídeo não é compatível com Reels",
        9007: "Permissão de publicação de Reels negada",
    }
    
    def __init__(self, access_token=None, ig_user_id=None):
        """
        Inicializa o publicador de Reels.
        
        Args:
            access_token (str): Token de acesso da API do Instagram/Facebook
            ig_user_id (str): ID da conta do Instagram
        """
        load_dotenv()
        
        # Obter credenciais de variáveis de ambiente se não fornecidas
        self.access_token = access_token or (
            os.getenv('INSTAGRAM_API_KEY') or 
            os.getenv('INSTAGRAM_ACCESS_TOKEN') or 
            os.getenv('FACEBOOK_ACCESS_TOKEN')
        )
        
        self.ig_user_id = ig_user_id or os.getenv("INSTAGRAM_ACCOUNT_ID")
        
        if not self.access_token or not self.ig_user_id:
            raise ValueError(
                "Credenciais incompletas. Defina INSTAGRAM_ACCESS_TOKEN e "
                "INSTAGRAM_ACCOUNT_ID nas variáveis de ambiente ou forneça-os diretamente."
            )
        
        # Configurar a sessão HTTP com retry
        self.session = self._setup_session()
        
        # Validar token antes de prosseguir
        self._validate_token()

        self.imgur_client = ImgurClient(os.getenv('IMGUR_CLIENT_ID'), os.getenv('IMGUR_CLIENT_SECRET'))
    
    def _setup_session(self):
        """Configura a sessão HTTP com retry e outros parâmetros."""
        session = requests.Session()
        
        # Configurar retry para lidar com falhas temporárias
        retry_strategy = Retry(
            total=5,
            backoff_factor=1.0,
            status_forcelist=[408, 429, 500, 502, 503, 504],
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount('https://', adapter)
        
        # Headers comuns para todas as requisições
        session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        })
        
        return session
    
    def _validate_token(self):
        """Valida o token de acesso antes de fazer requisições."""
        url = f"https://graph.facebook.com/{self.API_VERSION}/debug_token"
        params = {
            "input_token": self.access_token,
            "access_token": self.access_token
        }
        
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if 'data' in data and data['data'].get('is_valid'):
                logger.info("Token de acesso validado com sucesso.")
                
                # Verificar se tem permissão para publicar Reels
                if 'instagram_basic' not in data['data'].get('scopes', []) or \
                   'instagram_content_publish' not in data['data'].get('scopes', []):
                    logger.warning("Token pode não ter permissões para publicar Reels. "
                                  "Verifique se as permissões 'instagram_basic' e "
                                  "'instagram_content_publish' estão habilitadas.")
            else:
                logger.error("Token de acesso inválido ou expirado.")
        except Exception as e:
            logger.error(f"Erro ao validar token: {e}")
    
    def _make_api_request(self, method, endpoint, params=None, data=None):
        """
        Faz uma requisição para a API Graph do Instagram com tratamento de erros.
        
        Args:
            method (str): Método HTTP (GET, POST, etc)
            endpoint (str): Endpoint da API (sem URL base)
            params (dict): Parâmetros de URL
            data (dict): Corpo da requisição para métodos POST
            
        Returns:
            dict: Resposta da API ou None em caso de erro
        """
        # Construir a URL completa
        url = f"https://graph.facebook.com/{self.API_VERSION}/{endpoint}"
        
        # Adicionar token de acesso aos parâmetros
        params = params or {}
        params['access_token'] = self.access_token
        
        # Log da requisição (removendo dados sensíveis)
        safe_params = {k: '***REDACTED***' if k == 'access_token' else v 
                    for k, v in params.items()}
        logger.debug(f"Requisição {method} para {endpoint}: {safe_params}")
        
        try:
            if method.upper() == 'GET':
                response = self.session.get(url, params=params)
            elif method.upper() == 'POST':
                if data:
                    response = self.session.post(url, params=params, json=data)
                else:
                    response = self.session.post(url, params=params)
            else:
                response = self.session.request(method, url, params=params, json=data)
            
            # Verificar status HTTP
            response.raise_for_status()
            
            # Retornar dados JSON
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"Erro HTTP {e.response.status_code}: {e}")
            
            # Tentar extrair detalhes do erro da API
            try:
                error_data = e.response.json()
                if 'error' in error_data:
                    error = error_data['error']
                    error_code = error.get('code')
                    error_message = error.get('message')
                    
                    # Sugestão específica para erros de Reels
                    if error_code in self.REELS_ERROR_CODES:
                        logger.error(f"Erro específico de Reels: {self.REELS_ERROR_CODES[error_code]}")
                    
                    logger.error(f"Erro da API: Código {error_code}, Mensagem: {error_message}")
            except:
                logger.error(f"Resposta de erro não-JSON: {e.response.text}")
                
            return None
            
        except Exception as e:
            logger.error(f"Erro na requisição: {str(e)}")
            return None
    
    def create_reels_container(self, video_url, caption, share_to_feed=True, 
                               audio_name=None, thumbnail_url=None, user_tags=None):
        """
        Cria um container para Reels.
        
        Args:
            video_url (str): URL pública do vídeo
            caption (str): Legenda do Reels
            share_to_feed (bool): Se o Reels deve ser compartilhado também no feed
            audio_name (str, optional): Nome do áudio a ser exibido no Reels
            thumbnail_url (str, optional): URL da imagem de miniatura personalizada
            user_tags (list, optional): Lista de usuários marcados no formato adequado
            
        Returns:
            str: ID do container ou None em caso de falha
        """
        endpoint = f"{self.ig_user_id}/media"
        
        # Parâmetros específicos para Reels conforme documentação da Meta
        params = {
            'media_type': 'REELS',
            'video_url': video_url,
            'caption': caption,
            'share_to_feed': 'true' if share_to_feed else 'false',
        }
        
        # Adicionar parâmetros opcionais se fornecidos
        if audio_name:
            params['audio_name'] = audio_name
            
        if thumbnail_url:
            params['thumbnail_url'] = thumbnail_url
            
        if user_tags:
            if isinstance(user_tags, list) and user_tags:
                params['user_tags'] = json.dumps(user_tags)
        
        # Fazer requisição à API
        result = self._make_api_request('POST', endpoint, data=params)
        
        if result and 'id' in result:
            container_id = result['id']
            logger.info(f"Container de Reels criado com sucesso: {container_id}")
            return container_id
        else:
            logger.error("Falha ao criar container de Reels")
            return None
    
    def check_container_status(self, container_id):
        """
        Verifica o status do container de mídia.
        
        Args:
            container_id (str): ID do container
            
        Returns:
            str: Status do container ('FINISHED', 'ERROR', etc) ou None
        """
        endpoint = f"{container_id}"
        params = {
            'fields': 'status_code,status'
        }
        
        result = self._make_api_request('GET', endpoint, params=params)
        
        if result:
            status = result.get('status_code')
            logger.info(f"Status do container: {status}")
            
            # Detalhes adicionais se houver erro
            if status == 'ERROR' and 'status' in result:
                logger.error(f"Detalhes do erro: {result['status']}")
                
            return status
        
        return None
    
    def publish_reels(self, container_id):
        """
        Publica o Reels usando o container criado anteriormente, com melhor
        tratamento de erros e estratégias de recuperação.
        
        Args:
            container_id (str): ID do container de mídia
            
        Returns:
            str: ID da publicação ou None em caso de falha
        """
        endpoint = f"{self.ig_user_id}/media_publish"
        params = {
            'creation_id': container_id
        }
        
        max_retries = 5
        retry_delay = 10
        
        for attempt in range(max_retries):
            try:
                result = self._make_api_request('POST', endpoint, data=params)
                
                if result and 'id' in result:
                    post_id = result['id']
                    logger.info(f"Reels publicado com sucesso: {post_id}")
                    return post_id
                
                # Analisar o erro para decidir se devemos tentar novamente
                if hasattr(self, '_last_error') and self._last_error:
                    error_data = self._last_error.get('error', {})
                    error_code = error_data.get('code')
                    error_message = error_data.get('message', 'Erro desconhecido')
                    
                    # Alguns erros não adianta tentar novamente
                    if error_code in [190, 10, 200, 2207026]:
                        logger.error(f"Erro fatal na publicação: {error_message} (Código: {error_code})")
                        return None
                    
                    # Para o erro genérico 1, aumentar o tempo de espera exponencialmente
                    if error_code == 1:
                        backoff_time = retry_delay * (2 ** attempt) + random.uniform(5, 15)
                        logger.warning(f"Erro genérico (código 1). Aguardando {backoff_time:.1f}s...")
                        time.sleep(backoff_time)
                        continue
                
                # Backoff exponencial com jitter
                backoff_time = retry_delay * (2 ** attempt) + random.uniform(0, 5)
                logger.info(f"Tentativa {attempt + 1}/{max_retries}. Aguardando {backoff_time:.1f}s...")
                time.sleep(backoff_time)
                
            except Exception as e:
                logger.error(f"Erro na publicação (tentativa {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (2 ** attempt))
        
        # Verificar se o Reels foi publicado apesar do erro
        if self._verify_recent_posting(minutes=2):
            logger.info("Detectamos um post recente! O vídeo pode ter sido publicado apesar do erro.")
            return "unknown_id_but_likely_posted"
        
        logger.error("Todas as tentativas de publicação falharam")
        return None
    
    def get_reels_permalink(self, post_id):
        """
        Obtém o link permanente (URL) para o Reels publicado.
        
        Args:
            post_id (str): ID da publicação
            
        Returns:
            str: URL do Reels ou None
        """
        endpoint = f"{post_id}"
        params = {
            'fields': 'permalink'
        }
        
        result = self._make_api_request('GET', endpoint, params=params)
        
        if result and 'permalink' in result:
            permalink = result['permalink']
            logger.info(f"Permalink do Reels: {permalink}")
            return permalink
        
        logger.warning("Não foi possível obter permalink do Reels")
        return None
    
    def post_reels(self, video_url, caption, share_to_feed=True, 
                  audio_name=None, thumbnail_url=None, user_tags=None,
                  max_retries=30, retry_interval=10):
        """
        Fluxo completo para postar um Reels: criar container, verificar status e publicar.
        Inclui tratamento robusto de erros e estratégias de recuperação.
        
        Args:
            video_url (str): URL pública do vídeo
            caption (str): Legenda do Reels
            share_to_feed (bool): Se o Reels deve ser compartilhado no feed
            audio_name (str, optional): Nome do áudio a ser exibido
            thumbnail_url (str, optional): URL da miniatura personalizada
            user_tags (list, optional): Lista de usuários marcados
            max_retries (int): Número máximo de tentativas para verificar o status
            retry_interval (int): Tempo de espera entre verificações
            
        Returns:
            dict: Informações sobre o Reels publicado ou None
        """
        # 1. Criar container
        container_id = self.create_reels_container(
            video_url, caption, share_to_feed, audio_name, thumbnail_url, user_tags
        )
        
        if not container_id:
            # Verificar se há algum erro específico para fornecer mensagem mais detalhada
            if hasattr(self, '_last_error') and self._last_error:
                error_data = self._last_error.get('error', {})
                error_code = error_data.get('code')
                error_message = error_data.get('message', 'Erro desconhecido')
                
                logger.error(f"Falha ao criar container. Código: {error_code}, Mensagem: {error_message}")
                
                # Mensagens específicas para erros comuns
                if error_code == 2207026:
                    logger.error("O vídeo não atende aos requisitos de formato do Instagram.")
                    logger.error("Tente processar o vídeo antes do upload usando InstagramVideoProcessor.")
                elif error_code in [4, 17, 32, 613]:
                    logger.error("Limite de taxa excedido. Aguarde alguns minutos antes de tentar novamente.")
            
            return None
        
        # 2. Aguardar processamento com monitoramento aprimorado de status
        logger.info(f"Aguardando processamento do Reels... (máx. {max_retries} tentativas)")
        status = self.wait_for_container_status(container_id, max_attempts=max_retries, delay=retry_interval)
        
        if status != 'FINISHED':
            logger.error(f"Processamento do vídeo falhou com status: {status}")
            
            # Verificar se o vídeo foi publicado apesar do erro
            if self._verify_recent_posting(minutes=2):
                logger.info("Um post recente foi detectado! O vídeo pode ter sido publicado apesar do erro.")
                return {
                    'id': 'unknown_id_but_likely_posted',
                    'container_id': container_id,
                    'media_type': 'REELS',
                    'status': 'UNCERTAIN_BUT_LIKELY_POSTED'
                }
            
            return None
        
        # 3. Publicar o Reels com estratégias de recuperação
        post_id = self.publish_reels(container_id)
        
        if not post_id:
            return None
        
        # 4. Obter permalink
        permalink = self.get_reels_permalink(post_id)
        
        # 5. Retornar informações da publicação
        result = {
            'id': post_id,
            'permalink': permalink,
            'container_id': container_id,
            'media_type': 'REELS'
        }
        
        logger.info("Reels publicado com sucesso!")
        logger.info(f"ID: {post_id}")
        logger.info(f"Link: {permalink or 'Não disponível'}")
        
        return result
    
    def upload_local_video_to_reels(self, video_path, caption, hashtags=None, 
                                    optimize=True, thumbnail_path=None, 
                                    share_to_feed=True, audio_name=None):
        """
        Envia um vídeo local para o Instagram como Reels.
        Gerencia todo o fluxo de otimização, upload e publicação.
        
        Args:
            video_path (str): Caminho local do arquivo de vídeo
            caption (str): Legenda do Reels
            hashtags (list or str): Lista ou string com hashtags (sem #)
            optimize (bool): Se deve otimizar o vídeo para Reels
            thumbnail_path (str, optional): Caminho para imagem de miniatura
            share_to_feed (bool): Se o Reels deve aparecer também no feed
            audio_name (str, optional): Nome personalizado para o áudio
            
        Returns:
            dict: Informações sobre o Reels publicado ou None em caso de falha
        """
        if not os.path.exists(video_path):
            logger.error(f"Arquivo de vídeo não encontrado: {video_path}")
            return None
        
        # Formatar legenda com hashtags
        final_caption = self._format_caption_with_hashtags(caption, hashtags)
        
        # Processar o vídeo se necessário
        processor = InstagramVideoProcessor()
        uploader = VideoUploader()
        video_to_upload = video_path
        thumbnail_url = None
        is_video_optimized = False
        
        try:
            # Verificar se o vídeo atende aos requisitos para Reels
            is_valid, message = uploader.validate_video(video_path)
            
            if not is_valid and optimize:
                logger.info(f"Vídeo não atende aos requisitos: {message}")
                logger.info("Otimizando vídeo para Reels...")
                
                optimized_video = processor.process_video(
                    video_path, 
                    post_type='reel'  # Corrigido de 'reels' para 'reel'
                )
                
                if optimized_video:
                    logger.info(f"Vídeo otimizado: {optimized_video}")
                    video_to_upload = optimized_video
                    is_video_optimized = True
                else:
                    logger.warning("Falha na otimização automática. Tentando upload do vídeo original.")
            
            # Processar thumbnail se fornecida
            if thumbnail_path and os.path.exists(thumbnail_path):
                logger.info(f"Enviando thumbnail personalizada: {thumbnail_path}")
                thumb_result = uploader.upload_from_path(thumbnail_path)
                
                if thumb_result and thumb_result.get('url'):
                    thumbnail_url = thumb_result.get('url')
                    logger.info(f"Thumbnail enviada: {thumbnail_url}")
            
            # Upload video to Imgur
            logger.info(f"Enviando vídeo para Imgur...")
            imgur_response = self.imgur_client.upload_from_path(video_to_upload, config=None, anon=True)
            video_url = imgur_response['link']
            logger.info(f"Vídeo disponível em: {video_url}")

            # Publicar o Reels usando a URL do vídeo
            result = self.post_reels(
                video_url=video_url,
                caption=final_caption,
                share_to_feed=share_to_feed,
                audio_name=audio_name,
                thumbnail_url=thumbnail_url
            )

            # Remover arquivo de vídeo otimizado temporário
            if is_video_optimized and os.path.exists(video_to_upload) and video_to_upload != video_path:
                try:
                    os.remove(video_to_upload)
                    logger.info(f"Arquivo temporário removido: {video_to_upload}")
                except Exception as e:
                    logger.warning(f"Não foi possível remover arquivo temporário: {e}")

            return result

        except Exception as e:
            logger.error(f"Erro na publicação do Reels: {e}")
            return None

        except Exception as e:
            logger.error(f"Erro no processamento do vídeo: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def _format_caption_with_hashtags(self, caption, hashtags=None):
        """
        Formata a legenda com hashtags.
        
        Args:
            caption (str): Legenda original
            hashtags (list or str): Lista de hashtags ou string com hashtags separadas por vírgula
            
        Returns:
            str: Legenda formatada com hashtags
        """
        if not hashtags:
            return caption
            
        # Converter string de hashtags separadas por vírgula em lista
        if isinstance(hashtags, str):
            hashtag_list = [tag.strip() for tag in hashtags.split(',')]
        else:
            hashtag_list = hashtags
        
        # Formatar cada hashtag e adicionar à legenda
        hashtag_text = ' '.join([f"#{tag}" for tag in hashtag_list if tag])
        
        if caption:
            return f"{caption}\n\n{hashtag_text}"
        else:
            return hashtag_text
        
    def get_account_info(self):
        """
        Obtém informações sobre a conta do Instagram associada.
        
        Returns:
            dict: Informações da conta ou None em caso de falha
        """
        endpoint = f"{self.ig_user_id}"
        params = {
            'fields': 'id,username,name,profile_picture_url,biography,follows_count,followers_count,media_count'
        }
        
        result = self._make_api_request('GET', endpoint, params=params)
        return result
        
    def delete_reels(self, media_id):
        """
        Remove um Reels publicado.
        
        Args:
            media_id (str): ID do Reels
            
        Returns:
            bool: True se excluído com sucesso, False caso contrário
        """
        endpoint = f"{media_id}"
        
        result = self._make_api_request('DELETE', endpoint)
        
        if result and result.get('success') is True:
            logger.info(f"Reels {media_id} removido com sucesso")
            return True
        
        logger.error(f"Erro ao remover Reels {media_id}")
        return False
    
    # Adicionar um método para lidar com erros específicos da API
    def _handle_api_error(self, error_data, context=""):
        """
        Trata erros específicos da API do Instagram/Facebook com mensagens e estratégias
        de recuperação adequadas.
        
        Args:
            error_data (dict): Dados do erro da resposta da API
            context (str): Contexto adicional sobre onde o erro ocorreu
            
        Returns:
            tuple: (deve_tentar_novamente, tempo_espera, mensagem_erro)
        """
        try:
            error = error_data.get('error', {})
            code = error.get('code')
            message = error.get('message', '')
            error_type = error.get('type', '')
            fb_trace_id = error.get('fbtrace_id', 'N/A')
            
            error_message = f"\nErro na API do Instagram ({context}):"
            error_message += f"\nCódigo: {code}"
            error_message += f"\nTipo: {error_type}"
            error_message += f"\nMensagem: {message}"
            error_message += f"\nTrace ID: {fb_trace_id}"
            
            # Erros de autenticação (190, 104, etc)
            if code in [190, 104]:
                error_message += "\n\nErro de autenticação. Ações recomendadas:"
                error_message += "\n1. Verifique se o token não expirou"
                error_message += "\n2. Gere um novo token de acesso"
                error_message += "\n3. Confirme se o token tem as permissões necessárias"
                return False, 0, error_message
            
            # Erros de permissão (200, 10, 803)
            elif code in [200, 10, 803]:
                error_message += "\n\nErro de permissão. Ações recomendadas:"
                error_message += "\n1. Verifique se a conta é Business/Creator"
                error_message += "\n2. Confirme as permissões do app no Facebook Developer"
                return False, 0, error_message
            
            # Erros de limite de taxa (4, 17, 32, 613)
            elif code in [4, 17, 32, 613]:
                wait_time = 300  # 5 minutos padrão
                if 'minutes' in message.lower():
                    try:
                        # Tentar extrair tempo de espera da mensagem
                        import re
                        time_match = re.search(r'(\d+)\s*minutes?', message.lower())
                        if time_match:
                            wait_time = int(time_match.group(1)) * 60
                    except:
                        pass
                error_message += f"\n\nLimite de taxa atingido. Aguardando {wait_time/60:.0f} minutos."
                return True, wait_time, error_message
            
            # Erros de formato de mídia (2207026)
            elif code == 2207026:
                error_message += "\n\nErro no formato da mídia. Requisitos para Reels:"
                error_message += "\n- Formato: MP4/MOV"
                error_message += "\n- Codec Vídeo: H.264"
                error_message += "\n- Codec Áudio: AAC"
                error_message += "\n- Resolução: Mínimo 500x500, recomendado 1080x1920"
                error_message += "\n- Duração: 3-90 segundos"
                error_message += "\n- Tamanho: Máximo 100MB"
                return False, 0, error_message
            
            # Erros de servidor (1, 2, 500, etc)
            elif code in [1, 2] or error_type == 'OAuthException':
                error_message += "\n\nErro temporário do servidor. Tentando novamente..."
                return True, 30, error_message
            
            # Caso desconhecido
            else:
                error_message += "\n\nErro desconhecido. Tentando novamente..."
                return True, 30, error_message
                
        except Exception as e:
            return True, 30, f"Erro ao processar resposta de erro: {str(e)}"
    
    def _verify_recent_posting(self, minutes=5):
        """
        Verifica se houve alguma postagem recente na conta.
        Útil para confirmar se um vídeo foi publicado mesmo quando a API retorna erro.
        
        Args:
            minutes (int): Intervalo de tempo em minutos para considerar uma postagem recente
            
        Returns:
            bool: True se encontrou uma postagem recente, False caso contrário
        """
        try:
            url = f"https://graph.facebook.com/{self.API_VERSION}/{self.ig_user_id}/media"
            params = {
                'fields': 'id,media_type,timestamp',
                'limit': 5,
                'access_token': self.access_token
            }
            
            response = self.session.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                if 'data' not in data or not data['data']:
                    return False
                
                now = datetime.now()
                
                for post in data['data']:
                    if 'timestamp' in post and post.get('media_type') in ['VIDEO', 'REELS']:
                        try:
                            # Formato do timestamp: 2023-01-01T12:00:00+0000
                            post_time = datetime.strptime(
                                post['timestamp'].replace('+0000', ''), 
                                '%Y-%m-%dT%H:%M:%S'
                            )
                            
                            # Calcular diferença em minutos
                            time_diff = (now - post_time).total_seconds() / 60
                            
                            if time_diff <= minutes:
                                logger.info(f"Encontrou post recente: {post['id']} ({post['media_type']})")
                                logger.info(f"Publicado há aproximadamente {time_diff:.1f} minutos")
                                return True
                        except Exception as e:
                            logger.debug(f"Erro ao processar data do post: {e}")
            
            return False
            
        except Exception as e:
            logger.error(f"Erro ao verificar postagens recentes: {str(e)}")
            return False
    
    def wait_for_container_status(self, container_id, max_attempts=30, delay=10):
        """
        Aguarda o processamento do container com tratamento aprimorado de erros
        e detecção de problemas.
        
        Args:
            container_id (str): ID do container a verificar
            max_attempts (int): Número máximo de tentativas
            delay (int): Tempo de espera entre tentativas em segundos
            
        Returns:
            str: Status final do container ('FINISHED', 'ERROR', etc)
        """
        last_error_code = None
        endpoint = f"{container_id}"
        
        for attempt in range(max_attempts):
            try:
                params = {
                    'fields': 'status_code,status'
                }
                
                result = self._make_api_request('GET', endpoint, params=params)
                
                if not result:
                    if attempt == max_attempts - 1:
                        logger.error("Erro persistente ao verificar status do container")
                        return 'ERROR'
                    time.sleep(delay)
                    continue
                
                status = result.get('status_code', '')
                logger.info(f"Status do container: {status} (tentativa {attempt + 1}/{max_attempts})")
                
                if status == 'FINISHED':
                    logger.info("Processamento do vídeo concluído com sucesso!")
                    return status
                elif status in ['ERROR', 'EXPIRED']:
                    # Tratamento especial para erros de processamento
                    error_message = result.get('status', 'Sem detalhes')
                    logger.error(f"Erro no processamento do vídeo: {error_message}")
                    
                    # Verificar se há indicação do erro 2207026 (formato de mídia)
                    if '2207026' in str(error_message):
                        last_error_code = 2207026
                        logger.error("ERRO DE FORMATO DE MÍDIA (2207026) DETECTADO")
                        logger.error("Verifique se o vídeo atende aos requisitos do Instagram:")
                        logger.error("- Codec H.264 para vídeo e AAC para áudio")
                        logger.error("- Formato MP4 ou MOV")
                        logger.error("- Resolução adequada (mínimo 500x500)")
                        logger.error("- Duração entre 3 e 90 segundos")
                        
                    return status
                    
                # Mensagens informativas baseadas no status
                if status == 'IN_PROGRESS':
                    logger.info("Vídeo sendo processado pelo Instagram...")
                elif status == 'PUBLISHED':
                    logger.info("Vídeo foi publicado!")
                    return status
                
                # Aguardar antes da próxima verificação
                time.sleep(delay)
                
            except Exception as e:
                logger.error(f"Erro durante verificação de status (tentativa {attempt + 1}): {e}")
                time.sleep(delay)
        
        logger.error("Tempo limite de processamento excedido")
        return 'TIMEOUT'