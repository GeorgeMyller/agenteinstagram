# Este arquivo implementa um servidor de monitoramento para acompanhar o status da aplicação

# Importando bibliotecas necessárias
from flask import Flask, jsonify, render_template  # Para criar o servidor web e manipular requisições
import threading  # Para executar tarefas em paralelo
import time  # Para manipulação de tempo
import os  # Para operações com sistema de arquivos
import psutil  # Para obter estatísticas do sistema
from datetime import datetime  # Para manipulação de datas e horários
import logging  # Para registrar logs
import json  # Para trabalhar com dados em formato JSON
from src.instagram.instagram_facade import InstagramFacade  # Para interagir com o Instagram

# Configuração básica de logging
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Inicialize o app Flask com o diretório de templates
app = Flask(__name__, template_folder="monitoring_templates")

# Inicializar o facade do Instagram
instagram = InstagramFacade(
    access_token=os.getenv('INSTAGRAM_API_KEY'),
    ig_user_id=os.getenv('INSTAGRAM_ACCOUNT_ID')  # Changed from INSTAGRAM_USER_ID to match the service
)

# Variáveis globais para armazenar estatísticas
system_stats = {
    "start_time": datetime.now(),
    "successful_posts": 0,
    "failed_posts": 0,
    "rate_limited_posts": 0,
    "last_error": None,
    "last_success": None
}

def update_system_stats():
    """Atualiza as estatísticas do sistema periodicamente"""
    while True:
        try:
            status = instagram.get_account_status()
            system_stats.update({
                "api_status": status.get('account_status', 'unknown'),
                "api_usage": status.get('usage_rate', 0),
                "rate_limit_remaining": status.get('calls_remaining', 'N/A'),
                "rate_limit_reset": status.get('minutes_until_reset', 0)
            })
        except Exception as e:
            logger.error(f"Error updating system stats: {e}")
            system_stats.update({
                "api_status": "error",
                "last_error": str(e)
            })
        time.sleep(300)  # Atualiza a cada 5 minutos

@app.route('/')
def dashboard():
    """Rota principal que renderiza o dashboard"""
    return render_template('dashboard.html', system=system_stats)

@app.route('/api/stats')
def get_stats():
    """Endpoint para obter estatísticas atuais via API"""
    return jsonify(system_stats)

@app.route('/debug/carousel/clear', methods=['POST'])
def clear_carousel():
    """Limpa o cache e estado do carrossel"""
    try:
        # Aqui você pode adicionar lógica para limpar arquivos temporários
        # ou qualquer outro estado relacionado aos carrosséis
        return jsonify({"status": "success", "message": "Carousel state cleared"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

def start_monitoring_server(port=5002):
    """
    Starts the monitoring server on the specified port
    Args:
        port (int): Port number to run the server on. Defaults to 5002.
    """
    # Inicia a thread de atualização de estatísticas
    stats_thread = threading.Thread(target=update_system_stats, daemon=True)
    stats_thread.start()
    
    # Inicia o servidor web
    app.run(port=port)

if __name__ == '__main__':
    start_monitoring_server()