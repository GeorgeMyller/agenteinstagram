from flask import Flask, request, jsonify
import logging
from src.services.message import Message
from src.utils.config import Config
from src.utils.cleanup_scheduler import CleanupScheduler
from src.utils.resource_manager import ResourceManager
import os
import tempfile
from src.instagram.image_validator import InstagramImageValidator
from src.utils.image_decode_save import ImageDecodeSaver
from src.utils.video_decode_save import VideoDecodeSaver
from src.instagram.instagram_send import InstagramSend
from src.instagram.instagram_reels_publisher import ReelsPublisher
import subprocess
import time
import traceback
import threading
import re
from datetime import datetime

from src.utils.paths import Paths
from src.services.post_queue import RateLimitExceeded, ContentPolicyViolation
from monitor import start_monitoring_server
from src.instagram.filter import FilterImage
from src.services.send import sender
from src.instagram.describe_video_tool import VideoDescriber
from src.instagram.describe_carousel_tool import CarouselDescriber
from src.instagram.crew_post_instagram import InstagramPostCrew

# Configure logging with detailed format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__, template_folder="monitoring_templates")

# Initialize configuration and resource management
config = Config.get_instance()
resource_manager = ResourceManager()
cleanup_scheduler = CleanupScheduler.get_instance()

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

def _handle_text_message(message: Message):
    """Processes a text message"""
    logger.info("Handling text message")
    return {"type": "text", "content": message.content.text or ""}

def _handle_image_message(message: Message):
    """Processes an image message and posts it to Instagram"""
    logger.info("Handling image message")
    try:
        # Use the content attributes from the Message class
        image_base64 = message.content.image_base64
        caption = message.content.image_caption or ""
        
        if not image_base64:
            logger.error("No image data found in message")
            return {"type": "image", "status": "error", "message": "No image data found"}
            
        try:
            # Save base64 image using ImageDecodeSaver
            temp_path = ImageDecodeSaver.process(image_base64)
            logger.info(f"Image saved to temporary file: {temp_path}")
            
            # Validate and optimize image for Instagram
            validator = InstagramImageValidator()
            result = validator.process_single_photo(temp_path)
            
            if result['status'] == 'error':
                logger.error(f"Image validation failed: {result['message']}")
                return {"type": "image", "status": "error", "message": result['message']}
            
            # Use optimized image path for posting
            optimized_path = result['image_path'] or temp_path
            
            try:
                # Import and use InstagramSend to post the image
                from src.instagram.instagram_send import InstagramSend
                post_result = InstagramSend.send_instagram(optimized_path, caption)
                
                if post_result and post_result.get("status") == "success":
                    logger.info(f"Image posted successfully to Instagram with ID: {post_result.get('id')}")
                    return {
                        "type": "image", 
                        "status": "success", 
                        "message": "Image posted successfully",
                        "post_id": post_result.get("id")
                    }
                else:
                    error_msg = post_result.get("message") if post_result else "Unknown error"
                    logger.error(f"Failed to post image: {error_msg}")
                    return {
                        "type": "image", 
                        "status": "error", 
                        "message": f"Failed to post image: {error_msg}"
                    }
            finally:
                # Clean up temporary files
                for path in [temp_path, optimized_path]:
                    if path and os.path.exists(path):
                        try:
                            os.unlink(path)
                            logger.info(f"Cleaned up temporary file: {path}")
                        except Exception as e:
                            logger.warning(f"Failed to clean up temporary file {path}: {e}")
                            
        except Exception as e:
            logger.error(f"Error processing image: {str(e)}")
            return {"type": "image", "status": "error", "message": str(e)}
            
    except Exception as e:
        logger.error(f"Error handling image message: {str(e)}")
        return {"type": "image", "status": "error", "message": str(e)}

