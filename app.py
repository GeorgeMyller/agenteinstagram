from src.services.message import Message
from src.utils.image_decode_save import ImageDecodeSaver
from src.utils.video_decode_save import VideoDecodeSaver  # Added import for video processing
from src.services.instagram_send import InstagramSend
from src.instagram.instagram_reels_publisher import ReelsPublisher  # Importe a classe ReelsPublisher
from flask import Flask, request, jsonify
import subprocess
import os
import time
import traceback
import threading
import re

from src.utils.paths import Paths  # Add this import

# Import our queue exceptions for error handling
from src.services.post_queue import RateLimitExceeded, ContentPolicyViolation

# Import monitoring server starter
from monitor import start_monitoring_server

from src.instagram.filter import FilterImage
from src.services.send import sender #Para enviar mensagens de volta

app = Flask(__name__)

# Initialize required directories
os.makedirs(os.path.join(Paths.ROOT_DIR, "temp_videos"), exist_ok=True)
os.makedirs(os.path.join(Paths.ROOT_DIR, "temp"), exist_ok=True)

border_image = "moldura.png"

# Variáveis de estado para o modo carrossel
is_carousel_mode = False
carousel_images = []
carousel_start_time = 0
carousel_caption = ""
CAROUSEL_TIMEOUT = 300  # 5 minutos em segundos
MAX_CAROUSEL_IMAGES = 10


