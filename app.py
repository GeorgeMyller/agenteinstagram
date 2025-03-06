from src.services.message import Message
from src.utils.image_decode_save import ImageDecodeSaver
from src.services.instagram_send import InstagramSend
from src.instagram.instagram_reels_publisher import ReelsPublisher  # Importe a classe ReelsPublisher
from flask import Flask, request, jsonify
import subprocess
import os
import time
import traceback
import threading

from src.utils.paths import Paths  # Add this import

# Import our queue exceptions for error handling
from src.services.post_queue import RateLimitExceeded, ContentPolicyViolation

# Import monitoring server starter
from monitor import start_monitoring_server

from src.instagram.filter import FilterImage
from src.services.send import sender #Para enviar mensagens de volta

app = Flask(__name__)

border_image = "moldura.png"

# Variáveis de estado para o modo carrossel
is_carousel_mode = False
carousel_images = []
carousel_start_time = 0
CAROUSEL_TIMEOUT = 300  # 5 minutos em segundos
MAX_CAROUSEL_IMAGES = 10


@app.route("/messages-upsert", methods=['POST'])
def webhook():
    global is_carousel_mode, carousel_images, carousel_start_time  # Acesso às variáveis globais

    try:
        data = request.get_json()

        msg = Message(data)
        texto = msg.get_text()
        
        #Verificar se o número é de um grupo valido.
        if msg.scope == Message.SCOPE_GROUP:
            print(f"Grupo: {msg.group_id}")
            if str(msg.group_id) != "120363383673368986":  #Use != para a comparação, e a string correta.
                return jsonify({"status": "processed, but ignored"}), 200 #Retorna 200 para o webhook não reenviar.
        
        # Lógica do Modo Carrossel
        if texto and texto.lower() == "carrossel":
            is_carousel_mode = True
            carousel_images = []
            carousel_start_time = time.time()
            return jsonify({"status": "Modo carrossel ativado"}), 200

        if is_carousel_mode:
            if msg.message_type == msg.TYPE_IMAGE:
                image_path = ImageDecodeSaver.process(msg.image_base64)
                carousel_images.append(image_path)
                if len(carousel_images) >= MAX_CAROUSEL_IMAGES:
                    # Atingiu o limite máximo de imagens, processar o carrossel
                    try:
                        #TODO: Chamar função para processar o carrossel (ainda a ser criada em InstagramSend)
                        # job_id = InstagramSend.queue_carousel(carousel_images, ...) 
                        #sender.send_text(number=msg.remote_jid, msg=f"Carrossel enfileirado com sucesso! ID do trabalho: {job_id}")
                        pass #Por agora
                    except Exception as e:
                        print(f"Erro ao enfileirar carrossel: {e}")
                        sender.send_text(number=msg.remote_jid, msg=f"Erro ao enfileirar carrossel: {e}")
                        return jsonify({"status": "error", "message": "Erro ao enfileirar carrossel"}), 500
                    finally:
                        is_carousel_mode = False  # Resetar o modo carrossel
                        carousel_images = []
                    
                    return jsonify({"status": "Imagem adicionada ao carrossel, processando..."}), 200
                else:
                    return jsonify({"status": f"Imagem adicionada ao carrossel. {len(carousel_images)}/{MAX_CAROUSEL_IMAGES}"}), 200

            elif time.time() - carousel_start_time > CAROUSEL_TIMEOUT:
                # Timeout, sair do modo carrossel
                is_carousel_mode = False
                carousel_images = []
                sender.send_text(number=msg.remote_jid, msg="Timeout do carrossel. Envie 'carrossel' novamente para iniciar.")
                return jsonify({"status": "Timeout do carrossel"}), 200

            #Ignorar outras mensagens, se estiver em modo carrossel
            return jsonify({"status": "processed (carousel mode)"}), 200

        # Processamento de Imagem Única
        if msg.message_type == msg.TYPE_IMAGE:
            image_path = ImageDecodeSaver.process(msg.image_base64)
            caption = msg.image_caption if msg.image_caption else ""  # Usar a legenda da imagem, se houver

            try:
                job_id = InstagramSend.queue_post(image_path, caption)
                sender.send_text(number=msg.remote_jid, msg=f"Postagem de imagem enfileirada com sucesso! ID do trabalho: {job_id}")
                return jsonify({"status": "enqueued", "job_id": job_id}), 202
            except ContentPolicyViolation as e:
                sender.send_text(number=msg.remote_jid, msg=f"Conteúdo viola diretrizes: {str(e)}")
                return jsonify({"error": "Conteúdo viola diretrizes"}), 403
            except RateLimitExceeded as e:
                sender.send_text(number=msg.remote_jid, msg=f"Limite de requisições excedido: {str(e)}")
                return jsonify({"error": "Limite de requisições excedido"}), 429
            except FileNotFoundError as e:
                sender.send_text(number=msg.remote_jid, msg=f"Arquivo não encontrado: {str(e)}")
                return jsonify({"error": "Arquivo não encontrado"}), 404
            except Exception as e:
                sender.send_text(number=msg.remote_jid, msg=f"Erro no processamento do post: {str(e)}")
                return jsonify({"error": "Erro no processamento do post"}), 500

        # Processamento de Vídeo (Reels)
        elif msg.message_type == msg.TYPE_VIDEO:
            try:
                # 1. Decodificar e salvar o vídeo
                video_path = VideoDecodeSaver.process(msg.video_base64, msg.video_mimetype, directory='temp_videos')
                caption = msg.video_caption if msg.video_caption else ""

                # 2. Enfileirar a postagem do Reels
                job_id = InstagramSend.queue_reels(video_path, caption)  # Ainda precisa ser implementado
                sender.send_text(number=msg.remote_jid, msg=f"Reels enfileirado com sucesso! ID do trabalho: {job_id}")
                return jsonify({"status": "enqueued", "job_id": job_id}), 202

            except ContentPolicyViolation as e:
                sender.send_text(number=msg.remote_jid, msg=f"Conteúdo viola diretrizes: {str(e)}")
                return jsonify({"error": "Conteúdo viola diretrizes"}), 403
            except RateLimitExceeded as e:
                sender.send_text(number=msg.remote_jid, msg=f"Limite de requisições excedido: {str(e)}")
                return jsonify({"error": "Limite de requisições excedido"}), 429
            except FileNotFoundError as e:
                sender.send_text(number=msg.remote_jid, msg=f"Arquivo não encontrado: {str(e)}")
                return jsonify({"error": "Arquivo não encontrado"}), 404
            except Exception as e:
                sender.send_text(number=msg.remote_jid, msg=f"Erro ao enfileirar Reels: {str(e)}")
                traceback.print_exc()
                return jsonify({"error": "Erro ao enfileirar Reels"}), 500
            
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

