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
from datetime import datetime

from src.utils.paths import Paths  # Add this import

# Import our queue exceptions for error handling
from src.services.post_queue import RateLimitExceeded, ContentPolicyViolation

# Import monitoring server starter
from monitor import start_monitoring_server

from src.instagram.filter import FilterImage
from src.services.send import sender #Para enviar mensagens de volta
from src.instagram.describe_video_tool import VideoDescriber  # Importar a classe VideoDescriber
from src.instagram.describe_carousel_tool import CarouselDescriber  # Importar a classe CarouselDescriber
from src.instagram.crew_post_instagram import InstagramPostCrew  # Importar a classe InstagramPostCrew
from src.instagram.image_validator import InstagramImageValidator  # Add this import
from src.services.post_notification import PostCompletionNotifier
from src.services.post_queue import post_queue

app = Flask(__name__)

# Initialize required directories
os.makedirs(os.path.join(Paths.ROOT_DIR, "temp_videos"), exist_ok=True)
os.makedirs(os.path.join(Paths.ROOT_DIR, "temp"), exist_ok=True)

# Create assets directory if it doesn't exist
assets_dir = os.path.join(Paths.ROOT_DIR, "assets")
os.makedirs(assets_dir, exist_ok=True)

# Define border image with full path
border_image_path = os.path.join(assets_dir, "moldura.png")

# Check if border image exists, if not, set it to None to make it optional
if not os.path.exists(border_image_path):
    print(f"⚠️ Aviso: Imagem de borda não encontrada em {border_image_path}")
    border_image_path = None

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
                                    msg=f"⚠️ São necessárias pelo menos 2 imagens para criar um carrossel. "
                                        f"Você tem apenas {len(carousel_images)} imagem.")
                    return jsonify({"status": "not enough images"}), 200
                
                try:
                    # Validar as imagens segundo os requisitos do Instagram
                    is_valid, validation_msg = InstagramImageValidator.validate_for_carousel(carousel_images)
                    if not is_valid:
                        sender.send_text(number=msg.remote_jid, 
                                        msg=f"⚠️ Erro de validação das imagens: {validation_msg}")
                        return jsonify({"status": "validation_error", "message": validation_msg}), 400
                    
                    # Se não houver legenda definida, usar uma padrão
                    caption_to_use = carousel_caption if carousel_caption else ""
                    
                    # Gerar descrição automática para as imagens do carrossel
                    if not caption_to_use:
                        try:
                            image_descriptions = CarouselDescriber.describe(carousel_images)
                            crew = InstagramPostCrew()
                            inputs_dict = {
                                "genero": "Neutro",
                                "caption": image_descriptions,
                                "describe": image_descriptions,
                                "estilo": "Divertido, Alegre, Sarcástico e descontraído",
                                "pessoa": "Terceira pessoa do singular",
                                "sentimento": "Positivo",
                                "tamanho": "200 palavras",
                                "emojs": "sim",
                                "girias": "sim"
                            }
                            caption_to_use = crew.kickoff(inputs=inputs_dict)
                        except Exception as e:
                            print(f"Erro ao gerar legenda automática: {str(e)}")
                            caption_to_use = "Carrossel de imagens publicado via webhook"  # Usar uma legenda padrão em caso de erro
                    
                    sender.send_text(number=msg.remote_jid, 
                                    msg=f"🔄 Processando carrossel com {len(carousel_images)} imagens...")
                    
                    # Aplicar bordas às imagens do carrossel (apenas se a imagem de borda existir)
                    bordered_images = []
                    for image_path in carousel_images:
                        try:
                            # Primeiro verificar e redimensionar se necessário
                            resized_image = InstagramImageValidator.resize_for_instagram(image_path)
                            
                            # Aplicar borda apenas se a imagem de borda existir
                            if border_image_path and os.path.exists(border_image_path):
                                bordered_image_path = FilterImage.apply_border(resized_image, border_image_path)
                                bordered_images.append(bordered_image_path)
                            else:
                                # Se não existir, usar a imagem redimensionada diretamente
                                bordered_images.append(resized_image)
                        except Exception as e:
                            print(f"Erro ao processar imagem {image_path}: {str(e)}")
                            bordered_images.append(image_path)  # Usar a imagem original em caso de erro
                    
                    # Enfileirar o carrossel para publicação
                    job_inputs = {'remote_jid': msg.remote_jid}
                    job_id = InstagramSend.queue_carousel(bordered_images, caption_to_use, job_inputs)
                    
                    sender.send_text(number=msg.remote_jid, 
                                    msg=f"✅ Carrossel enfileirado com sucesso!\n"
                                        f"ID do trabalho: {job_id}\n"
                                        f"Número de imagens: {len(bordered_images)}\n"
                                        f"Você pode verificar o status usando \"status {job_id}\"")
                    
                    # Verificar o status do trabalho após enfileiramento
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
            try:
                image_path = ImageDecodeSaver.process(msg.image_base64)
                caption = msg.image_caption if msg.image_caption else ""  # Usar a legenda da imagem, se houver

                # Enfileirar a postagem da foto
                job_inputs = {'remote_jid': msg.remote_jid}
                job_id = InstagramSend.queue_post(image_path, caption, job_inputs)
                sender.send_text(number=msg.remote_jid, msg=f"✅ Postagem de imagem enfileirada com sucesso!\nID do trabalho: {job_id}")
                
                # Verificar o status do trabalho após enfileiramento
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
                
                # Gerar legenda automática se não houver uma fornecida
                if not caption:
                    try:
                        # Descrever o vídeo
                        video_description = VideoDescriber.describe(video_path)
                        crew = InstagramPostCrew()
                        inputs_dict = {
                            "genero": "Neutro",
                            "caption": video_description,
                            "describe": video_description,
                            "estilo": "Divertido, Alegre, Sarcástico e descontraído",
                            "pessoa": "Terceira pessoa do singular",
                            "sentimento": "Positivo",
                            "tamanho": "200 palavras",
                            "emojs": "sim",
                            "girias": "sim"
                        }
                        caption = crew.kickoff(inputs=inputs_dict)
                    except Exception as e:
                        print(f"Erro ao gerar legenda automática: {str(e)}")
                        caption = ""  # Usar uma legenda vazia em caso de erro

                # 2. Enfileirar a postagem do Reels
                job_inputs = {'remote_jid': msg.remote_jid}
                job_id = InstagramSend.queue_reels(video_path, caption, job_inputs)
                sender.send_text(number=msg.remote_jid, msg=f"✅ Reels enfileirado com sucesso! ID do trabalho: {job_id}")
                
                # 3. Verificar o status do trabalho após enfileiramento
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
        if (is_valid):
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