@app.route("/messages-upsert", methods=['POST'])
def webhook():
    global is_carousel_mode, carousel_images, carousel_start_time, carousel_caption

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
        # Iniciar modo carrossel com comando "carrossel" ou "carousel"
        carousel_command = re.match(r'^carrosse?l\s*(.*)', texto.lower() if texto else "") if texto else None
        if carousel_command:
            is_carousel_mode = True
            carousel_images = []
            carousel_caption = carousel_command.group(1).strip() if carousel_command.group(1) else ""
            carousel_start_time = time.time()
            
            instructions = (
                "🎠 *Modo carrossel ativado!*\n\n"
                "- Envie as imagens que deseja incluir no carrossel (2-10 imagens)\n"
                "- Para definir uma legenda, envie \"legenda: sua legenda aqui\"\n"
                "- Quando terminar, envie \"postar\" para publicar o carrossel\n"
                "- Para cancelar, envie \"cancelar\"\n\n"
                "O modo carrossel será desativado automaticamente após 5 minutos de inatividade."
            )
            
            if carousel_caption:
                sender.send_text(number=msg.remote_jid, 
                                msg=f"{instructions}\n\nLegenda inicial definida: {carousel_caption}")
            else:
                sender.send_text(number=msg.remote_jid, msg=instructions)
            
            return jsonify({"status": "Modo carrossel ativado"}), 200

        if is_carousel_mode:
            # Recebimento de imagens para o carrossel
            if msg.message_type == msg.TYPE_IMAGE:
                if len(carousel_images) >= MAX_CAROUSEL_IMAGES:
                    sender.send_text(number=msg.remote_jid, 
                                    msg=f"⚠️ Limite máximo de {MAX_CAROUSEL_IMAGES} imagens atingido! Envie \"postar\" para publicar.")
                    return jsonify({"status": "max images reached"}), 200
                    
                image_path = ImageDecodeSaver.process(msg.image_base64)
                carousel_images.append(image_path)
                
                # Verificar se já temos pelo menos 2 imagens para habilitar o comando "postar"
                if len(carousel_images) >= 2:
                    sender.send_text(number=msg.remote_jid, 
                                    msg=f"✅ Imagem {len(carousel_images)} adicionada ao carrossel.\n"
                                        f"Você pode enviar mais imagens ou enviar \"postar\" para publicar.")
                else:
                    sender.send_text(number=msg.remote_jid, 
                                    msg=f"✅ Imagem {len(carousel_images)} adicionada ao carrossel.\n"
                                        f"Envie pelo menos mais uma imagem para completar o carrossel.")
                
                # Resetar o timer de timeout a cada imagem recebida
                carousel_start_time = time.time()
                return jsonify({"status": f"Imagem adicionada ao carrossel"}), 200

            # Comando para definir legenda
            elif texto and texto.lower().startswith("legenda:"):
                carousel_caption = texto[8:].strip()  # Remove "legenda:" e espaços em branco
                sender.send_text(number=msg.remote_jid, 
                                msg=f"✅ Legenda definida: \"{carousel_caption}\"")
                carousel_start_time = time.time()  # Resetar timer
                return jsonify({"status": "Legenda definida"}), 200

            # Comando para publicar o carrossel
            elif texto and texto.lower() == "postar":
                if len(carousel_images) < 2:
                    sender.send_text(number=msg.remote_jid, 
                                    msg="⚠️ São necessárias pelo menos 2 imagens para criar um carrossel. "
                                        f"Você tem apenas {len(carousel_images)} imagem.")
                    return jsonify({"status": "not enough images"}), 200
                
                try:
                    # Se não houver legenda definida, usar uma padrão
                    caption_to_use = carousel_caption if carousel_caption else "Carrossel de imagens publicado via webhook"
                    
                    sender.send_text(number=msg.remote_jid, 
                                    msg=f"🔄 Processando carrossel com {len(carousel_images)} imagens...")
                    
                    # Enfileirar o carrossel para publicação
                    job_id = InstagramSend.queue_carousel(carousel_images, caption_to_use)
                    
                    sender.send_text(number=msg.remote_jid, 
                                    msg=f"✅ Carrossel enfileirado com sucesso!\n"
                                        f"ID do trabalho: {job_id}\n"
                                        f"Número de imagens: {len(carousel_images)}\n"
                                        f"Você pode verificar o status usando \"status {job_id}\"")
                    
                except Exception as e:
                    print(f"Erro ao enfileirar carrossel: {e}")
                    sender.send_text(number=msg.remote_jid, 
                                    msg=f"❌ Erro ao enfileirar carrossel: {str(e)}")
                    return jsonify({"status": "error", "message": "Erro ao enfileirar carrossel"}), 500
                finally:
                    is_carousel_mode = False  # Resetar o modo carrossel
                    carousel_images = []
                    carousel_caption = ""
                return jsonify({"status": "Carrossel processado e enfileirado"}), 200

            # Comando para cancelar o carrossel
            elif texto and texto.lower() == "cancelar":
                is_carousel_mode = False
                carousel_images = []
                carousel_caption = ""
                sender.send_text(number=msg.remote_jid, 
                                msg="🚫 Modo carrossel cancelado. Todas as imagens foram descartadas.")
                return jsonify({"status": "Carrossel cancelado"}), 200
                
            # Verificar timeout
            elif time.time() - carousel_start_time > CAROUSEL_TIMEOUT:
                # Timeout, sair do modo carrossel
                is_carousel_mode = False
                carousel_images = []
                carousel_caption = ""
                sender.send_text(number=msg.remote_jid, 
                                msg="⏱️ Timeout do carrossel. Envie 'carrossel' novamente para iniciar.")
                return jsonify({"status": "Timeout do carrossel"}), 200

            # Verificar status de um job
            elif texto and texto.lower().startswith("status "):
                job_id = texto.split(" ", 1)[1].strip()
                try:
                    job_status = InstagramSend.check_post_status(job_id)
                    if job_status:
                        status_text = f"📊 Status do trabalho {job_id}:\n"
                        status_text += f"• Status: {job_status.get('status', 'Desconhecido')}\n"
                        status_text += f"• Tipo: {job_status.get('content_type', 'Desconhecido')}\n"
                        status_text += f"• Criado em: {job_status.get('created_at', 'Desconhecido')}\n"
                        
                        if job_status.get('result') and job_status['result'].get('permalink'):
                            status_text += f"• Link: {job_status['result']['permalink']}"
                        
                        sender.send_text(number=msg.remote_jid, msg=status_text)
                    else:
                        sender.send_text(number=msg.remote_jid, 
                                        msg=f"❌ Trabalho {job_id} não encontrado")
                except Exception as e:
                    sender.send_text(number=msg.remote_jid, 
                                    msg=f"❌ Erro ao verificar status: {str(e)}")
                
                carousel_start_time = time.time()  # Resetar timer
                return jsonify({"status": "Status verificado"}), 200

            #Ignorar outras mensagens, se estiver em modo carrossel
            carousel_start_time = time.time()  # Resetar timer para qualquer interação
            return jsonify({"status": "processed (carousel mode)"}), 200

        # Verificar comando de status mesmo fora do modo carrossel
        if texto and texto.lower().startswith("status "):
            job_id = texto.split(" ", 1)[1].strip()
            try:
                job_status = InstagramSend.check_post_status(job_id)
                if job_status:
                    status_text = f"📊 Status do trabalho {job_id}:\n"
                    status_text += f"• Status: {job_status.get('status', 'Desconhecido')}\n"
                    status_text += f"• Tipo: {job_status.get('content_type', 'Desconhecido')}\n"
                    status_text += f"• Criado em: {job_status.get('created_at', 'Desconhecido')}\n"
                    
                    if job_status.get('result') and job_status['result'].get('permalink'):
                        status_text += f"• Link: {job_status['result']['permalink']}"
                    
                    sender.send_text(number=msg.remote_jid, msg=status_text)
                else:
                    sender.send_text(number=msg.remote_jid, 
                                    msg=f"❌ Trabalho {job_id} não encontrado")
            except Exception as e:
                sender.send_text(number=msg.remote_jid, 
                                msg=f"❌ Erro ao verificar status: {str(e)}")
            
            return jsonify({"status": "Status verificado"}), 200

        # Processamento de Imagem Única
        if msg.message_type == msg.TYPE_IMAGE:
            image_path = ImageDecodeSaver.process(msg.image_base64)
            caption = msg.image_caption if msg.image_caption else ""  # Usar a legenda da imagem, se houver

            try:
                job_id = InstagramSend.queue_post(image_path, caption)
                sender.send_text(number=msg.remote_jid, msg=f"✅ Postagem de imagem enfileirada com sucesso!\nID do trabalho: {job_id}")
                return jsonify({"status": "enqueued", "job_id": job_id}), 202
            except ContentPolicyViolation as e:
                sender.send_text(number=msg.remote_jid, msg=f"⚠️ Conteúdo viola diretrizes: {str(e)}")
                return jsonify({"error": "Conteúdo viola diretrizes"}), 403
            except RateLimitExceeded as e:
                sender.send_text(number=msg.remote_jid, msg=f"⏳ Limite de requisições excedido: {str(e)}")
                return jsonify({"error": "Limite de requisições excedido"}), 429
            except FileNotFoundError as e:
                sender.send_text(number=msg.remote_jid, msg=f"❌ Arquivo não encontrado: {str(e)}")
                return jsonify({"error": "Arquivo não encontrado"}), 404
            except Exception as e:
                sender.send_text(number=msg.remote_jid, msg=f"❌ Erro no processamento do post: {str(e)}")
                return jsonify({"error": "Erro no processamento do post"}), 500

        # Processamento de Vídeo (Reels)
        elif msg.message_type == msg.TYPE_VIDEO:
            try:
                # 1. Decodificar e salvar o vídeo
                video_path = VideoDecodeSaver.process(msg.video_base64)
                caption = msg.video_caption if msg.video_caption else ""
                print(f"Caption received: {caption}")  # Debug statement
                # 2. Enfileirar a postagem do Reels
                job_id = InstagramSend.queue_reels(video_path, caption)  # Ainda precisa ser implementado
                sender.send_text(number=msg.remote_jid, msg=f"✅ Reels enfileirado com sucesso! ID do trabalho: {job_id}")
                return jsonify({"status": "enqueued", "job_id": job_id}), 202

            except ContentPolicyViolation as e:
                sender.send_text(number=msg.remote_jid, msg=f"⚠️ Conteúdo viola diretrizes: {str(e)}")
                return jsonify({"error": "Conteúdo viola diretrizes"}), 403
            except RateLimitExceeded as e:
                sender.send_text(number=msg.remote_jid, msg=f"⏳ Limite de requisições excedido: {str(e)}")
                return jsonify({"error": "Limite de requisições excedido"}), 429
            except FileNotFoundError as e:
                sender.send_text(number=msg.remote_jid, msg=f"❌ Arquivo não encontrado: {str(e)}")
                return jsonify({"error": "Arquivo não encontrado"}), 404
            except Exception as e:
                sender.send_text(number=msg.remote_jid, msg=f"❌ Erro ao enfileirar Reels: {str(e)}")
                traceback.print_exc()
                return jsonify({"error": "Erro ao enfileirar Reels"}), 500
            
    except Exception as e:
        print(f"Erro no processamento do webhook: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": "Erro no processamento da requisição"}), 500

    return jsonify({"status": "processed"}), 200

