"""
Error Handler Middleware

Provides consistent error handling and logging across the application.
Handles common Instagram API errors and rate limiting.
"""

import logging
import functools
from typing import Callable, Dict, Any, Optional
from flask import Flask, jsonify, request
import traceback
from datetime import datetime

from .monitor import ApiMonitor

logger = logging.getLogger(__name__)

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Type
import functools
import logging
import traceback
from datetime import datetime
from flask import Flask, request, jsonify

logger = logging.getLogger(__name__)

@dataclass
class ErrorInfo:
    """Information about an error occurrence"""
    timestamp: datetime
    error_type: str
    message: str
    endpoint: Optional[str] = None
    request_data: Optional[dict] = None
    traceback: Optional[str] = None

@dataclass
class ErrorStats:
    """Error occurrence statistics"""
    error_count: int = 0
    errors_by_type: Dict[str, int] = field(default_factory=dict)
    recent_errors: List[ErrorInfo] = field(default_factory=list)
    max_recent_errors: int = 50

def error_handler(func):
    """
    Decorator for API route functions to handle exceptions gracefully
    
    Args:
        func: The route function to decorate
        
    Returns:
        Decorated function that catches and handles exceptions
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # Log the error
            logger.exception(f"Error in {func.__name__}: {str(e)}")
            
            # Get request data if available
            req_data = None
            if request:
                if request.is_json:
                    req_data = request.get_json()
                elif request.form:
                    req_data = dict(request.form)
                    
            # Create error info
            error_info = ErrorInfo(
                timestamp=datetime.now(),
                error_type=type(e).__name__,
                message=str(e),
                endpoint=request.endpoint if request else None,
                request_data=req_data,
                traceback=traceback.format_exc()
            )
            
            # Track error stats
            _track_error(error_info)
            
            # Return JSON error response
            return jsonify({
                "status": "error",
                "error": {
                    "type": error_info.error_type,
                    "message": error_info.message
                }
            }), 500
            
    return wrapper

def _track_error(error_info: ErrorInfo) -> None:
    """Track error for statistics"""
    global _error_stats
    
    # Initialize stats if needed
    if not hasattr(error_handler, "_error_stats"):
        error_handler._error_stats = ErrorStats()
    
    stats = error_handler._error_stats
    
    # Update counts
    stats.error_count += 1
    error_type = error_info.error_type
    stats.errors_by_type[error_type] = stats.errors_by_type.get(error_type, 0) + 1
    
    # Add to recent errors
    stats.recent_errors.append(error_info)
    
    # Trim if needed
    if len(stats.recent_errors) > stats.max_recent_errors:
        stats.recent_errors = stats.recent_errors[-stats.max_recent_errors:]

def get_error_stats() -> Dict[str, Any]:
    """Get current error statistics"""
    if not hasattr(error_handler, "_error_stats"):
        error_handler._error_stats = ErrorStats()
        
    stats = error_handler._error_stats
    
    # Convert to serializable dict
    return {
        "total_errors": stats.error_count,
        "errors_by_type": stats.errors_by_type,
        "recent_errors": [
            {
                "timestamp": err.timestamp.isoformat(),
                "type": err.error_type,
                "message": err.message,
                "endpoint": err.endpoint
            }
            for err in stats.recent_errors
        ]
    }

def init_error_handlers(app: Flask) -> None:
    """
    Initialize error handlers for Flask app
    
    Args:
        app: Flask application instance
    """
    # Handle 404 errors
    @app.errorhandler(404)
    def not_found_error(e):
        return jsonify({
            "status": "error",
            "error": {
                "type": "NotFoundError",
                "message": "The requested resource was not found"
            }
        }), 404
    
    # Handle 405 errors
    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({
            "status": "error",
            "error": {
                "type": "MethodNotAllowedError",
                "message": "The method is not allowed for the requested URL"
            }
        }), 405
    
    # Handle 500 errors
    @app.errorhandler(500)
    def server_error(e):
        logger.error(f"Server error: {str(e)}")
        return jsonify({
            "status": "error",
            "error": {
                "type": "ServerError",
                "message": "An internal server error occurred"
            }
        }), 500