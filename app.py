import os
import logging
from typing import Dict, Any, List, Optional
from flask import Flask, request, jsonify
from datetime import datetime

from src.services.message import Message
from src.utils.image_decode_save import ImageDecodeSaver
from src.utils.video_decode_save import VideoDecodeSaver
from src.utils.monitor import ApiMonitor
from src.utils.config import ConfigManager
from src.utils.error_handler import error_handler, init_error_handlers
from src.instagram.instagram_facade import InstagramFacade
from src.instagram.image_validator import InstagramImageValidator
from src.services.send import sender

app = Flask(__name__)
monitor = ApiMonitor()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize error handlers
init_error_handlers(app)

# Initialize configuration
config = ConfigManager()
config_file_path = os.path.join(os.path.dirname(__file__), 'config.json')
if os.path.exists(config_file_path):
    config.load_file(config_file_path)
    logger.info(f"Loaded configuration from {config_file_path}")
config.load_env()

# Load Instagram API credentials
access_token = os.getenv('INSTAGRAM_API_KEY')
ig_user_id = os.getenv('INSTAGRAM_ACCOUNT_ID')

if not access_token or not ig_user_id:
    raise ValueError("Instagram API key and account ID must be configured")

# Initialize facade
instagram = InstagramFacade(access_token, ig_user_id)
image_validator = InstagramImageValidator()

# Global carousel state
is_carousel_mode = False
carousel_images = []
carousel_start_time = 0
carousel_caption = ""