# ... resto do código permanece o mesmo
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

# Add these new debug endpoints
@app.route("/debug/carousel/clear", methods=['POST'])
def clear_carousel_cache():
    """Clear any cached carousel state"""
    try:
        # Reset global carousel state variables
        global is_carousel_mode, carousel_images, carousel_start_time, carousel_caption
        
        # Save previous state for logging
        prev_state = {
            "was_carousel_mode": is_carousel_mode,
            "image_count": len(carousel_images)
        }
        
        is_carousel_mode = False
        carousel_images = []
        carousel_caption = ""
        carousel_start_time = 0
        
        # Also look for any temporary media files that might be used by carousel
        # (This is optional but can help clear filesystem clutter)
        
        return jsonify({
            "status": "success", 
            "message": "Carousel state cleared",
            "previous_state": prev_state
        })
    except Exception as e:
        import traceback
        return jsonify({
            "status": "error",
            "message": str(e),
            "traceback": traceback.format_exc()
        }), 500

@app.route("/debug/carousel/status", methods=['GET'])
def get_carousel_status():
    """Get current carousel state for debugging"""
    try:
        status = {
            "is_carousel_mode": is_carousel_mode,
            "image_count": len(carousel_images),
            "image_paths": carousel_images if len(carousel_images) < 10 else "Too many to display",
            "caption": carousel_caption,
            "time_in_mode": time.time() - carousel_start_time if carousel_start_time > 0 else 0,
            "timeout_seconds": CAROUSEL_TIMEOUT,
            "will_timeout_in": CAROUSEL_TIMEOUT - (time.time() - carousel_start_time) if carousel_start_time > 0 else "N/A"
        }
        
        return jsonify(status)
    except Exception as e:
        import traceback
        return jsonify({
            "status": "error",
            "message": str(e),
            "traceback": traceback.format_exc()
        }), 500