def _handle_video_message(message: Message):
    """Processes a video message"""
    logger.info("Handling video message")
    try:
        video_base64 = message.content.video_base64
        caption = message.content.video_caption or ""
        
        if not video_base64:
            logger.error("No video data found in message")
            return {"type": "video", "status": "error", "message": "No video data found"}
            
        try:
            # Save base64 video to a temporary file
            from src.instagram.video_decode_save import VideoDecodeSaver
            video_path = VideoDecodeSaver.process(video_base64)
            logger.info(f"Video saved to temporary file: {video_path}")
            
            try:
                # Import and use InstagramSend to post the video
                from src.instagram.instagram_send import InstagramSend
                post_result = InstagramSend.send_instagram_video(video_path, caption)
                
                if post_result and post_result.get("status") == "success":
                    logger.info(f"Video posted successfully to Instagram with ID: {post_result.get('id')}")
                    return {
                        "type": "video", 
                        "status": "success", 
                        "message": "Video posted successfully",
                        "post_id": post_result.get("id")
                    }
                else:
                    error_msg = post_result.get("message") if post_result else "Unknown error"
                    logger.error(f"Failed to post video: {error_msg}")
                    return {
                        "type": "video", 
                        "status": "error", 
                        "message": f"Failed to post video: {error_msg}"
                    }
            finally:
                # Clean up temporary file
                if video_path and os.path.exists(video_path):
                    try:
                        os.unlink(video_path)
                        logger.info(f"Cleaned up temporary video file: {video_path}")
                    except Exception as e:
                        logger.warning(f"Failed to clean up temporary video file {video_path}: {e}")
                            
        except Exception as e:
            logger.error(f"Error processing video: {str(e)}")
            return {"type": "video", "status": "error", "message": str(e)}
            
    except Exception as e:
        logger.error(f"Error handling video message: {str(e)}")
        return {"type": "video", "status": "error", "message": str(e)}

def _handle_unsupported_type(message: Message):
    """Handles unsupported message types"""
    logger.info("Unsupported message type received")
    return {"error": "Unsupported message type"}

def initialize_app_wrapper():
    """
    Initialize application components before first request.
    
    Performs:
    1. Starts cleanup scheduler for temporary files
    2. Validates configuration
    3. Initializes resource monitoring
    4. Logs initial system status
    """
    try:
        # Start cleanup scheduler
        cleanup_scheduler.start()
        logger.info("Cleanup scheduler started successfully")
        
        # Log initial disk usage
        usage = resource_manager.monitor_disk_usage()
        if usage:
            logger.info(f"Initial storage usage: {usage['total_size_mb']:.1f}MB")
    except Exception as e:
        logger.error(f"Error during application initialization: {e}")

# Register initialization
if hasattr(app, 'before_first_request'):
    app.before_first_request(initialize_app_wrapper)
else:
    initialize_app_wrapper()

