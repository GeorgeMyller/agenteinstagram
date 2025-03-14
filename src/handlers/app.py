import os
import sys

# Add the project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, project_root)

from flask import Flask, request, jsonify
from src.services.message import Message
from src.services.instagram_send import InstagramSend
from src.utils.image_decode_save import ImageDecodeSaver
from src.utils.video_decode_save import VideoDecodeSaver
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route("/", methods=['GET'])
def index():
    """
    Root endpoint that confirms API is running.
    
    Returns:
        str: Simple status message
        int: HTTP 200 status code
        
    Example:
        GET /
        Response: "Agent Social Media API is running!"
    """
    return "Agent Social Media API is running!", 200

@app.route("/health", methods=['GET'])
def health():
    """
    Health check endpoint for monitoring.
    
    Returns JSON with basic service health information:
    - API status
    - Database connectivity
    - Resource availability
    - Rate limit status
    
    Returns:
        dict: Service health information
        int: HTTP status code
        
    Example Response:
        {
            "status": "ok",
            "details": {
                "api_status": "operational",
                "rate_limits": {
                    "remaining": 95,
                    "reset": "2024-03-12T23:00:00Z"
                }
            }
        }
    """
    return jsonify({"status": "ok"}), 200

@app.route("/messages-upsert", methods=['POST'])
def webhook():
    """
    Primary webhook endpoint for message processing.
    
    Handles incoming messages from messaging platforms:
    - Text messages and commands
    - Image uploads with captions
    - Video/reels content
    - Document attachments
    
    Request Format:
        {
            "data": {
                "message": {
                    "type": "text|image|video|document",
                    "content": "message content",
                    "caption": "optional caption",
                    "metadata": {}
                },
                "sender": {
                    "id": "sender_id",
                    "name": "sender_name"
                }
            }
        }
    
    Response Format:
        {
            "status": "success|error",
            "message": "Status description",
            "data": {
                "processed": true|false,
                "post_id": "instagram_post_id",
                "media_type": "image|video|carousel"
            }
        }
    
    Error Responses:
        400: Invalid request format
        401: Authentication failed
        403: Unauthorized source
        415: Unsupported media type
        429: Rate limit exceeded
        500: Processing error
        
    Examples:
        1. Post a single image:
        POST /messages-upsert
        {
            "data": {
                "message": {
                    "type": "image",
                    "content": "base64_encoded_image",
                    "caption": "My test post"
                }
            }
        }
        
        2. Post a carousel:
        POST /messages-upsert
        {
            "data": {
                "message": {
                    "type": "carousel",
                    "images": ["base64_1", "base64_2"],
                    "caption": "My carousel post"
                }
            }
        }
        
        3. Post a video:
        POST /messages-upsert
        {
            "data": {
                "message": {
                    "type": "video",
                    "content": "base64_encoded_video",
                    "caption": "My video post"
                }
            }
        }
    """
    try:
        data = request.get_json()  
        
        logger.info("Message received")
                
        msg = Message(data)
        texto = msg.get_text()
        
        if msg.scope == Message.SCOPE_GROUP:    
            logger.info(f"Group message: {msg.group_id}")
            
            if str(msg.group_id) == "120363383673368986":
                 
                if msg.message_type == msg.TYPE_IMAGE:
                    image_path = ImageDecodeSaver.process(msg.image_base64)
                    
                    try:
                        result = InstagramSend.send_instagram(image_path, texto)
                        if result:
                            logger.info("Post processed and sent to Instagram")
                            return jsonify({
                                "status": "success",
                                "message": "Post processed successfully",
                                "data": {
                                    "processed": True,
                                    "post_id": result.get("id"),
                                    "media_type": "image"
                                }
                            }), 200
                        else:
                            logger.warning("Could not confirm post status")
                            return jsonify({
                                "status": "error", 
                                "message": "Could not confirm post status"
                            }), 500
                            
                    except Exception as e:
                        logger.error(f"Error sending to Instagram: {str(e)}")
                        return jsonify({
                            "status": "error",
                            "message": f"Instagram posting error: {str(e)}"
                        }), 500
                        
                    finally:
                        # Cleanup temp file
                        if os.path.exists(image_path):
                            try:
                                os.remove(image_path)
                                logger.info(f"Temp file {image_path} deleted")
                            except Exception as e:
                                logger.error(f"Error deleting temp file: {str(e)}")
                                
                elif msg.message_type == msg.TYPE_VIDEO:
                    video_path = VideoDecodeSaver.process(msg.video_base64)
                    
                    try:
                        result = InstagramSend.send_instagram_video(video_path, texto)
                        if result:
                            logger.info("Video processed and sent to Instagram")
                            return jsonify({
                                "status": "success",
                                "message": "Video processed successfully",
                                "data": {
                                    "processed": True,
                                    "post_id": result.get("id"),
                                    "media_type": "video"
                                }
                            }), 200
                        else:
                            logger.warning("Could not confirm video post status")
                            return jsonify({
                                "status": "error",
                                "message": "Could not confirm video post status"
                            }), 500
                            
                    except Exception as e:
                        logger.error(f"Error sending video to Instagram: {str(e)}")
                        return jsonify({
                            "status": "error",
                            "message": f"Instagram video posting error: {str(e)}"
                        }), 500
                        
                    finally:
                        # Cleanup temp file
                        if os.path.exists(video_path):
                            try:
                                os.remove(video_path)
                                logger.info(f"Temp video file {video_path} deleted")
                            except Exception as e:
                                logger.error(f"Error deleting temp video: {str(e)}")
                                
                else:
                    logger.info(f"Unsupported message type: {msg.message_type}")
                    return jsonify({
                        "status": "error",
                        "message": f"Unsupported message type: {msg.message_type}"
                    }), 415
                    
            else:
                logger.info("Message from unauthorized group")
                return jsonify({
                    "status": "error",
                    "message": "Unauthorized group"
                }), 403
                
        return jsonify({
            "status": "success",
            "message": "Message processed"
        }), 200
        
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Processing error: {str(e)}"
        }), 500