@app.route('/health', methods=['GET'])
@error_handler
def health_check():
    """Health check endpoint"""
    health = monitor.check_health()
    stats = instagram.get_queue_stats()
    
    return jsonify({
        'status': 'healthy',
        'api_health': health,
        'queue_stats': stats,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/post/image', methods=['POST'])
@error_handler
def queue_image_post():
    """Queue a single image post"""
    data = request.get_json()
    if not data:
        return jsonify({'status': 'error', 'message': 'No data provided'}), 400
    
    image_path = data.get('image_path')
    caption = data.get('caption')
    
    if not image_path:
        return jsonify({'status': 'error', 'message': 'image_path is required'}), 400
    
    try:
        container_id = instagram.queue_post(image_path, caption)
        return jsonify({
            'status': 'success',
            'message': 'Post queued successfully',
            'container_id': container_id
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/post/carousel', methods=['POST'])
@error_handler
def queue_carousel_post():
    """Queue a carousel post"""
    data = request.get_json()
    if not data:
        return jsonify({'status': 'error', 'message': 'No data provided'}), 400
    
    image_paths = data.get('image_paths', [])
    caption = data.get('caption')
    
    if not image_paths:
        return jsonify({'status': 'error', 'message': 'image_paths is required'}), 400
    
    try:
        container_id = instagram.queue_carousel(image_paths, caption)
        return jsonify({
            'status': 'success',
            'message': 'Carousel queued successfully',
            'container_id': container_id
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/post/reel', methods=['POST'])
@error_handler
def queue_reel_post():
    """Queue a reel post"""
    data = request.get_json()
    if not data:
        return jsonify({'status': 'error', 'message': 'No data provided'}), 400
    
    video_path = data.get('video_path')
    caption = data.get('caption')
    share_to_feed = data.get('share_to_feed', True)
    
    if not video_path:
        return jsonify({'status': 'error', 'message': 'video_path is required'}), 400
    
    try:
        container_id = instagram.queue_reels(video_path, caption, share_to_feed)
        return jsonify({
            'status': 'success',
            'message': 'Reel queued successfully',
            'container_id': container_id
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/post/status/<container_id>', methods=['GET'])
@error_handler
def check_post_status(container_id):
    """Check status of a queued post"""
    status = instagram.get_container_status(container_id)
    if not status:
        return jsonify({
            'status': 'error',
            'message': 'Container not found'
        }), 404
    
    return jsonify({
        'status': 'success',
        'container_status': status
    })

@app.route('/monitor/stats', methods=['GET'])
@error_handler
def get_monitor_stats():
    """Get API monitoring statistics"""
    stats = monitor.get_stats()
    queue_stats = instagram.get_queue_stats()
    recent_posts = instagram.get_recent_posts(5)
    
    return jsonify({
        'status': 'success',
        'monitor_stats': stats,
        'queue_stats': queue_stats,
        'recent_posts': recent_posts
    })

@app.route('/messages-upsert', methods=['POST'])
@error_handler
def messages_upsert():
    """Handle webhook message upsert requests"""
    global is_carousel_mode, carousel_images, carousel_start_time, carousel_caption
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'No data provided'}), 400

        msg = Message(data)
        texto = msg.get_text()
        
        # Group validation
        if msg.scope == Message.SCOPE_GROUP:
            if str(msg.group_id) != "120363383673368986":
                return jsonify({"status": "processed, but ignored"}), 200

        # Handle carousel mode
        if texto and texto.lower().startswith("carrossel"):
            is_carousel_mode = True
            carousel_images = []
            carousel_caption = texto[9:].strip()
            carousel_start_time = datetime.now().timestamp()
            
            sender.send_text(
                number=msg.remote_jid,
                msg="🎠 Modo carrossel ativado! Envie as imagens (2-10) e use 'postar' quando terminar."
            )
            return jsonify({"status": "Carousel mode activated"}), 200
            
        if is_carousel_mode:
            if msg.message_type == msg.TYPE_IMAGE:
                image_path = ImageDecodeSaver.process(msg.image_base64)
                carousel_images.append(image_path)
                sender.send_text(
                    number=msg.remote_jid,
                    msg=f"✅ Imagem {len(carousel_images)} adicionada ao carrossel."
                )
                return jsonify({"status": "Image added to carousel"}), 200
                
            elif texto and texto.lower() == "postar":
                if len(carousel_images) < 2:
                    sender.send_text(
                        number=msg.remote_jid,
                        msg="⚠️ São necessárias pelo menos 2 imagens para criar um carrossel."
                    )
                    return jsonify({"status": "Not enough images"}), 400
                    
                try:
                    container_id = instagram.queue_carousel(carousel_images, carousel_caption)
                    sender.send_text(
                        number=msg.remote_jid,
                        msg=f"✅ Carrossel enfileirado! ID: {container_id}"
                    )
                    is_carousel_mode = False
                    carousel_images = []
                    carousel_caption = ""
                    return jsonify({"status": "Carousel queued"}), 200
                except Exception as e:
                    sender.send_text(
                        number=msg.remote_jid,
                        msg=f"❌ Erro ao enfileirar carrossel: {str(e)}"
                    )
                    return jsonify({"status": "error", "message": str(e)}), 500

        # Handle single image
        elif msg.message_type == msg.TYPE_IMAGE:
            try:
                image_path = ImageDecodeSaver.process(msg.image_base64)
                caption = msg.image_caption if msg.image_caption else ""
                
                container_id = instagram.queue_post(image_path, caption)
                sender.send_text(
                    number=msg.remote_jid,
                    msg=f"✅ Imagem enfileirada! ID: {container_id}"
                )
                return jsonify({"status": "success", "container_id": container_id}), 200
            except Exception as e:
                sender.send_text(
                    number=msg.remote_jid,
                    msg=f"❌ Erro ao processar imagem: {str(e)}"
                )
                return jsonify({"status": "error", "message": str(e)}), 500

        # Handle video/reels
        elif msg.message_type == msg.TYPE_VIDEO:
            try:
                video_path = VideoDecodeSaver.process(msg.video_base64)
                caption = msg.video_caption if msg.video_caption else ""
                
                container_id = instagram.queue_reels(video_path, caption)
                sender.send_text(
                    number=msg.remote_jid,
                    msg=f"✅ Vídeo enfileirado! ID: {container_id}"
                )
                return jsonify({"status": "success", "container_id": container_id}), 200
            except Exception as e:
                sender.send_text(
                    number=msg.remote_jid,
                    msg=f"❌ Erro ao processar vídeo: {str(e)}"
                )
                return jsonify({"status": "error", "message": str(e)}), 500

    except Exception as e:
        logger.error(f"Error in webhook: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

    return jsonify({"status": "processed"}), 200

if __name__ == '__main__':
    # Start monitoring
    monitor.start()
    
    try:
        port = int(os.environ.get('PORT', 5001))
        app.run(host='0.0.0.0', port=port)
    finally:
        monitor.stop()