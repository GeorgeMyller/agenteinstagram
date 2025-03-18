import logging
import time
import os
import json
from datetime import datetime, timedelta
from typing import Tuple, Optional, List

logger = logging.getLogger('InstagramPublicationVerifier')

class InstagramPublicationVerifier:
    """
    Class to verify if a container has already been published on Instagram.
    This helps prevent duplicate posts when the system encounters errors
    during the publication process.
    
    IMPORTANTE: Observamos que mesmo quando a API do Instagram retorna um erro 403 (rate limit),
    em muitos casos a publicação é realmente processada e o post é criado. Este comportamento
    inconsistente da API requer que sejamos conservadores e assumamos que tentativas com erro
    podem ter resultado em posts bem-sucedidos para evitar duplicatas.
    """
    
    # Class variable to store container publish attempts
    PUBLISH_ATTEMPTS_FILE = 'container_publish_attempts.json'
    _publish_attempts = {}
    _last_load_time = 0
    
    def __init__(self, instagram_service):
        """
        Initialize the verifier with a reference to the Instagram service.
        
        Args:
            instagram_service: An instance of InstagramPostService
        """
        self.instagram_service = instagram_service
        self._load_publish_attempts()
    
    def _load_publish_attempts(self):
        """Load the record of container publish attempts"""
        current_time = time.time()
        # Only reload if more than 60 seconds have passed since last load
        if current_time - InstagramPublicationVerifier._last_load_time < 60:
            return
            
        try:
            if os.path.exists(self.PUBLISH_ATTEMPTS_FILE):
                with open(self.PUBLISH_ATTEMPTS_FILE, 'r') as f:
                    InstagramPublicationVerifier._publish_attempts = json.load(f)
                    logger.info(f"Loaded {len(InstagramPublicationVerifier._publish_attempts)} container publish attempts")
            InstagramPublicationVerifier._last_load_time = current_time
        except Exception as e:
            logger.error(f"Error loading container publish attempts: {str(e)}")
    
    def _save_publish_attempts(self):
        """Save the record of container publish attempts"""
        try:
            # Clean up old entries to keep the file size manageable
            self._cleanup_old_attempts()
            
            with open(self.PUBLISH_ATTEMPTS_FILE, 'w') as f:
                json.dump(InstagramPublicationVerifier._publish_attempts, f, indent=2)
                logger.info(f"Saved {len(InstagramPublicationVerifier._publish_attempts)} container publish attempts")
        except Exception as e:
            logger.error(f"Error saving container publish attempts: {str(e)}")
    
    def _cleanup_old_attempts(self):
        """Remove attempts older than 7 days"""
        current_time = time.time()
        one_week_ago = current_time - (7 * 24 * 60 * 60)  # 7 days in seconds
        
        containers_to_remove = []
        for container_id, attempt_data in InstagramPublicationVerifier._publish_attempts.items():
            attempt_time = attempt_data.get('attempt_time', 0)
            if attempt_time < one_week_ago:
                containers_to_remove.append(container_id)
        
        for container_id in containers_to_remove:
            InstagramPublicationVerifier._publish_attempts.pop(container_id, None)
    
    def record_publish_attempt(self, container_id: str):
        """
        Record that a publish attempt was made for a container
        
        Args:
            container_id: The container ID that was attempted to be published
        """
        # Record the attempt with timestamp
        InstagramPublicationVerifier._publish_attempts[container_id] = {
            'attempt_time': time.time(),
            'timestamp': datetime.now().isoformat()
        }
        self._save_publish_attempts()
    
    def verify_publication(self, container_id: str) -> Tuple[bool, Optional[str]]:
        """
        Verify if a container has already been published to Instagram.
        
        Args:
            container_id: The ID of the container to check
            
        Returns:
            Tuple of (is_published, post_id)
        """
        # First check if we have a record of attempting to publish this container
        self._load_publish_attempts()
        if container_id in InstagramPublicationVerifier._publish_attempts:
            attempt_data = InstagramPublicationVerifier._publish_attempts[container_id]
            attempt_time = attempt_data.get('attempt_time', 0)
            
            # Se tentamos publicar este container recentemente (última hora)
            # há uma boa chance de que tenha sido publicado com sucesso,
            # mesmo se recebemos um erro 403 ou 400
            if time.time() - attempt_time < 3600:  # 1 hour in seconds
                logger.info(f"Container {container_id} was attempted to be published within the last hour")
                
                # Try to verify with Instagram API
                is_published, post_id = self._verify_with_api(container_id)
                if is_published:
                    return True, post_id
                
                # Se a verificação API falhar mas tentamos recentemente, assumimos que foi publicado
                # para prevenir posts duplicados (melhor perder um post do que duplicar)
                # NOTA: Observamos que o Instagram frequentemente publica mesmo retornando erro 403
                logger.warning(f"Assuming container {container_id} was published to prevent duplication")
                return True, None
        
        # If we don't have a record or it's an old attempt, verify with the API
        return self._verify_with_api(container_id)
    
    def _verify_with_api(self, container_id: str) -> Tuple[bool, Optional[str]]:
        """Verify publication using Instagram API"""
        try:
            # Try to get recent posts from Instagram
            posts = self._get_recent_posts(limit=20)  # Increase limit for better chance of finding
            
            if not posts or not isinstance(posts, list):
                logger.warning(f"Could not verify publication - no recent posts returned")
                return False, None
            
            # Check if the container ID appears in any recent post
            for post in posts:
                post_container_id = self._get_container_id_from_post(post, container_id)
                
                if post_container_id and post_container_id == container_id:
                    post_id = post.get('id')
                    logger.info(f"Container {container_id} verified as published with post ID: {post_id}")
                    
                    # Record the verified publication
                    if container_id not in InstagramPublicationVerifier._publish_attempts:
                        self.record_publish_attempt(container_id)
                        
                    return True, post_id
            
            # Not found in recent posts
            logger.info(f"Container {container_id} not found in recent posts")
            return False, None
            
        except Exception as e:
            logger.error(f"Error verifying publication status: {str(e)}")
            # In case of error, we assume it's not published to be safe
            return False, None
    
    def _get_recent_posts(self, limit: int = 10) -> List[dict]:
        """
        Get a list of recent posts from Instagram.
        
        Returns:
            List of post objects
        """
        try:
            # Use the Instagram Graph API to get recent media
            params = {
                'fields': 'id,media_type,media_url,permalink,caption,thumbnail_url,timestamp,created_time',
                'limit': limit
            }
            
            # Make the API request
            result = self.instagram_service._make_request(
                'GET', 
                f"{self.instagram_service.ig_user_id}/media", 
                params=params
            )
            
            if result and 'data' in result:
                return result['data']
                
            return []
            
        except Exception as e:
            logger.error(f"Error getting recent posts: {str(e)}")
            return []
    
    def _get_container_id_from_post(self, post: dict, target_container_id: str = None) -> Optional[str]:
        """
        Extract container ID from a post if available.
        This uses multiple strategies to try to identify if a post matches a container ID.
        
        IMPORTANT: O Instagram frequentemente publica posts mesmo retornando códigos de erro 403.
        Esta função usa estratégias múltiplas para tentar identificar publicações "fantasmas"
        que foram criadas apesar dos erros reportados pela API.
        
        Args:
            post: Post data from the Instagram API
            target_container_id: Optional container ID we're specifically looking for
            
        Returns:
            Container ID if found, None otherwise
        """
        # Strategy 1: Look for container ID in caption (in case we embedded it)
        if 'caption' in post and post['caption']:
            caption = post['caption']
            # Check if the caption contains the container ID
            if target_container_id and target_container_id in caption:
                return target_container_id
        
        # Strategy 2: Use timestamp to match recent publish attempts
        if target_container_id and target_container_id in InstagramPublicationVerifier._publish_attempts:
            attempt_data = InstagramPublicationVerifier._publish_attempts[target_container_id]
            attempt_time = attempt_data.get('attempt_time', 0)
            
            # Get post timestamp
            post_time = None
            if 'timestamp' in post:
                try:
                    # Parse ISO format timestamp
                    post_time = datetime.fromisoformat(post['timestamp'].replace('Z', '+00:00'))
                    post_timestamp = post_time.timestamp()
                except (ValueError, TypeError):
                    post_timestamp = None
            elif 'created_time' in post:
                try:
                    # Parse Unix timestamp
                    post_timestamp = float(post['created_time'])
                except (ValueError, TypeError):
                    post_timestamp = None
            
            if post_timestamp:
                # Aumentado o intervalo de tempo para até 30 minutos, já que verificamos
                # que o Instagram pode publicar com atraso mesmo após erros
                time_diff = abs(post_timestamp - attempt_time)
                if time_diff < 1800:  # 30 minutes in seconds (aumento de 10 para 30 minutos)
                    logger.info(f"Found post with timestamp close to publish attempt: {time_diff}s difference")
                    return target_container_id
        
        # Strategy 3: For all posts, check if they were created very recently
        if 'timestamp' in post or 'created_time' in post:
            try:
                if 'timestamp' in post:
                    post_time = datetime.fromisoformat(post['timestamp'].replace('Z', '+00:00'))
                    post_timestamp = post_time.timestamp()
                else:
                    post_timestamp = float(post['created_time'])
                
                # Se o post foi criado nos últimos 30 minutos e estamos procurando um container específico
                # Também aumentamos este intervalo para capturar publicações atrasadas
                if target_container_id and (time.time() - post_timestamp < 1800):
                    logger.info(f"Found very recent post, likely matches container {target_container_id}")
                    return target_container_id
            except (ValueError, TypeError) as e:
                logger.error(f"Error parsing timestamp: {e}")
        
        # No match found
        return None
    
    def check_recent_publications_after_error(self, container_id: str) -> Tuple[bool, Optional[str]]:
        """
        Método especializado para verificar publicações feitas nos últimos minutos.
        Este método deve ser chamado imediatamente após receber um erro 403/400
        para verificar se o post foi publicado apesar do erro.
        
        Args:
            container_id: The ID of the container to check
            
        Returns:
            Tuple of (is_published, post_id)
        """
        logger.info(f"Checking if container {container_id} was published despite error...")
        
        try:
            # Fazer várias tentativas com intervalo para dar tempo do post aparecer no feed
            max_attempts = 3
            for attempt in range(max_attempts):
                # Obter posts recentes com limite maior para aumentar chances de encontrar
                posts = self._get_recent_posts(limit=30)
                
                if not posts:
                    logger.warning("No recent posts found")
                    
                    # Esperar antes da próxima tentativa
                    if attempt < max_attempts - 1:
                        time.sleep(10)  # Esperar 10 segundos entre tentativas
                    continue
                
                # Ordenar posts por timestamp (mais recente primeiro) se disponível
                sorted_posts = []
                for post in posts:
                    try:
                        if 'timestamp' in post:
                            timestamp = datetime.fromisoformat(post['timestamp'].replace('Z', '+00:00')).timestamp()
                            sorted_posts.append((post, timestamp))
                        else:
                            # Se não tiver timestamp, colocar no final da lista
                            sorted_posts.append((post, 0))
                    except Exception:
                        sorted_posts.append((post, 0))
                
                # Ordenar por timestamp decrescente
                sorted_posts.sort(key=lambda x: x[1], reverse=True)
                
                # Verificar os 5 posts mais recentes com especial atenção
                for i, (post, _) in enumerate(sorted_posts[:5]):
                    match_confidence = self._estimate_post_match_confidence(post, container_id)
                    
                    if match_confidence > 0.8:  # 80% de confiança
                        post_id = post.get('id')
                        logger.info(f"Found recent post (position {i+1}) that likely matches container {container_id}")
                        return True, post_id
                
                # Se não encontrou nos primeiros 5, verificar o restante
                for i, (post, _) in enumerate(sorted_posts[5:]):
                    post_container_id = self._get_container_id_from_post(post, container_id)
                    if post_container_id and post_container_id == container_id:
                        post_id = post.get('id')
                        logger.info(f"Found post at position {i+6} that matches container {container_id}")
                        return True, post_id
                
                # Não encontrou, aguardar antes da próxima tentativa
                if attempt < max_attempts - 1:
                    logger.info(f"No matching post found in attempt {attempt+1}, waiting before retry...")
                    time.sleep(10)  # Esperar 10 segundos entre tentativas
            
            # Se chegou aqui, não encontrou após várias tentativas
            return False, None
            
        except Exception as e:
            logger.error(f"Error checking recent publications after error: {str(e)}")
            return False, None
    
    def _estimate_post_match_confidence(self, post: dict, container_id: str) -> float:
        """
        Estima a confiança de que um post corresponde a um container específico.
        Útil para identificar publicações feitas apesar de erros 403/400.
        
        Returns:
            float: Score de confiança entre 0.0 e 1.0
        """
        confidence = 0.0
        
        # Verificar tentativas recentes deste container
        if container_id in self._publish_attempts:
            attempt_data = self._publish_attempts[container_id]
            attempt_time = attempt_data.get('attempt_time', 0)
            
            # Post tem timestamp?
            if 'timestamp' in post:
                try:
                    post_time = datetime.fromisoformat(post['timestamp'].replace('Z', '+00:00'))
                    post_timestamp = post_time.timestamp()
                    
                    # Calcular diferença de tempo
                    time_diff = abs(post_timestamp - attempt_time)
                    
                    # Se publicado até 5 minutos depois da tentativa, alta confiança
                    if 0 <= time_diff <= 300:  # 5 minutos
                        confidence += 0.7
                    # Se entre 5 e 15 minutos, confiança moderada
                    elif time_diff <= 900:  # 15 minutos
                        confidence += 0.5
                    # Se entre 15 e 30 minutos, baixa confiança
                    elif time_diff <= 1800:  # 30 minutos
                        confidence += 0.3
                except (ValueError, TypeError):
                    pass
            
            # Se foi um dos posts mais recentes, aumentar confiança
            if 'created_time' in post or 'timestamp' in post:
                confidence += 0.2
        
        return min(confidence, 1.0)  # Limitar a 1.0