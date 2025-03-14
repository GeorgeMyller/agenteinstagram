from flask import Flask, request, jsonify
import logging
from src.services.message import Message
from src.utils.config import Config
from src.utils.cleanup_scheduler import CleanupScheduler
from src.utils.resource_manager import ResourceManager
import os
import tempfile
import base64

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
        # Extract image data
        image_data = message.data.get("message", {}).get("imageMessage", {})
        image_base64 = image_data.get("base64")
        caption = image_data.get("caption", "")
        
        if not image_base64:
            logger.error("No image data found in message")
            return {"type": "image", "status": "error", "message": "No image data found"}
        
        # Save image to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
            temp_file.write(base64.b64decode(image_base64))
            temp_path = temp_file.name
        
        try:
            # Import and use InstagramSend to post the image
            from src.instagram.instagram_send import InstagramSend
            result = InstagramSend.send_instagram(temp_path, caption)
            
            if result and result.get("status") == "success":
                logger.info(f"Image posted successfully to Instagram with ID: {result.get('id')}")
                return {
                    "type": "image", 
                    "status": "success", 
                    "message": "Image posted successfully",
                    "post_id": result.get("id")
                }
            else:
                error_msg = result.get("message") if result else "Unknown error"
                logger.error(f"Failed to post image: {error_msg}")
                return {
                    "type": "image", 
                    "status": "error", 
                    "message": f"Failed to post image: {error_msg}"
                }
        except Exception as e:
            logger.error(f"Error posting image to Instagram: {str(e)}")
            return {"type": "image", "status": "error", "message": str(e)}
        finally:
            # Clean up the temporary file
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    except Exception as e:
        logger.error(f"Error processing image message: {str(e)}")
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
        # Run the Flask app (WSGI mode)
        app.run(host='0.0.0.0', port=5001, debug=True)
    finally:
        cleanup_scheduler.stop()

# ASGI adapter for running with uvicorn (or similar command)
# When using "uvicorn app:asgi_app", the ASGI adapter will enable the Flask app to run.
from asgiref.wsgi import WsgiToAsgi
asgi_app = WsgiToAsgi(app)