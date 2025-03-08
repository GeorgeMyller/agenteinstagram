import os
import time
import uuid
import threading
import logging
from queue import Queue, Empty
from threading import Thread

# Configurar logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('PostQueue')

class ContentPolicyViolation(Exception):
    """Exceção para violações de política de conteúdo"""

class RateLimitExceeded(Exception):
    """Exceção para limites de taxa excedidos"""

# Add PostStatus class that monitor.py is trying to import
class PostStatus:
    """Enum-like class to represent post status values"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"
    POLICY_VIOLATION = "policy_violation"

class PostQueue:
    """
    Sistema de filas para processamento assíncrono de posts e reels
    """
    
    def __init__(self):
        """Inicializa o sistema de filas"""
        self.job_queue = Queue()
        self.jobs = {}  # Armazena informações sobre os trabalhos
        self.job_history = []  # Histórico de trabalhos
        self.stats = {
            "total_jobs": 0,
            "completed_jobs": 0,
            "failed_jobs": 0,
            "rate_limited_posts": 0,
            "video_processing_jobs": 0,
            "image_processing_jobs": 0,
            "avg_processing_time": 0
        }
        self.worker_thread = None
        self.is_running = False
        self.processing_lock = threading.Lock()  # Lock para operações críticas

        # Iniciar thread de processamento
        self.start_worker()
    
    def start_worker(self):
        """Inicia o thread worker para processamento de filas"""
        if not self.is_running:
            self.is_running = True
            self.worker_thread = Thread(target=self._process_queue, daemon=True)
            self.worker_thread.start()
            logger.info("Worker de processamento iniciado")
    
    def stop_worker(self):
        """Para o thread worker"""
        self.is_running = False
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=5.0)
            logger.info("Worker de processamento encerrado")
    
    def add_job(self, media_path, caption, inputs=None) -> str:
        """
        Adiciona um novo trabalho à fila
        
        Args:
            media_path (str or list): Caminho do arquivo de mídia ou lista de caminhos
            caption (str): Legenda do post
            inputs (dict): Configurações adicionais
            
        Returns:
            str: ID do trabalho
        """
        job_id = str(uuid.uuid4())
        
        # Converter media_path para lista se for string
        media_paths = media_path if isinstance(media_path, list) else [media_path]
        
        # Verificar tipo de conteúdo
        content_type = "image"  # default
        if inputs and "content_type" in inputs:
            content_type = inputs["content_type"]  # Use explicit content type if provided
        elif len(media_paths) > 1:
            content_type = "carrossel"
        else:
            # Check file extension for video
            path = media_paths[0]
            if isinstance(path, str) and path.lower().endswith(('.mp4', '.mov', '.avi', '.wmv')):
                content_type = "reel"
        
        job_data = {
            "id": job_id,
            "media_paths": media_paths,
            "caption": caption,
            "inputs": inputs or {},
            "status": "pending",
            "created_at": time.time(),
            "updated_at": time.time(),
            "result": None,
            "error": None,
            "content_type": content_type
        }
        
        # Validate paths exist
        for path in media_paths:
            if not os.path.isfile(path):
                raise FileNotFoundError(f"Media file not found: {path}")
        
        # Store job information
        self.jobs[job_id] = job_data
        
        # Add to processing queue
        self.job_queue.put(job_id)
        
        # Update statistics
        with self.processing_lock:
            self.stats["total_jobs"] += 1
            if content_type == "reel":
                self.stats["video_processing_jobs"] += 1
            else:
                self.stats["image_processing_jobs"] += 1
        
        logger.info(f"Novo trabalho adicionado: {job_id} ({content_type})")
        return job_id
    
    def _process_queue(self):
        """Thread worker para processar trabalhos na fila"""
        while self.is_running:
            try:
                # Tentar obter um trabalho da fila
                try:
                    job_id = self.job_queue.get(block=True, timeout=1.0)
                except Empty:
                    # Fila vazia, continuar verificando
                    continue
                
                # Processar o trabalho
                try:
                    logger.info(f"Processando trabalho: {job_id}")
                    
                    # Obter dados do trabalho
                    job = self.jobs[job_id]
                    
                    # Atualizar status
                    self._update_job_status(job_id, "processing")
                    
                    # Importar módulos necessários aqui para evitar dependências circulares
                    from src.services.instagram_send import InstagramSend
                    
                    start_time = time.time()
                    result = None
                    error = None
                    
                    # Processar com base no tipo de conteúdo
                    try:
                        if job["content_type"] == "reel":
                            logger.info(f"Processando vídeo para Reels: {job['media_paths'][0]}")
                            # Priorizar configurações específicas para otimizar vídeos
                            share_to_feed = True
                            if "share_to_feed" in job["inputs"]:
                                share_to_feed = job["inputs"]["share_to_feed"]
                                
                            result = InstagramSend.send_reels(
                                job["media_paths"][0], 
                                job["caption"],
                                job["inputs"]
                            )
                        elif job["content_type"] == "carousel":
                            logger.info(f"Processando carrossel: {job['media_paths']}")
                            result = InstagramSend.send_carousel(
                                job["media_paths"], 
                                job["caption"],
                                job["inputs"]
                            )
                        else:
                            # Imagem padrão
                            result = InstagramSend.send_instagram(
                                job["media_paths"][0], 
                                job["caption"],
                                job["inputs"]
                            )
                            
                        if result:
                            self._update_job_status(job_id, "completed", result=result)
                            logger.info(f"Trabalho completado: {job_id}")
                            
                            with self.processing_lock:
                                self.stats["completed_jobs"] += 1
                        else:
                            raise Exception("Falha no processamento do conteúdo")
                            
                    except RateLimitExceeded as e:
                        error = str(e)
                        logger.warning(f"Rate limit excedido: {error}")
                        
                        # Marcar como falha de rate limit
                        self._update_job_status(job_id, "rate_limited", error=error)
                        
                        with self.processing_lock:
                            self.stats["rate_limited_posts"] += 1
                            self.stats["failed_jobs"] += 1
                            
                    except ContentPolicyViolation as e:
                        error = str(e)
                        logger.warning(f"Violação de política: {error}")
                        self._update_job_status(job_id, "policy_violation", error=error)
                        
                        with self.processing_lock:
                            self.stats["failed_jobs"] += 1
                            
                    except Exception as e:
                        error = str(e)
                        logger.error(f"Erro no processamento: {error}")
                        self._update_job_status(job_id, "failed", error=error)
                        
                        with self.processing_lock:
                            self.stats["failed_jobs"] += 1
                    
                    # Calcular tempo médio de processamento
                    processing_time = time.time() - start_time
                    with self.processing_lock:
                        if self.stats["completed_jobs"] > 0:
                            current_avg = self.stats["avg_processing_time"]
                            total_processed = self.stats["completed_jobs"]
                            new_avg = ((current_avg * (total_processed - 1)) + processing_time) / total_processed
                            self.stats["avg_processing_time"] = new_avg
                    
                    # Adicionar ao histórico
                    self._add_to_history(job_id)
                    
                    # Limpar mídia temporária após processamento 
                    for media_path in job["media_paths"]:
                        self._cleanup_media(media_path)
                    
                finally:
                    # Marcar como concluído na fila
                    self.job_queue.task_done()
                    
            except Exception as e:
                logger.exception(f"Erro no worker de processamento: {e}")
    
    def _update_job_status(self, job_id, status, result=None, error=None):
        """Atualiza o status de um trabalho"""
        if job_id in self.jobs:
            self.jobs[job_id]["status"] = status
            self.jobs[job_id]["updated_at"] = time.time()
            
            if result is not None:
                self.jobs[job_id]["result"] = result
                
            if error is not None:
                self.jobs[job_id]["error"] = error
    
    def _add_to_history(self, job_id):
        """Adiciona um trabalho ao histórico"""
        if job_id in self.jobs:
            # Copiar o trabalho para o histórico
            job_copy = self.jobs[job_id].copy()
            
            # Limitar tamanho do histórico
            MAX_HISTORY = 100
            if len(self.job_history) >= MAX_HISTORY:
                self.job_history.pop(0)  # Remover o mais antigo
                
            self.job_history.append(job_copy)
            
            # Limpar trabalhos antigos após um período
            self._cleanup_old_jobs()
    
    def _cleanup_old_jobs(self):
        """Limpa trabalhos antigos"""
        current_time = time.time()
        MAX_AGE = 24 * 60 * 60  # 24 horas
        
        jobs_to_remove = []
        for job_id, job in self.jobs.items():
            if current_time - job["updated_at"] > MAX_AGE:
                jobs_to_remove.append(job_id)
        
        for job_id in jobs_to_remove:
            if job_id in self.jobs:
                del self.jobs[job_id]
    
    def _cleanup_media(self, media_path):
        """Limpa arquivos de mídia temporários"""
        try:
            # Verificar se é um arquivo temporário que devemos remover
            if os.path.exists(media_path) and os.path.basename(media_path).startswith("temp-"):
                os.remove(media_path)
                logger.info(f"Arquivo de mídia temporário removido: {media_path}")
        except Exception as e:
            logger.warning(f"Erro ao limpar arquivo temporário {media_path}: {e}")
    
    def get_job_status(self, job_id):
        """
        Obtém o status de um trabalho
        
        Args:
            job_id (str): ID do trabalho
            
        Returns:
            dict: Informações do trabalho
        """
        if job_id in self.jobs:
            # Retornar cópia para evitar modificações
            return self.jobs[job_id].copy()
        
        # Verificar no histórico
        for job in self.job_history:
            if job["id"] == job_id:
                return job.copy()
                
        return {"error": "Job não encontrado"}
    
    def get_queue_stats(self):
        """
        Obtém estatísticas da fila
        
        Returns:
            dict: Estatísticas da fila
        """
        with self.processing_lock:
            stats = self.stats.copy()
            stats["queue_size"] = self.job_queue.qsize()
            stats["active_jobs"] = len(self.jobs)
            return stats
    
    def get_job_history(self, limit=10):
        """
        Obtém histórico de trabalhos
        
        Args:
            limit (int): Número máximo de registros
            
        Returns:
            list: Histórico de trabalhos
        """
        # Retornar histórico em ordem cronológica inversa
        return sorted(
            self.job_history,
            key=lambda x: x.get("updated_at", 0),
            reverse=True
        )[:limit]
    
    def clear_queue(self):
        """Limpa a fila atual de trabalhos"""
        while not self.job_queue.empty():
            try:
                self.job_queue.get(False)
                self.job_queue.task_done()
            except Empty:
                break
        
        logger.info("Fila limpa")

# Instância global para uso em toda a aplicação
post_queue = PostQueue()