@app.route("/debug/api-limits", methods=['GET'])
def check_api_limits():
    """Check current API usage and rate limits"""
    try:
        from src.instagram.instagram_carousel_service import InstagramCarouselService
        
        service = InstagramCarouselService()
        usage_info = service.get_app_usage_info()
        
        # Calculate time until reset if we have usage info
        usage_data = {}
        
        if 'app_usage' in usage_info and usage_info['app_usage']:
            app_usage = usage_info['app_usage']
            for limit_type, usage in app_usage.items():
                if isinstance(usage, dict) and 'call_count' in usage and 'total_cputime' in usage:
                    usage_data[limit_type] = {
                        'call_count': usage['call_count'],
                        'total_cpu_time': usage['total_cputime'],
                        'total_time': usage.get('total_time', 0),
                        'estimated_time_to_regain_access': usage.get('estimated_time_to_regain_access', 0)
                    }
        
        return jsonify({
            "status": "success",
            "usage_info": usage_info,
            "usage_data": usage_data,
            "note": "If estimated_time_to_regain_access > 0, wait this many seconds before retrying"
        })
        
    except Exception as e:
        import traceback
        return jsonify({
            "status": "error",
            "message": str(e),
            "traceback": traceback.format_exc()
        }), 500

def handle_post_completion(job_id, job_info):
    """
    Callback function for when a post is completed
    
    Args:
        job_id (str): ID do trabalho completado
        job_info (dict): Detalhes do trabalho completado
    """
    try:
        # Obter informações relevantes do post
        remote_jid = job_info.get("inputs", {}).get("remote_jid")
        content_type = job_info.get("content_type", "post")
        result = job_info.get("result", {})
        
        # Se não temos um número para notificar, não podemos enviar a notificação
        if not remote_jid:
            return
            
        # Construir mensagem de notificação
        notification_text = f"✅ Seu post foi publicado com sucesso! 🎉\n\n"
        notification_text += f"🆔 ID do trabalho: {job_id}\n"
        notification_text += f"📌 Tipo: {content_type}\n"
        
        # Adicionar link se disponível
        if result and result.get("permalink"):
            notification_text += f"🔗 Link: {result.get('permalink')}\n"
            
        # Enviar notificação
        sender.send_text(number=remote_jid, msg=notification_text)
        
    except Exception as e:
        print(f"Erro ao enviar notificação de conclusão: {e}")

# Create a global notifier instance
post_notifier = PostCompletionNotifier(notification_callback=handle_post_completion)

def setup_notification_system():
    """Configura o sistema de notificação de posts completados"""
    # Iniciar o monitoramento de posts completados
    post_notifier.start_monitoring(post_queue)
    print("Sistema de notificação de posts iniciado")

if __name__ == "__main__":
    # Ensure dependencies are installed
    ensure_dependencies()

    # Disable firewall
    disable_firewall()
    
    # Ensure border image exists
    try:
        from setup_border import create_border_image
        border_image_path = create_border_image()
        print(f"Using border image: {border_image_path}")
    except Exception as e:
        print(f"Warning: Could not create border image: {str(e)}")
    
    # Start periodic cleanup
    temp_dir = Paths.TEMP # Usando Paths.TEMP
    start_periodic_cleanup(temp_dir)

    # Only start monitoring server on initial run, not on reloads
    if not os.environ.get('WERKZEUG_RUN_MAIN'):
        monitor_thread = start_monitoring_server()
        if (monitor_thread):
            print("Sistema de monitoramento iniciado na porta 6002")
        else:
            print("Monitor já está rodando ou não foi possível iniciar")

    # Setup notification system
    setup_notification_system()

    # Start the main app
    app.run(host="0.0.0.0", port=5001, debug=True)