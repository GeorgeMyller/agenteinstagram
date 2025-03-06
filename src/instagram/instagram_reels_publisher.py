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
import requests
from urllib.parse import urlencode
from dotenv import load_dotenv
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from pathlib import Path
from src.instagram.instagram_video_processor import VideoProcessor
from src.instagram.instagram_video_uploader import VideoUploader
from PIL import Image

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
        Publica o Reels usando o container criado anteriormente.
        
        Args:
            container_id (str): ID do container de mídia
            
        Returns:
            str: ID da publicação ou None em caso de falha
        """
        endpoint = f"{self.ig_user_id}/media_publish"
        params = {
            'creation_id': container_id
        }
        
        result = self._make_api_request('POST', endpoint, data=params)
        
        if result and 'id' in result:
            post_id = result['id']
            logger.info(f"Reels publicado com sucesso: {post_id}")
            return post_id
        else:
            logger.error("Falha ao publicar Reels")
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
            return None
        
        # 2. Aguardar processamento
        logger.info(f"Aguardando processamento do Reels... (máx. {max_retries} tentativas)")
        status = None
        
        for attempt in range(max_retries):
            status = self.check_container_status(container_id)
            
            if status == 'FINISHED':
                logger.info("Reels processado com sucesso!")
                break
            elif status in ['ERROR', 'EXPIRED']:
                logger.error(f"Erro no processamento do Reels: {status}")
                return None
            
            logger.info(f"Status atual: {status}. Aguardando {retry_interval}s... " 
                      f"(tentativa {attempt + 1}/{max_retries})")
            time.sleep(retry_interval)
        
        # Verificar se saiu do loop por timeout
        if status != 'FINISHED':
            logger.error("Tempo máximo de processamento excedido")
            return None
        
        # 3. Publicar o Reels
        post_id = self.publish_reels(container_id)
        
        if not post_id:
            return None
        
        # 4. Obter permalink
        permalink = self.get_reels_permalink(post_id)
        
        # 5. Retornar informações da publicação
        return {
            'id': post_id,
            'permalink': permalink,
            'container_id': container_id,
            'media_type': 'REELS'
        }
    
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
        processor = VideoProcessor()
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
                
                optimized_video = processor.optimize_for_instagram(
                    video_path, 
                    post_type='reels'
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
            
            # Fazer upload do vídeo para hospedagem temporária
            logger.info(f"Enviando vídeo para hospedagem temporária...")
            upload_result = uploader.upload_from_path(video_to_upload)
            
            if not upload_result or not upload_result.get('url'):
                logger.error("Falha no upload do vídeo para hospedagem temporária")
                return None
            
            video_url = upload_result.get('url')
            logger.info(f"Vídeo disponível em: {video_url}")
            
            # Publicar o Reels usando a URL do vídeo
            try:
                result = self.post_reels(
                    video_url=video_url,
                    caption=final_caption,
                    share_to_feed=share_to_feed,
                    audio_name=audio_name,
                    thumbnail_url=thumbnail_url
                )
                
                # Limpar recursos temporários
                if upload_result.get('deletehash'):
                    uploader.delete_video(upload_result['deletehash'])
                
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
                # Limpar recursos em caso de erro
                if upload_result.get('deletehash'):
                    uploader.delete_video(upload_result['deletehash'])
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