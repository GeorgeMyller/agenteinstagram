from flask import Flask, jsonify, request, render_template
import threading
import time
import os
import json
import psutil
from datetime import datetime
from src.services.post_queue import post_queue, PostStatus
from src.instagram.instagram_post_service import InstagramPostService
from src.services.instagram_send import InstagramSend
import logging
import sqlite3
import glob

# Initialize the monitoring app on port 5001
app = Flask(__name__, template_folder="monitoring_templates")

# Configure logging
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Track server stats
SERVER_STATS = {
    "start_time": datetime.now().isoformat(),
    "requests_served": 0,
    "last_error": None,
    "api_rate_limits": {
        "count": 0,
        "window_start": time.time()
    },
    # Storage for carousel related data
    "carousel_debug": {
        "last_cleared": None,
        "clear_count": 0
    },
    # Storage for error queue data
    "error_queue": {
        "last_cleared": None,
        "clear_count": 0,
        "errors": []
    }
}

# Path to temporary carousel storage
CAROUSEL_TEMP_DIR = os.path.join("temp", "carousel")
os.makedirs(CAROUSEL_TEMP_DIR, exist_ok=True)

# Create templates directory if it doesn't exist
os.makedirs("monitoring_templates", exist_ok=True)

# Create a basic HTML template for the dashboard
with open("monitoring_templates/dashboard.html", "w") as f:
    f.write("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Instagram Posting Monitor</title>
        <meta http-equiv="refresh" content="30">
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            h1, h2 { color: #3b5998; }
            .stats-container { display: flex; flex-wrap: wrap; }
            .stat-box { 
                background-color: #f0f2f5; 
                border-radius: 5px; 
                padding: 20px; 
                margin: 10px;
                min-width: 200px;
                flex-grow: 1;
            }
            .stat-value { 
                font-size: 24px; 
                font-weight: bold; 
                margin: 10px 0;
            }
            .jobs-table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 20px;
            }
            .jobs-table th, .jobs-table td {
                padding: 12px;
                text-align: left;
                border-bottom: 1px solid #ddd;
            }
            .status-queued { color: #f9a602; }
            .status-processing { color: #1877f2; }
            .status-completed { color: #42b72a; }
            .status-failed { color: #ff0000; }
            .status-rate_limited { color: #ff8c00; }
            .status-content_violation { color: #8b0000; }
            .error-message {
                background-color: #ffdddd;
                border-left: 6px solid #f44336;
                padding: 10px;
                margin: 10px 0;
            }
        </style>
    </head>
    <body>
        <h1>Instagram Posting Monitor</h1>
        
        <div class="stats-container">
            <div class="stat-box">
                <h3>Queue Status</h3>
                <p>Pending Jobs: <span class="stat-value">{{stats.pending_jobs}}</span></p>
                <p>Active Jobs: <span class="stat-value">{{stats.active_jobs}}</span></p>
            </div>
            <div class="stat-box">
                <h3>Performance</h3>
                <p>Avg Processing Time: <span class="stat-value">{{stats.average_processing_time|round(1)}}s</span></p>
                <p>Success Rate: <span class="stat-value">{{success_rate|round(1)}}%</span></p>
            </div>
            <div class="stat-box">
                <h3>Results</h3>
                <p>Successful Posts: <span class="stat-value">{{stats.successful_posts}}</span></p>
                <p>Failed Posts: <span class="stat-value">{{stats.failed_posts}}</span></p>
            </div>
            <div class="stat-box">
                <h3>Issues</h3>
                <p>Rate Limited: <span class="stat-value">{{stats.rate_limited_posts}}</span></p>
                <p>Content Violations: <span class="stat-value">{{stats.content_violations}}</span></p>
            </div>
        </div>
        <div class="stat-box">
            <h3>System Resources</h3>
            <div class="stats-container">
                <div>
                    <p>CPU Usage: <span class="stat-value">{{system.cpu_percent}}%</span></p>
                    <p>Memory Usage: <span class="stat-value">{{system.memory_percent|round(1)}}%</span></p>
                </div>
                <div>
                    <p>Disk Usage: <span class="stat-value">{{system.disk_percent|round(1)}}%</span></p>
                    <p>Uptime: <span class="stat-value">{{system.uptime}}</span></p>
                </div>
            </div>
        </div>
        
        <h2>Recent Jobs</h2>
        <table class="jobs-table">
            <thead>
                <tr>
                    <th>Job ID</th>
                    <th>Status</th>
                    <th>Caption</th>
                    <th>Created</th>
                    <th>Completed</th>
                    <th>Error</th>
                </tr>
            </thead>
            <tbody>
                {% for job in jobs %}
                <tr>
                    <td>{{job.id[:8]}}...</td>
                    <td class="status-{{job.status}}">{{job.status}}</td>
                    <td>{{job.caption|truncate(30)}}</td>
                    <td>{{job.created_at|replace("T", " ")|truncate(19, True, "")}}</td>
                    <td>{{job.completed_at|replace("T", " ")|truncate(19, True, "") if job.completed_at else "-"}}</td>
                    <td>{{job.error|truncate(50) if job.error else "-"}}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        
        <footer style="margin-top: 30px; text-align: center; color: #666;">
            <p>Instagram Posting Monitoring System | Last updated: {{current_time}}</p>
        </footer>
    </body>
    </html>
    """)

# Get system stats
def get_system_stats():
    try:
        process = psutil.Process(os.getpid())
        
        # Calculate uptime
        uptime_seconds = time.time() - process.create_time()
        days, remainder = divmod(uptime_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if days > 0:
            uptime = f"{int(days)}d {int(hours)}h {int(minutes)}m"
        elif hours > 0:
            uptime = f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
        else:
            uptime = f"{int(minutes)}m {int(seconds)}s"
            
        # Get disk usage
        disk = psutil.disk_usage('/')
        
        return {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": process.memory_percent(),
            "disk_percent": disk.percent,
            "uptime": uptime,
            "threads": threading.active_count()
        }
    except Exception as e:
        return {
            "error": str(e),
            "cpu_percent": 0,
            "memory_percent": 0,
            "disk_percent": 0,
            "uptime": "unknown",
            "threads": threading.active_count()
        }

@app.route('/')
def dashboard():
    SERVER_STATS["requests_served"] += 1
    
    # Get queue stats
    stats = post_queue.get_queue_stats()
    
    # Get recent jobs
    jobs = post_queue.get_job_history(20)
    
    # Calculate success rate
    total_completed = stats['successful_posts'] + stats['failed_posts']
    success_rate = 0
    if total_completed > 0:
        success_rate = (stats['successful_posts'] / total_completed) * 100
    
    # Get system stats
    system = get_system_stats()
    
    return render_template(
        'dashboard.html', 
        stats=stats, 
        jobs=jobs, 
        system=system, 
        success_rate=success_rate,
        current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

@app.route('/api/health')
def health_check():
    return jsonify({
        "status": "ok",
        "uptime": time.time() - float(datetime.fromisoformat(SERVER_STATS["start_time"]).timestamp()),
        "requests_served": SERVER_STATS["requests_served"]
    })

@app.route('/api/stats')
def get_stats():
    SERVER_STATS["requests_served"] += 1
    
    stats = post_queue.get_queue_stats()
    system = get_system_stats()
    
    return jsonify({
        "queue": stats,
        "system": system,
        "server": {
            "start_time": SERVER_STATS["start_time"],
            "requests_served": SERVER_STATS["requests_served"],
            "last_error": SERVER_STATS["last_error"]
        }
    })

@app.route('/api/jobs')
def list_jobs():
    SERVER_STATS["requests_served"] += 1
    
    limit = request.args.get('limit', default=10, type=int)
    status = request.args.get('status', default=None, type=str)
    
    # Get recent jobs
    jobs = post_queue.get_job_history(limit=50)  # Get more than we need for filtering
    
    # Filter by status if specified
    if status:
        jobs = [job for job in jobs if job.get('status') == status]
    
    # Limit results
    jobs = jobs[:limit]
    
    return jsonify({
        "jobs": jobs,
        "count": len(jobs),
        "total_jobs": post_queue.get_queue_stats()['total_posts']
    })

@app.route('/api/jobs/<string:job_id>')
def get_job(job_id):
    SERVER_STATS["requests_served"] += 1
    
    job = post_queue.get_job_status(job_id)
    
    if job.get('status') == 'not_found':
        return jsonify({"error": "Job not found"}), 404
        
    return jsonify(job)

@app.route('/api/test', methods=['POST'])
def test_post():
    SERVER_STATS["requests_served"] += 1
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing request body"}), 400
        
    # Extract parameters with defaults
    image_url = data.get('image_url', 'https://i.imgur.com/h1CzPBh.jpg')
    caption = data.get('caption', 'Test post from monitoring API')
    
    try:
        # Create test service
        service = InstagramPostService()
        
        # Don't actually post to Instagram in test mode
        # Just validate the parameters
        result = {
            "test_id": "test_" + str(time.time()),
            "image_url": image_url,
            "caption": caption,
            "validation": "passed",
            "timestamp": datetime.now().isoformat()
        }
        
        return jsonify(result)
    except Exception as e:
        SERVER_STATS["last_error"] = str(e)
        return jsonify({"error": str(e), "validation": "failed"}), 400

@app.route('/api/queue', methods=['POST'])
def queue_post():
    SERVER_STATS["requests_served"] += 1
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing request body"}), 400
        
    # Extract required parameters
    image_path = data.get('image_path')
    caption = data.get('caption')
    inputs = data.get('inputs')
    
    if not image_path:
        return jsonify({"error": "Missing image_path parameter"}), 400
        
    try:
        # Queue the post
        job_id = InstagramSend.queue_post(image_path, caption, inputs)
        
        # Return the job details
        job = post_queue.get_job_status(job_id)
        
        return jsonify({
            "job_id": job_id,
            "status": job.get('status'),
            "created_at": job.get('created_at'),
            "message": "Post queued successfully"
        }), 202
    except FileNotFoundError as e:
        SERVER_STATS["last_error"] = str(e)
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        SERVER_STATS["last_error"] = str(e)
        return jsonify({"error": str(e)}), 500

# New debug endpoints for troubleshooting Instagram carousel issues

@app.route('/debug/carousel/clear', methods=['POST'])
def clear_carousel_state():
    """
    Clear carousel-related temporary files and state
    As referenced in docs/troubleshooting/common.md
    """
    try:
        # Clear any temporary carousel files
        count = 0
        
        # Clear temp files from carousel directory
        for file_path in glob.glob(os.path.join(CAROUSEL_TEMP_DIR, "*")):
            try:
                os.remove(file_path)
                count += 1
            except Exception as e:
                logger.error(f"Failed to delete file {file_path}: {str(e)}")
        
        # Try to clear any cached carousel data in Instagram services
        try:
            # Get an instance of InstagramPostService to clear its container cache
            service = InstagramPostService()
            if hasattr(service, 'container_cache'):
                # Filter and clear only carousel entries from cache
                carousel_keys = [key for key in service.container_cache.keys() 
                                if 'carousel' in key or 'children' in str(service.container_cache[key])]
                for key in carousel_keys:
                    service.container_cache.pop(key, None)
                count += len(carousel_keys)
        except Exception as e:
            logger.error(f"Failed to clear InstagramPostService container_cache: {str(e)}")
        
        # Update stats
        SERVER_STATS["carousel_debug"]["last_cleared"] = datetime.now().isoformat()
        SERVER_STATS["carousel_debug"]["clear_count"] += 1
        
        return jsonify({
            "success": True,
            "message": f"Carousel state cleared - removed {count} items",
            "timestamp": SERVER_STATS["carousel_debug"]["last_cleared"]
        })
    except Exception as e:
        SERVER_STATS["last_error"] = str(e)
        logger.error(f"Error clearing carousel state: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Failed to clear carousel state"
        }), 500

@app.route('/debug/error-queue/clear', methods=['POST'])
def clear_error_queue():
    """
    Clear any pending errors in the queue
    As referenced in docs/troubleshooting/common.md
    """
    try:
        # Clear error queue
        count = len(SERVER_STATS["error_queue"]["errors"])
        SERVER_STATS["error_queue"]["errors"] = []
        
        # Attempt to reset error status on failed carousel jobs
        try:
            # Get active jobs
            jobs = post_queue.get_job_history(limit=50)
            
            # Filter for failed carousel jobs
            carousel_jobs = [job for job in jobs 
                           if job.get('status') == 'failed' and 
                           job.get('content_type') == 'carousel']
            
            # Reset job status if possible
            reset_count = 0
            for job in carousel_jobs:
                try:
                    job_id = job.get('id')
                    if job_id:
                        post_queue.update_job_status(job_id, PostStatus.PENDING, 
                                                    error_message=None)
                        reset_count += 1
                except Exception as job_e:
                    logger.error(f"Failed to reset job {job.get('id')}: {str(job_e)}")
            
            # Add reset count to the total
            count += reset_count
        except Exception as e:
            logger.error(f"Failed to reset failed carousel jobs: {str(e)}")
        
        # Update stats
        SERVER_STATS["error_queue"]["last_cleared"] = datetime.now().isoformat()
        SERVER_STATS["error_queue"]["clear_count"] += 1
        
        return jsonify({
            "success": True,
            "message": f"Error queue cleared - {count} errors removed or jobs reset",
            "timestamp": SERVER_STATS["error_queue"]["last_cleared"]
        })
    except Exception as e:
        SERVER_STATS["last_error"] = str(e)
        logger.error(f"Error clearing error queue: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Failed to clear error queue"
        }), 500

@app.route('/debug/carousel/status', methods=['GET'])
def get_carousel_status():
    """
    Get status of carousel processing, including pending uploads
    """
    try:
        # Check for carousel files in temporary directory
        temp_files = glob.glob(os.path.join(CAROUSEL_TEMP_DIR, "*"))
        
        # Get active carousel jobs
        jobs = post_queue.get_job_history(limit=50)
        carousel_jobs = [job for job in jobs 
                       if (job.get('content_type') == 'carousel' and 
                           job.get('status') in ['pending', 'processing'])]
        
        # Get service container cache information if available
        container_cache_info = []
        try:
            service = InstagramPostService()
            if hasattr(service, 'container_cache'):
                for key, value in service.container_cache.items():
                    if 'carousel' in key or 'children' in str(value):
                        cache_item = {
                            "key": key,
                            "id": value.get('id'),
                            "timestamp": datetime.fromtimestamp(value.get('timestamp')).isoformat() 
                                        if 'timestamp' in value else None
                        }
                        container_cache_info.append(cache_item)
        except Exception as e:
            logger.error(f"Failed to get container cache info: {str(e)}")
        
        return jsonify({
            "success": True,
            "temp_files": {
                "count": len(temp_files),
                "files": [os.path.basename(f) for f in temp_files]
            },
            "active_jobs": {
                "count": len(carousel_jobs),
                "jobs": carousel_jobs
            },
            "container_cache": {
                "count": len(container_cache_info),
                "items": container_cache_info
            },
            "last_cleared": SERVER_STATS["carousel_debug"]["last_cleared"],
            "clear_count": SERVER_STATS["carousel_debug"]["clear_count"]
        })
    except Exception as e:
        SERVER_STATS["last_error"] = str(e)
        logger.error(f"Error getting carousel status: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Failed to get carousel status"
        }), 500

@app.route('/debug/error-queue/status', methods=['GET'])
def get_error_queue_status():
    """
    Get status of error queue
    """
    try:
        # Get all failed jobs
        jobs = post_queue.get_job_history(limit=100)
        failed_jobs = [job for job in jobs if job.get('status') == 'failed']
        failed_carousel_jobs = [job for job in failed_jobs if job.get('content_type') == 'carousel']
        failed_image_jobs = [job for job in failed_jobs if job.get('content_type') == 'image']
        failed_reel_jobs = [job for job in failed_jobs if job.get('content_type') == 'reel']
        
        # Group errors by type
        error_types = {}
        for job in failed_jobs:
            error = job.get('error')
            if error:
                error_code = None
                # Try to extract error code if available
                if "Code:" in error:
                    try:
                        code_part = error.split("Code:")[1].strip()
                        error_code = int(code_part.split()[0])
                    except:
                        pass
                
                # Use error code as key if available, otherwise use first 30 chars
                key = str(error_code) if error_code else error[:30]
                if key in error_types:
                    error_types[key]['count'] += 1
                else:
                    error_types[key] = {
                        'count': 1,
                        'message': error,
                        'code': error_code
                    }
        
        return jsonify({
            "success": True,
            "failed_jobs": {
                "total": len(failed_jobs),
                "carousel": len(failed_carousel_jobs),
                "image": len(failed_image_jobs),
                "reel": len(failed_reel_jobs)
            },
            "error_types": list(error_types.values()),
            "current_errors": SERVER_STATS["error_queue"]["errors"],
            "last_cleared": SERVER_STATS["error_queue"]["last_cleared"],
            "clear_count": SERVER_STATS["error_queue"]["clear_count"]
        })
    except Exception as e:
        SERVER_STATS["last_error"] = str(e)
        logger.error(f"Error getting error queue status: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Failed to get error queue status"
        }), 500

@app.route('/debug/log-error', methods=['POST'])
def log_instagram_error():
    """
    Log an Instagram API error for later analysis
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing request body"}), 400
        
        # Extract error details
        error = {
            "timestamp": datetime.now().isoformat(),
            "code": data.get("code"),
            "subcode": data.get("subcode"),
            "message": data.get("message"),
            "type": data.get("type"),
            "fb_trace_id": data.get("fb_trace_id"),
            "context": data.get("context")
        }
        
        # Add to error list, maintain max size of 100
        SERVER_STATS["error_queue"]["errors"].append(error)
        if len(SERVER_STATS["error_queue"]["errors"]) > 100:
            SERVER_STATS["error_queue"]["errors"] = SERVER_STATS["error_queue"]["errors"][-100:]
        
        return jsonify({
            "success": True,
            "message": "Error logged successfully",
            "error_id": len(SERVER_STATS["error_queue"]["errors"]) - 1
        })
    except Exception as e:
        SERVER_STATS["last_error"] = str(e)
        logger.error(f"Error logging Instagram error: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Failed to log error"
        }), 500

@app.errorhandler(Exception)
def handle_error(e):
    SERVER_STATS["last_error"] = str(e)
    logger.error(f"Unhandled exception: {str(e)}")
    return jsonify({"error": str(e)}), 500

def start_monitoring_server():
    """Start the monitoring server in a separate thread"""
    from werkzeug.serving import make_server
    import socket
    port = 5001  # Changed to match documentation
    retries = 3
    for _ in range(retries):
        try:
            # Create a werkzeug server
            srv = make_server('0.0.0.0', port, app)
            
            # Start server in a thread
            thread = threading.Thread(target=srv.serve_forever)
            thread.daemon = True
            thread.start()
            
            logger.info(f"Monitoring server started on http://0.0.0.0:{port}")
            return thread
        except socket.error as e:
            if "Address already in use" in str(e):
                logger.warning(f"Port {port} is already in use, monitoring server may already be running")
                return None
            port += 1
    
    logger.error("Failed to start monitoring server after several attempts")
    return None

if __name__ == '__main__':
    # Start server directly when run as script
    app.run(host='0.0.0.0', port=5001, debug=False)  # Changed to match documentation

import streamlit as st
import requests
import time
import pandas as pd
import plotly.express as px
import matplotlib.pyplot as plt
import datetime
import os
from src.services.instagram_send import InstagramSend

# Configuração da página
st.set_page_config(
    page_title="Agent Social Media - Monitoramento",
    page_icon="📊",
    layout="wide"
)

# Título
st.title('📊 Monitoramento do Agent Social Media')

# Definir URL base da API
API_BASE_URL = os.environ.get('API_BASE_URL', 'http://localhost:3000')

# Sidebar para configurações
st.sidebar.header('Configurações')
refresh_interval = st.sidebar.slider('Intervalo de atualização (segundos)', 5, 60, 15)
auto_refresh = st.sidebar.checkbox('Atualização automática', value=True)

# Função para obter dados da API
def get_api_data(endpoint):
    try:
        response = requests.get(f"{API_BASE_URL}/{endpoint}")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Erro ao obter dados da API: {str(e)}")
        return None

# Função para formatar timestamp
def format_timestamp(timestamp):
    if isinstance(timestamp, (int, float)):
        return datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    return "N/A"

# Criar tabs para diferentes visualizações
tab1, tab2, tab3 = st.tabs(["Dashboard Geral", "Monitoramento de Reels", "Histórico de Jobs"])

# Tab 1: Dashboard Geral
with tab1:
    st.header("Estatísticas Gerais")
    
    # Obter estatísticas
    stats = InstagramSend.get_queue_stats()
    
    # Criar colunas para métricas principais
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total de Jobs", stats["total_jobs"])
        st.metric("Jobs Completados", stats["completed_jobs"])
        st.metric("Jobs Falhos", stats["failed_jobs"])
    
    with col2:
        st.metric("Posts de Imagens", stats["image_processing_jobs"])
        st.metric("Posts de Vídeos", stats["video_processing_jobs"])
        taxa_sucesso = 0
        if stats["total_jobs"] > 0:
            taxa_sucesso = round((stats["completed_jobs"] / stats["total_jobs"]) * 100, 2)
        st.metric("Taxa de Sucesso", f"{taxa_sucesso}%")
    
    with col3:
        st.metric("Jobs na Fila", stats["queue_size"])
        st.metric("Rate Limited", stats["rate_limited_posts"])
        st.metric("Tempo Médio", f"{round(stats['avg_processing_time'], 2)}s")
    
    # Gráfico de pizza: distribuição por tipo de conteúdo
    st.subheader("Distribuição por Tipo de Conteúdo")
    
    tipos_data = {
        'Tipo': ['Imagens', 'Vídeos'],
        'Quantidade': [stats["image_processing_jobs"], stats["video_processing_jobs"]]
    }
    
    tipos_df = pd.DataFrame(tipos_data)
    if sum(tipos_data['Quantidade']) > 0:  # Verificar se há dados para mostrar
        fig = px.pie(tipos_df, values='Quantidade', names='Tipo', 
                     title='Distribuição de Posts por Tipo')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sem dados suficientes para gerar o gráfico")

# Tab 2: Monitoramento de Reels
with tab2:
    st.header("Monitoramento de Reels")
    
    # Obter histórico de jobs
    history = InstagramSend.get_recent_posts(20)  # Pegar mais jobs para filtrar apenas vídeos
    
    # Filtrar apenas vídeos/reels
    reels_jobs = [job for job in history if job.get('content_type') == 'reel']
    
    if not reels_jobs:
        st.info("Nenhum job de Reels encontrado no histórico recente.")
    else:
        # Criar DataFrame com dados relevantes
        reels_data = []
        for job in reels_jobs:
            status = job.get('status', 'unknown')
            created_at = format_timestamp(job.get('created_at'))
            updated_at = format_timestamp(job.get('updated_at'))
            
            # Calcular duração do processamento
            processing_time = "N/A"
            if job.get('created_at') and job.get('updated_at') and job.get('status') in ['completed', 'failed']:
                duration = job.get('updated_at') - job.get('created_at')
                processing_time = f"{round(duration, 2)}s"
            
            # Informações adicionais
            result = job.get('result', {})
            permalink = result.get('permalink', 'N/A') if result else 'N/A'
            post_id = result.get('id', 'N/A') if result else 'N/A'
            
            # Extrair path do vídeo para análise
            media_path = job.get('media_path', 'N/A')
            media_filename = os.path.basename(media_path) if media_path != 'N/A' else 'N/A'
            
            reels_data.append({
                'Job ID': job.get('id', 'N/A')[:8] + "...",
                'Status': status,
                'Criado': created_at,
                'Atualizado': updated_at,
                'Tempo Processamento': processing_time,
                'Post ID': post_id,
                'Permalink': permalink,
                'Arquivo': media_filename
            })
        
        # Converter para DataFrame
        reels_df = pd.DataFrame(reels_data)
        
        # Mostrar tabela de reels
        st.dataframe(reels_df, use_container_width=True)
        
        # Mostrar gráfico de status dos reels
        st.subheader("Status dos Reels")
        status_counts = {}
        for job in reels_jobs:
            status = job.get('status', 'unknown')
            status_counts[status] = status_counts.get(status, 0) + 1
        
        status_data = {
            'Status': list(status_counts.keys()),
            'Quantidade': list(status_counts.values())
        }
        
        status_df = pd.DataFrame(status_data)
        
        colors = {
            'completed': '#2ecc71',
            'failed': '#e74c3c',
            'processing': '#3498db',
            'pending': '#95a5a6',
            'rate_limited': '#f39c12',
            'unknown': '#7f8c8d'
        }
        
        fig = px.bar(status_df, x='Status', y='Quantidade', 
                    title='Distribuição dos Status de Reels',
                    color='Status',
                    color_discrete_map=colors)
        
        st.plotly_chart(fig, use_container_width=True)

# Tab 3: Histórico de Jobs
with tab3:
    st.header("Histórico de Jobs")
    
    # Filtros
    col1, col2 = st.columns(2)
    with col1:
        status_filter = st.multiselect(
            'Filtrar por Status',
            ['completed', 'failed', 'processing', 'pending', 'rate_limited'],
            default=['completed', 'failed', 'processing', 'pending', 'rate_limited']
        )
    
    with col2:
        tipo_filter = st.multiselect(
            'Filtrar por Tipo',
            ['image', 'reel'],
            default=['image', 'reel']
        )
    
    # Obter histórico
    history = InstagramSend.get_recent_posts(50)  # Aumentar limite para mostrar mais jobs
    
    # Aplicar filtros
    filtered_jobs = [
        job for job in history 
        if job.get('status') in status_filter and job.get('content_type') in tipo_filter
    ]
    
    if not filtered_jobs:
        st.info("Nenhum job encontrado com os filtros aplicados.")
    else:
        # Preparar dados para tabela
        job_data = []
        for job in filtered_jobs:
            job_id = job.get('id', 'N/A')
            status = job.get('status', 'unknown')
            content_type = job.get('content_type', 'unknown')
            created_at = format_timestamp(job.get('created_at'))
            
            # Verificar resultado
            result = job.get('result', {})
            post_id = result.get('id', 'N/A') if result else 'N/A'
            
            # Verificar erro
            error = job.get('error', 'N/A')
            
            job_data.append({
                'Job ID': job_id[:8] + "...",
                'Tipo': content_type.upper(),
                'Status': status,
                'Criado em': created_at,
                'Post ID': post_id,
                'Erro': error if error != 'N/A' else ''
            })
        
        # Criar DataFrame
        jobs_df = pd.DataFrame(job_data)
        
        # Mostrar tabela com todos os jobs filtrados
        st.dataframe(jobs_df, use_container_width=True)
        
        # Gráfico de linha do tempo
        st.subheader("Timeline de Jobs")
        
        # Preparar dados de timeline (últimos 20 jobs em ordem cronológica)
        timeline_data = []
        for idx, job in enumerate(filtered_jobs[:20]):
            timeline_data.append({
                'Índice': idx,
                'Timestamp': job.get('created_at', 0),
                'Status': job.get('status', 'unknown'),
                'Tipo': job.get('content_type', 'unknown').upper()
            })
        
        # Ordenar por timestamp
        timeline_df = pd.DataFrame(timeline_data)
        timeline_df = timeline_df.sort_values('Timestamp')
        
        # Converter timestamp para datetime formatado
        timeline_df['Data/Hora'] = timeline_df['Timestamp'].apply(format_timestamp)
        
        # Plotar gráfico de linha do tempo
        fig = px.scatter(timeline_df, x='Data/Hora', y='Tipo', color='Status',
                        title='Histórico de Jobs ao Longo do Tempo',
                        color_discrete_map={
                            'completed': '#2ecc71',
                            'failed': '#e74c3c',
                            'processing': '#3498db',
                            'pending': '#95a5a6',
                            'rate_limited': '#f39c12'
                        })
        
        st.plotly_chart(fig, use_container_width=True)

# Auto refresh
if auto_refresh:
    time.sleep(refresh_interval)
    st.rerun()