@app.route('/messages-upsert', methods=['POST'])
def handle_message():
    """Primary endpoint for processing incoming messages."""
    global is_carousel_mode, carousel_images, carousel_start_time, carousel_caption

    try:
        data = request.json
        logger.info(f"Raw message data: {data}")
        
        # Create message object with raw data
        message = Message(data)
        
        # Debug information
        logger.info(f"Message type: {message.message_type}")
        logger.info(f"Remote JID: {message.remote_jid}")
        logger.info(f"Group ID: {message.group_id if hasattr(message, 'group_id') else None}")
        
        # Get authorized group ID from config
        logger.info(f"Authorized Group ID from config: {config.AUTHORIZED_GROUP_ID}")
        authorized_id = config.AUTHORIZED_GROUP_ID.split('@')[0] if config.AUTHORIZED_GROUP_ID else None
        
        # Verify if message is from authorized group - with more flexible checking
        if not message.remote_jid or not message.remote_jid.strip():
            logger.warning("Empty remote_jid in message")
            # Try to get group ID from different parts of the payload
            potential_group_id = None
            if data and isinstance(data, dict):
                # Try common locations in different webhook formats
                if 'key' in data and isinstance(data['key'], dict):
                    potential_group_id = data['key'].get('remoteJid')
                elif 'data' in data and isinstance(data['data'], dict):
                    data_obj = data['data']
                    if 'key' in data_obj and isinstance(data_obj['key'], dict):
                        potential_group_id = data_obj['key'].get('remoteJid')
                    elif 'message' in data_obj and isinstance(data_obj['message'], dict):
                        message_obj = data_obj['message']
                        potential_group_id = message_obj.get('key', {}).get('remoteJid')
            
            logger.info(f"Found potential group ID: {potential_group_id}")
            
            # If we found a group ID that matches, proceed
            if potential_group_id and (
                potential_group_id == config.AUTHORIZED_GROUP_ID or 
                potential_group_id.split('@')[0] == authorized_id
            ):
                logger.info(f"Proceeding with manually extracted group ID: {potential_group_id}")
                # Continue processing with the manually extracted group ID
            else:
                logger.info(f"Message ignored - unauthorized source (empty remote_jid)")
                return jsonify({
                    "status": "ignored", 
                    "message": "Message from unauthorized source (empty remote_jid)"
                }), 403
        elif not authorized_id:
            logger.warning("No authorized group ID configured")
            return jsonify({
                "status": "ignored", 
                "message": "No authorized group configured"
            }), 403
        elif message.group_id != authorized_id and message.remote_jid.split('@')[0] != authorized_id:
            logger.info(f"Message ignored - unauthorized source: {message.remote_jid}")
            return jsonify({
                "status": "ignored", 
                "message": "Message from unauthorized source"
            }), 403
        
        # Process message based on type
        logger.info(f"Processing message from authorized group: {message.remote_jid}")
        
        if message.message_type == message.TYPE_TEXT:
            response = _handle_text_message(message)
        elif message.message_type == message.TYPE_IMAGE:
            response = _handle_image_message(message)
        elif message.message_type == message.TYPE_VIDEO:
            response = _handle_video_message(message)
        else:
            response = _handle_unsupported_type(message)
            
        return jsonify({
            "status": "success",
            "message": "Message processed successfully",
            "response": response
        }), 200
        
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route("/messages-upsert", methods=['POST'])
def webhook():
    global is_carousel_mode, carousel_images, carousel_start_time, carousel_caption

    try:
        data = request.get_json()
        msg = Message(data)
        texto = msg.get_text()
        
        # Verificar se o número é de um grupo valido
        if msg.scope == Message.SCOPE_GROUP:
            print(f"Grupo: {msg.group_id}")
            if str(msg.group_id) != "120363383673368986":
                return jsonify({"status": "processed, but ignored"}), 200
        
        # Lógica do Modo Carrossel
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
            # Handle carousel mode operations
            if msg.message_type == msg.TYPE_IMAGE:
                if len(carousel_images) >= MAX_CAROUSEL_IMAGES:
                    sender.send_text(number=msg.remote_jid, 
                                    msg=f"⚠️ Limite máximo de {MAX_CAROUSEL_IMAGES} imagens atingido!")
                    return jsonify({"status": "max images reached"}), 200
                    
                image_path = ImageDecodeSaver.process(msg.image_base64)
                carousel_images.append(image_path)
                
                if len(carousel_images) >= 2:
                    sender.send_text(number=msg.remote_jid, 
                                    msg=f"✅ Imagem {len(carousel_images)} adicionada ao carrossel.")
                else:
                    sender.send_text(number=msg.remote_jid, 
                                    msg=f"✅ Imagem {len(carousel_images)} adicionada. Envie mais uma para completar.")
                
                carousel_start_time = time.time()
                return jsonify({"status": "Imagem adicionada"}), 200

            elif texto and texto.lower().startswith("legenda:"):
                carousel_caption = texto[8:].strip()
                sender.send_text(number=msg.remote_jid, 
                                msg=f"✅ Legenda definida: \"{carousel_caption}\"")
                carousel_start_time = time.time()
                return jsonify({"status": "Legenda definida"}), 200

            elif texto and texto.lower() == "postar":
                return handle_carousel_post(msg, carousel_images, carousel_caption)

            elif texto and texto.lower() == "cancelar":
                is_carousel_mode = False
                carousel_images = []
                carousel_caption = ""
                sender.send_text(number=msg.remote_jid, 
                                msg="🚫 Modo carrossel cancelado. Todas as imagens foram descartadas.")
                return jsonify({"status": "Carrossel cancelado"}), 200
                
            elif time.time() - carousel_start_time > CAROUSEL_TIMEOUT:
                is_carousel_mode = False
                carousel_images = []
                carousel_caption = ""
                sender.send_text(number=msg.remote_jid, 
                                msg="⏱️ Timeout do carrossel. Envie 'carrossel' novamente para iniciar.")
                return jsonify({"status": "Timeout do carrossel"}), 200

            elif texto and texto.lower().startswith("status "):
                return handle_status_check(msg, texto)

            carousel_start_time = time.time()
            return jsonify({"status": "processed (carousel mode)"}), 200

        # Handle status check outside carousel mode
        if texto and texto.lower().startswith("status "):
            return handle_status_check(msg, texto)

        # Handle single image post
        if msg.message_type == msg.TYPE_IMAGE:
            try:
                image_path = ImageDecodeSaver.process(msg.image_base64)
                caption = msg.image_caption if msg.image_caption else ""

                job_id = InstagramSend.queue_post(image_path, caption)
                sender.send_text(number=msg.remote_jid, 
                                msg=f"✅ Imagem enfileirada!\nID do trabalho: {job_id}")
                
                return check_and_send_status(msg, job_id)

            except Exception as e:
                handle_post_error(msg, e)
                return jsonify({"error": "Erro no processamento do post"}), 500

        # Handle video post
        elif msg.message_type == msg.TYPE_VIDEO:
            try:
                video_path = VideoDecodeSaver.process(msg.video_base64)
                caption = msg.video_caption if msg.video_caption else ""
                
                if not caption:
                    try:
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
                        print(f"Erro na geração de legenda: {str(e)}")
                        caption = ""

                job_id = InstagramSend.queue_reels(video_path, caption)
                sender.send_text(number=msg.remote_jid, 
                                msg=f"✅ Vídeo enfileirado!\nID do trabalho: {job_id}")
                
                return check_and_send_status(msg, job_id)

            except Exception as e:
                handle_post_error(msg, e)
                return jsonify({"error": "Erro no processamento do vídeo"}), 500
            
    except Exception as e:
        print(f"Erro no webhook: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": "Erro no processamento"}), 500

    return jsonify({"status": "processed"}), 200