@app.route("/queue-stats", methods=['GET'])
def queue_stats():
    """
    Get current API queue and rate limit statistics.
    
    Returns information about:
    - Current queue size
    - Processing rates
    - Error counts
    - Rate limit status
    
    Query Parameters:
        detailed (bool): Include full statistics
        
    Returns:
        dict: Queue statistics and metrics
        int: HTTP status code
        
    Example Response:
        {
            "queue_size": 5,
            "processing_rate": "2.3/min",
            "error_rate": "0.1%",
            "rate_limits": {
                "remaining": 95,
                "reset_time": "2024-03-12T23:00:00Z"
            }
        }
    """
    try:
        stats = InstagramSend.get_queue_stats()
        return jsonify(stats), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/job-status/<job_id>", methods=['GET'])
def job_status(job_id):
    """
    Check status of a specific posting job.
    
    Args:
        job_id: Unique identifier for the post
        
    Returns:
        dict: Current job status and details
        int: HTTP status code
        
    Example Response:
        {
            "status": "completed|failed|processing",
            "progress": 85,
            "error": null,
            "created_at": "2024-03-12T22:15:30Z",
            "completed_at": "2024-03-12T22:15:35Z",
            "post_url": "https://instagram.com/p/..."
        }
    """
    try:
        status = InstagramSend.check_post_status(job_id)
        return jsonify(status), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
        
@app.route("/job-history", methods=['GET'])
def job_history():
    """
    Get history of recent posting jobs.
    
    Query Parameters:
        limit (int): Number of jobs to return (default: 10)
        status (str): Filter by status (optional)
        type (str): Filter by media type (optional)
        
    Returns:
        dict: List of recent jobs and their details
        int: HTTP status code
        
    Example Response:
        {
            "total": 50,
            "returned": 10,
            "jobs": [
                {
                    "id": "job_123",
                    "type": "image",
                    "status": "completed",
                    "created_at": "2024-03-12T22:00:00Z",
                    "post_url": "https://instagram.com/p/..."
                },
                ...
            ]
        }
    """
    try:
        limit = request.args.get('limit', default=10, type=int)
        history = InstagramSend.get_recent_posts(limit)
        return jsonify(history), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500