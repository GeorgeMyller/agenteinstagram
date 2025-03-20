import logging
import time
import threading
from typing import Dict, Callable, Optional, List

# Configure logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('PostNotification')

class PostCompletionNotifier:
    """
    Classe responsável por monitorar os logs para notificar quando um post é completado.
    Envia notificações automáticas quando detecta "INFO:PostQueue:Trabalho completado".
    """
    
    def __init__(self, notification_callback: Callable[[str, Dict], None]):
        """
        Inicializa o notificador de conclusão de posts.
        
        Args:
            notification_callback: Função de callback que será chamada quando um post for completado.
                                  Deve aceitar job_id (str) e job_info (Dict) como parâmetros.
        """
        self.notification_callback = notification_callback
        self.is_running = False
        self.monitor_thread = None
        self.post_queue = None
        self.already_notified: List[str] = []
        
    def start_monitoring(self, post_queue_instance):
        """
        Inicia o monitoramento de posts concluídos.
        
        Args:
            post_queue_instance: Instância da classe PostQueue para consultar status dos jobs
        """
        if self.is_running:
            logger.info("Monitoramento já está ativo")
            return
            
        self.post_queue = post_queue_instance
        self.is_running = True
        self.monitor_thread = threading.Thread(target=self._monitor_completed_posts, daemon=True)
        self.monitor_thread.start()
        logger.info("Monitoramento de posts completados iniciado")
            
    def stop_monitoring(self):
        """Para o thread de monitoramento"""
        self.is_running = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5.0)
            logger.info("Monitoramento de posts completados encerrado")
            
    def _monitor_completed_posts(self):
        """Thread de monitoramento para detectar posts completados"""
        if not self.post_queue:
            logger.error("Post queue não foi configurada")
            return
            
        while self.is_running:
            try:
                # Consultar trabalhos no histórico recente
                job_history = self.post_queue.get_job_history(limit=20)
                
                for job in job_history:
                    job_id = job.get("id")
                    status = job.get("status")
                    
                    # Se o trabalho foi completado e ainda não notificamos
                    if status == "completed" and job_id not in self.already_notified:
                        # Obter detalhes completos do trabalho
                        job_detail = self.post_queue.get_job_status(job_id)
                        
                        # Chamar o callback com os detalhes
                        try:
                            self.notification_callback(job_id, job_detail)
                            logger.info(f"Notificação enviada para trabalho completado: {job_id}")
                        except Exception as e:
                            logger.error(f"Erro ao enviar notificação: {str(e)}")
                            
                        # Marcar como notificado
                        self.already_notified.append(job_id)
                        
                        # Limitar o tamanho da lista de notificados
                        if len(self.already_notified) > 100:
                            self.already_notified = self.already_notified[-100:]
                
                # Aguardar antes da próxima verificação
                time.sleep(5)
                
            except Exception as e:
                logger.exception(f"Erro no monitoramento de posts: {e}")
                time.sleep(10)  # Espera um pouco mais em caso de erro