def handle_carousel_post(msg, images, caption):
    """Handle posting a carousel"""
    global is_carousel_mode, carousel_images, carousel_caption
    
    try:
        if len(images) < 2:
            sender.send_text(number=msg.remote_jid, 
                            msg="⚠️ São necessárias pelo menos 2 imagens para um carrossel.")
            return jsonify({"status": "not enough images"}), 200
        
        is_valid, validation_msg = InstagramImageValidator.validate_for_carousel(images)
        if not is_valid:
            sender.send_text(number=msg.remote_jid, 
                            msg=f"⚠️ Erro de validação: {validation_msg}")
            return jsonify({"status": "validation_error"}), 400
        
        caption_to_use = caption if caption else generate_carousel_caption(images)
        
        sender.send_text(number=msg.remote_jid, 
                        msg=f"🔄 Processando carrossel com {len(images)} imagens...")
        
        processed_images = process_carousel_images(images)
        job_id = InstagramSend.queue_carousel(processed_images, caption_to_use)
        
        sender.send_text(number=msg.remote_jid, 
                        msg=f"✅ Carrossel enfileirado!\nID do trabalho: {job_id}")
        
        status_result = check_and_send_status(msg, job_id)
        
        is_carousel_mode = False
        carousel_images = []
        carousel_caption = ""
        
        return status_result

    except Exception as e:
        handle_post_error(msg, e)
        is_carousel_mode = False
        carousel_images = []
        carousel_caption = ""
        return jsonify({"error": "Erro no processamento do carrossel"}), 500