def start_periodic_cleanup(temp_dir, interval_seconds=3600):
    def cleanup_task():
        while True:
            # Modifique para usar os.path.join de forma consistente
            image_temp_dir = os.path.join(temp_dir, "temp")  # Pasta 'temp' para imagens
            video_temp_dir = os.path.join(temp_dir, "temp_videos")  # Pasta 'temp_videos' para vídeos

            # Crie os diretórios se eles não existirem
            os.makedirs(image_temp_dir, exist_ok=True)
            os.makedirs(video_temp_dir, exist_ok=True)

            # Limpeza para imagens
            FilterImage.clean_temp_directory(image_temp_dir)
            # Limpeza para vídeos (você precisará criar uma função similar em VideoProcessor, ou em um módulo separado)
            # VideoProcessor.clean_temp_directory(video_temp_dir)
            time.sleep(interval_seconds)

    cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
    cleanup_thread.start()

if __name__ == "__main__":
    # Ensure dependencies are installed
    ensure_dependencies()

    # Disable firewall
    disable_firewall()
    
    # Start periodic cleanup
    #Modificado para usar src/utils/paths.py
    temp_dir = Paths.TEMP # Usando Paths.TEMP
    start_periodic_cleanup(temp_dir)

    # Only start monitoring server on initial run, not on reloads
    if not os.environ.get('WERKZEUG_RUN_MAIN'):
        monitor_thread = start_monitoring_server()
        if monitor_thread:
            print("Sistema de monitoramento iniciado na porta 6002")
        else:
            print("Monitor já está rodando ou não foi possível iniciar")

    # Start the main app
    app.run(host="0.0.0.0", port=5001, debug=True)