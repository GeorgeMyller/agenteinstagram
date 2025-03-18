import os
import sys

# Add the project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, project_root)

from flask import Flask, request, jsonify
from src.services.message import Message
from src.instagram.instagram_send import InstagramSend  # Updated import path
from src.utils.image_decode_save import ImageDecodeSaver
from src.utils.video_decode_save import VideoDecodeSaver
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
from flask import Flask, request, jsonify
import logging

from ..services.message import Message
from ..instagram.instagram_facade import InstagramFacade
from ..utils.config import Config
from ..utils.monitor import ApiMonitor

logger = logging.getLogger(__name__)

@dataclass
class WebhookResponse:
    status: str
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        response = {
            "status": self.status,
            "timestamp": self.timestamp.isoformat()
        }
        if self.message:
            response["message"] = self.message
        if self.data:
            response["data"] = self.data
        return response

@dataclass
class ErrorResponse(WebhookResponse):
    error_code: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        response = super().to_dict()
        if self.error_code or self.error_details:
            response["error"] = {}
            if self.error_code:
                response["error"]["code"] = self.error_code
            if self.error_details:
                response["error"].update(self.error_details)
        return response

app = Flask(__name__)
config = Config.get_instance()
instagram = InstagramFacade()
monitor = ApiMonitor()

def success_response(message: Optional[str] = None, data: Optional[Dict[str, Any]] = None) -> tuple:
    """Create a success response"""
    response = WebhookResponse(
        status="success",
        message=message,
        data=data
    )
    return jsonify(response.to_dict()), 200

def error_response(
    message: str,
    code: int = 400,
    error_code: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> tuple:
    """Create an error response"""
    response = ErrorResponse(
        status="error",
        message=message,
        error_code=error_code,
        error_details=details
    )
    return jsonify(response.to_dict()), code

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
def health_check():
    """Health check endpoint"""
    try:
        api_health = monitor.check_health()
        queue_stats = instagram.get_queue_stats()
        
        return success_response(data={
            "status": "healthy",
            "api_health": api_health,
            "queue_stats": queue_stats,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return error_response(
            message="Health check failed",
            code=500,
            error_code="HEALTH_CHECK_FAILED",
            details={"error": str(e)}
        )

@app.route("/messages-upsert", methods=['POST'])
def handle_webhook():
    """Handle incoming webhook messages"""
    try:
        data = request.get_json()
        if not data:
            return error_response("No data provided", 400)

        # Create message object
        msg = Message(data)
        
        # Verify authorized group
        if msg.scope == Message.SCOPE_GROUP:
            if str(msg.group_id) != config.get_webhook_config().authorized_group_id:
                return success_response("Message processed but ignored (unauthorized group)")

        # Process message
        if msg.message_type == Message.TYPE_TEXT:
            result = instagram.process_text_message(msg)
        elif msg.message_type == Message.TYPE_IMAGE:
            # Process image message using InstagramFacade
            image_path = ImageDecodeSaver.process(msg.content.image_base64)
            caption = msg.content.image_caption or ""
            result = asyncio.run(instagram.post_image(image_path, caption))
        elif msg.message_type == Message.TYPE_VIDEO:
            result = instagram.process_video_message(msg)
        else:
            return error_response(f"Unsupported message type: {msg.message_type}", 400)

        # Handle processing result
        if result.get("success"):
            return success_response(
                message=result.get("message"),
                data=result.get("data")
            )
        else:
            return error_response(
                message=result.get("error"),
                code=result.get("code", 400),
                error_code=result.get("error_code"),
                details=result.get("details")
            )

    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return error_response(
            message="Internal server error",
            code=500,
            error_code="INTERNAL_ERROR",
            details={"error": str(e)}
        )

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

if __name__ == '__main__':
    monitor.start()
    try:
        app.run(host='0.0.0.0', port=5001)
    finally:
        monitor.stop()