def generate_carousel_caption(images):
    """Generate caption for carousel using AI"""
    try:
        descriptions = CarouselDescriber.describe(images)
        crew = InstagramPostCrew()
        inputs_dict = {
            "genero": "Neutro",
            "caption": descriptions,
            "describe": descriptions,
            "estilo": "Divertido, Alegre, Sarcástico e descontraído",
            "pessoa": "Terceira pessoa do singular",
            "sentimento": "Positivo",
            "tamanho": "200 palavras",
            "emojs": "sim",
            "girias": "sim"
        }
        return crew.kickoff(inputs=inputs_dict)
    except Exception as e:
        print(f"Erro na geração de legenda: {str(e)}")
        return "Carrossel de imagens"

def process_carousel_images(images):
    """Process images for carousel, applying resizing and borders"""
    processed_images = []
    for image_path in images:
        try:
            resized = InstagramImageValidator.resize_for_instagram(image_path)
            if border_image_path and os.path.exists(border_image_path):
                processed = FilterImage.apply_border(resized, border_image_path)
            else:
                processed = resized
            processed_images.append(processed)
        except Exception as e:
            print(f"Erro no processamento da imagem {image_path}: {str(e)}")
            processed_images.append(image_path)
    return processed_images

def handle_status_check(msg, texto):
    """Handle checking status of a job"""
    job_id = texto.split(" ", 1)[1].strip()
    try:
        return check_and_send_status(msg, job_id)
    except Exception as e:
        sender.send_text(number=msg.remote_jid, 
                        msg=f"❌ Erro ao verificar status: {str(e)}")
        return jsonify({"error": "Erro ao verificar status"}), 500

def check_and_send_status(msg, job_id):
    """Check and send job status to user"""
    try:
        job_status = InstagramSend.check_post_status(job_id)
        if job_status:
            status_text = format_status_message(job_id, job_status)
            sender.send_text(number=msg.remote_jid, msg=status_text)
            return jsonify({"status": "Status enviado", "job_status": job_status}), 200
        else:
            sender.send_text(number=msg.remote_jid, 
                            msg=f"❌ Trabalho {job_id} não encontrado")
            return jsonify({"error": "Job não encontrado"}), 404
    except Exception as e:
        raise

def format_status_message(job_id, status):
    """Format job status message"""
    text = f"📊 Status do trabalho {job_id}:\n"
    text += f"• Status: {status.get('status', 'Desconhecido')}\n"
    text += f"• Tipo: {status.get('content_type', 'Desconhecido')}\n"
    text += f"• Criado em: {status.get('created_at', 'Desconhecido')}\n"
    
    if status.get('result') and status['result'].get('permalink'):
        text += f"• Link: {status['result']['permalink']}"
    
    return text

def handle_post_error(msg, error):
    """Handle posting errors and send appropriate message to user"""
    if isinstance(error, ContentPolicyViolation):
        sender.send_text(number=msg.remote_jid, 
                        msg=f"⚠️ Conteúdo viola diretrizes: {str(error)}")
    elif isinstance(error, RateLimitExceeded):
        sender.send_text(number=msg.remote_jid, 
                        msg=f"⏳ Limite de requisições excedido: {str(error)}")
    elif isinstance(error, FileNotFoundError):
        sender.send_text(number=msg.remote_jid, 
                        msg=f"❌ Arquivo não encontrado: {str(error)}")
    else:
        sender.send_text(number=msg.remote_jid, 
                        msg=f"❌ Erro no processamento: {str(error)}")

@app.route("/status", methods=['GET'])
def status():
    """Endpoint to check system status"""
    try:
        stats = InstagramSend.get_queue_stats()
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
    """Endpoint to check specific job status"""
    try:
        job = InstagramSend.check_post_status(job_id)
        if job.get("status") == "not_found":
            return jsonify({"error": "Job não encontrado"}), 404
        return jsonify(job)
    except Exception as e:
        print(f"Erro ao verificar job: {str(e)}")
        return jsonify({"error": str(e)}), 500

def disable_firewall():
    """Disable macOS firewall for the app port"""
    try:
        state_command = ["/usr/libexec/ApplicationFirewall/socketfilterfw", "--getglobalstate"]
        result = subprocess.run(state_command, check=True, capture_output=True, text=True)
        if "0" in result.stdout:
            print("Firewall já está desabilitado.")
            return
            
        command = ["sudo", "/usr/libexec/ApplicationFirewall/socketfilterfw", "--setglobalstate", "off"]
        print("Tentando desabilitar o firewall do macOS...")
        subprocess.run(command, check=True, capture_output=True, text=True)
        print("Firewall desabilitado com sucesso.")
    except subprocess.CalledProcessError as e:
        print(f"Falha ao configurar firewall: {e.stderr}")