@app.route("/debug/token/check", methods=['GET'])
def check_instagram_token():
    """Check if the Instagram API token has the correct permissions"""
    try:
        from src.instagram.instagram_carousel_service import InstagramCarouselService
        
        service = InstagramCarouselService()
        is_valid, missing_permissions = service.check_token_permissions()
        
        token = os.getenv('INSTAGRAM_API_KEY', '')
        mask_token = token[:10] + "..." + token[-4:] if len(token) > 14 else "Not set"
        
        token_info = {
            "is_valid": is_valid,
            "missing_permissions": missing_permissions if not is_valid else [],
            "token": mask_token,
            "account_id": os.getenv('INSTAGRAM_ACCOUNT_ID', 'Not set')
        }
        
        # Add extra details if the token is valid
        if is_valid:
            try:
                details = service.debug_token()
                if details and 'data' in details:
                    data = details['data']
                    token_info["details"] = {
                        "app_id": data.get('app_id'),
                        "expires_at": datetime.fromtimestamp(data.get('expires_at')).strftime('%Y-%m-%d %H:%M:%S') if data.get('expires_at') else "Unknown",
                        "scopes": data.get('scopes', [])
                    }
            except Exception as e:
                token_info["error_getting_details"] = str(e)
        
        return jsonify(token_info)
    except Exception as e:
        import traceback
        return jsonify({
            "status": "error",
            "message": str(e),
            "traceback": traceback.format_exc()
        }), 500

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