from flask import Flask, request, jsonify
import logging
from src.services.message import Message
from src.utils.config import Config
from src.utils.cleanup_scheduler import CleanupScheduler
from src.utils.resource_manager import ResourceManager
import os
import tempfile
import base64
from src.instagram.image_validator import InstagramImageValidator
from src.utils.image_decode_save import ImageDecodeSaver

# Configure logging with detailed format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Initialize configuration and resource management
config = Config.get_instance()
resource_manager = ResourceManager()
cleanup_scheduler = CleanupScheduler.get_instance()

def _handle_text_message(message: Message):
    """Processes a text message"""
    # ...existing code...
    logger.info("Handling text message")
    return {"type": "text", "content": message.data.get("message", {}).get("content", "")}

def _handle_image_message(message: Message):
    """Processes an image message and posts it to Instagram"""
    logger.info("Handling image message")
    try:
        # Use the attributes already processed by the Message class
        image_base64 = message.image_base64
        caption = message.image_caption or ""
        
        if not image_base64:
            logger.error("No image data found in message")
            return {"type": "image", "status": "error", "message": "No image data found"}
            
        # Rest of the function remains the same
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
    # ...existing code...
    logger.info("Handling video message")
    return {"type": "video", "content": message.data.get("message", {}).get("content", "")}

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

# Register initialization: if before_first_request is available, use it;
# otherwise, call the initializer directly.
if hasattr(app, 'before_first_request'):
    app.before_first_request(initialize_app_wrapper)
else:
    initialize_app_wrapper()

@app.route('/messages-upsert', methods=['POST'])
def handle_message():
    """
    Primary endpoint for processing incoming messages.
    
    Handles various message types:
    - Text messages and commands
    - Image uploads with captions
    - Video/reels content
    - Document attachments
    """
    try:
        data = request.json
        logger.info("Message received:")
        
        # Create message object
        message = Message(data)
        
        # Verify if message is from authorized group
        if config.AUTHORIZED_GROUP_ID is None or message.remote_jid != config.AUTHORIZED_GROUP_ID:
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

# ASGI adapter for running with uvicorn (or similar command)
# When using "uvicorn app:asgi_app", the ASGI adapter will enable the Flask app to run.
from asgiref.wsgi import WsgiToAsgi
asgi_app = WsgiToAsgi(app)