def ensure_dependencies():
    """Ensure all required dependencies are installed"""
    try:
        print("Dependências já instaladas.")
    except ImportError:
        print("Instalando dependências necessárias...")
        subprocess.run(["pip", "install", "psutil"], check=True)
        print("Dependências instaladas.")

def start_periodic_cleanup(temp_dir, interval_seconds=3600):
    """Start periodic cleanup of temp directories"""
    def cleanup_task():
        while True:
            image_temp_dir = os.path.join(temp_dir, "temp")
            video_temp_dir = os.path.join(temp_dir, "temp_videos")

            os.makedirs(image_temp_dir, exist_ok=True)
            os.makedirs(video_temp_dir, exist_ok=True)

            FilterImage.clean_temp_directory(image_temp_dir)
            time.sleep(interval_seconds)

    cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
    cleanup_thread.start()

@app.route("/debug/carousel/clear", methods=['POST'])
def clear_carousel_cache():
    """Clear carousel state"""
    try:
        global is_carousel_mode, carousel_images, carousel_start_time, carousel_caption
        prev_state = {
            "was_carousel_mode": is_carousel_mode,
            "image_count": len(carousel_images)
        }
        
        is_carousel_mode = False
        carousel_images = []
        carousel_caption = ""
        carousel_start_time = 0
        
        return jsonify({
            "status": "success", 
            "message": "Carousel state cleared",
            "previous_state": prev_state
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e),
            "traceback": traceback.format_exc()
        }), 500

@app.route("/debug/carousel/status", methods=['GET'])
def get_carousel_status():
    """Get carousel debug status"""
    try:
        return jsonify({
            "is_carousel_mode": is_carousel_mode,
            "image_count": len(carousel_images),
            "image_paths": carousel_images if len(carousel_images) < 10 else "Too many to display",
            "caption": carousel_caption,
            "time_in_mode": time.time() - carousel_start_time if carousel_start_time > 0 else 0,
            "timeout_seconds": CAROUSEL_TIMEOUT,
            "will_timeout_in": CAROUSEL_TIMEOUT - (time.time() - carousel_start_time) if carousel_start_time > 0 else "N/A"
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e),
            "traceback": traceback.format_exc()
        }), 500

@app.route('/debug/storage-status', methods=['GET'])
def storage_status():
    """
    Debug endpoint to check storage usage and system status.
    
    Returns detailed information about:
    - Current storage usage
    - File counts and types
    - Resource age statistics
    - System performance metrics
    """
    try:
        usage = resource_manager.monitor_disk_usage()
        return jsonify(usage), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    ensure_dependencies()
    disable_firewall()
    
    try:
        from setup_border import create_border_image
        border_image_path = create_border_image()
        print(f"Using border image: {border_image_path}")
    except Exception as e:
        print(f"Warning: Could not create border image: {str(e)}")
    
    temp_dir = Paths.TEMP
    start_periodic_cleanup(temp_dir)

    if not os.environ.get('WERKZEUG_RUN_MAIN'):
        monitor_thread = start_monitoring_server()
        if monitor_thread:
            print("Sistema de monitoramento iniciado na porta 6002")
        else:
            print("Monitor já está rodando ou não foi possível iniciar")

    try:
        # Get port from environment variable or use default
        port = int(os.environ.get('PORT', 5001))
        max_port_attempts = 10
        
        # Try ports until we find an available one
        for port_attempt in range(port, port + max_port_attempts):
            try:
                app.run(host='0.0.0.0', port=port_attempt, debug=True)
                break
            except OSError as e:
                if port_attempt < port + max_port_attempts - 1:
                    logger.warning(f"Port {port_attempt} is in use, trying {port_attempt + 1}")
                    continue
                else:
                    raise e
    finally:
        cleanup_scheduler.stop()
