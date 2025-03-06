# app.py

from src.services.message import Message
from src.utils.image_decode_save import ImageDecodeSaver
from src.services.instagram_send import InstagramSend
from flask import Flask, request, jsonify
import subprocess
import os
import time
import traceback

# Import our queue exceptions for error handling
from src.services.post_queue import RateLimitExceeded, ContentPolicyViolation

# Import monitoring server starter
from monitor import start_monitoring_server

app = Flask(__name__)

border_image = "moldura.png"

@app.route("/messages-upsert", methods=['POST'])
def webhook():
    try:
        data = request.get_json()  
        
        print(data)
                
        msg = Message(data)
        texto = msg.get_text()
        
        if msg.scope == Message.SCOPE_GROUP:    
            print(f"Grupo: {msg.group_id}")
            
            if str(msg.group_id) == "120363383673368986":
                 
                if msg.message_type == msg.TYPE_IMAGE:
                    image_path = ImageDecodeSaver.process(msg.image_base64)
                    
                    try:
                        # Queue the post instead of processing immediately
                        job_id = InstagramSend.queue_post(image_path, texto)
                        
                        print(f"Post queued successfully. Job ID: {job_id}")
                        
                        # Return a success response with the job ID
                        return jsonify({
                            "status": "em processamento", 
                            "job_id": job_id,
                            "message": "Post adicionado à fila e será processado em breve"
                        }), 202
                        
                    except ContentPolicyViolation as e:
                        print(f"Conteúdo viola diretrizes: {str(e)}")
                        return jsonify({"error": "Conteúdo viola diretrizes"}), 403
                        
                    except RateLimitExceeded as e:
                        print(f"Limite de requisições excedido: {str(e)}")
                        return jsonify({"error": "Limite de requisições excedido"}), 429
                        
                    except FileNotFoundError as e:
                        print(f"Arquivo não encontrado: {str(e)}")
                        return jsonify({"error": "Arquivo não encontrado"}), 404
                        
                    except Exception as e:
                        print(f"Erro durante o envio para o Instagram: {str(e)}")
                        traceback.print_exc()
                        return jsonify({"error": "Erro no processamento do post"}), 500
                        
                    finally:
                        # No need to cleanup image here - the queue system will handle it
                        pass
                    
    except Exception as e:
        print(f"Erro no processamento do webhook: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": "Erro no processamento da requisição"}), 500
        
    return jsonify({"status": "processed"}), 200

@app.route("/status", methods=['GET'])
def status():
    """Endpoint to check system status"""
    try:
        # Get queue statistics
        stats = InstagramSend.get_queue_stats()
        
        # Return status information
        return jsonify({
            "status": "online",
            "queue": stats,
            "recent_posts": InstagramSend.get_recent_posts(5)
        })
    except Exception as e:
        print(f"Erro ao obter status: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/job/<string:job_id>", methods=['GET'])
def check_job(job_id):
    """Endpoint to check the status of a specific job"""
    try:
        # Get job status
        job = InstagramSend.check_post_status(job_id)
        
        if job.get("status") == "not_found":
            return jsonify({"error": "Job não encontrado"}), 404
            
        return jsonify(job)
    except Exception as e:
        print(f"Erro ao verificar job: {str(e)}")
        return jsonify({"error": str(e)}), 500

def disable_firewall():
    # Check the current firewall state
    state_command = ["/usr/libexec/ApplicationFirewall/socketfilterfw", "--getglobalstate"]
    try:
        result = subprocess.run(state_command, check=True, capture_output=True, text=True)
        # Expecting output like "State = 1" when enabled or "State = 0" when disabled.
        if "0" in result.stdout:
            print("Firewall já está desabilitado.")
            return
    except subprocess.CalledProcessError as e:
        print(f"Falha ao verificar o estado do firewall: {e.stderr}")
    
    # Attempt to disable the firewall if it is enabled
    command = ["sudo", "/usr/libexec/ApplicationFirewall/socketfilterfw", "--setglobalstate", "off"]
    try:
        print("Tentando desabilitar o firewall do macOS para a porta do app...")
        subprocess.run(command, check=True, capture_output=True, text=True)
        print("Firewall desabilitado com sucesso.")
    except subprocess.CalledProcessError as e:
        print(f"Falha ao desabilitar o firewall: {e.stderr}")

# Install psutil if not already installed
def ensure_dependencies():
    try:
        import psutil
        print("Dependências já instaladas.")
    except ImportError:
        print("Instalando dependências necessárias...")
        subprocess.run(["pip", "install", "psutil"], check=True)
        print("Dependências instaladas.")

if __name__ == "__main__":
    # Ensure dependencies are installed
    ensure_dependencies()
    
    # Disable firewall
    disable_firewall()
    
    # Only start monitoring server on initial run, not on reloads
    if not os.environ.get('WERKZEUG_RUN_MAIN'):
        monitor_thread = start_monitoring_server()
        if monitor_thread:
            print("Sistema de monitoramento iniciado na porta 6002")
        else:
            print("Monitor já está rodando ou não foi possível iniciar")
    
    # Start the main app
    app.run(host="0.0.0.0", port=5001, debug=True)