from flask import Flask, jsonify, render_template
import threading
import time
import os
import psutil
from datetime import datetime
import logging
import json

# Configuração básica de logging
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Inicialize o app Flask com o diretório de templates
app = Flask(__name__, template_folder="monitoring_templates")

# Cria o diretório de templates e o dashboard se ainda não existirem
TEMPLATE_DIR = "monitoring_templates"
os.makedirs(TEMPLATE_DIR, exist_ok=True)
dashboard_template_path = os.path.join(TEMPLATE_DIR, "dashboard.html")
if not os.path.exists(dashboard_template_path):
    with open(dashboard_template_path, "w", encoding="utf-8") as f:
        f.write("""<!DOCTYPE html>
<html>
<head>
    <title>Instagram Posting Monitor</title>
    <meta http-equiv="refresh" content="30">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
    </style>
</head>
<body>
    <h1>Instagram Posting Monitor</h1>
    <p>Current Time: {{ current_time }}</p>
    <p>Server Uptime: {{ uptime }}</p>
</body>
</html>""")

# Hora de início para cálculo de uptime
SERVER_START_TIME = datetime.now()

def get_system_stats():
    """Coleta estatísticas simples do sistema."""
    try:
        process = psutil.Process(os.getpid())
        uptime_seconds = time.time() - process.create_time()
        days, remainder = divmod(uptime_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{int(days)}d {int(hours)}h {int(minutes)}m {int(seconds)}s"

        # Load Instagram API stats
        api_stats = {'successful_posts': 0, 'failed_posts': 0, 'rate_limited_posts': 0}
        if os.path.exists('api_state.json'):
            try:
                with open('api_state.json', 'r') as f:
                    state = json.load(f)
                    api_stats = state.get('stats', api_stats)
            except Exception as e:
                logger.error(f"Error loading API stats: {e}")

        return {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": process.memory_percent(),
            "uptime": uptime_str,
            "successful_posts": api_stats.get('successful_posts', 0),
            "failed_posts": api_stats.get('failed_posts', 0),
            "rate_limited_posts": api_stats.get('rate_limited_posts', 0)
        }
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas do sistema: {e}")
        return {
            "cpu_percent": 0, 
            "memory_percent": 0, 
            "uptime": "unknown",
            "successful_posts": 0,
            "failed_posts": 0,
            "rate_limited_posts": 0
        }

@app.route("/")
def dashboard():
    """Rota principal que renderiza o dashboard."""
    system_stats = get_system_stats()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return render_template(
        "dashboard.html", 
        current_time=current_time, 
        uptime=system_stats["uptime"],
        system=system_stats
    )

@app.route("/api/health")
def health_check():
    """Endpoint de health que retorna status, uptime, etc."""
    uptime_seconds = time.time() - SERVER_START_TIME.timestamp()
    stats = get_system_stats()
    return jsonify({
        "status": "ok",
        "uptime": uptime_seconds,
        "stats": stats
    })

def start_monitoring_server():
    """Inicia o servidor de monitoramento em uma thread separada na porta 5501."""
    from werkzeug.serving import make_server
    port = 5501
    try:
        server = make_server("0.0.0.0", port, app)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        logger.info(f"Servidor de monitoramento iniciado em http://0.0.0.0:{port}")
        return thread
    except Exception as e:
        logger.error(f"Falha ao iniciar o servidor de monitoramento: {e}")
        return None

if __name__ == "__main__":
    # Roda o servidor diretamente quando executado como script
    app.run(host="0.0.0.0", port=5501, debug=False)