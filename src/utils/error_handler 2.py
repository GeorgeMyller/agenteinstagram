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

class InstagramApiError(Exception):
    """Base class for Instagram API errors"""
    def __init__(self, message: str, error_code: int = None):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)

class AuthenticationError(InstagramApiError):
    """Authentication or permission error"""
    pass

class RateLimitError(InstagramApiError):
    """Rate limit exceeded error"""
    pass

class MediaError(InstagramApiError):
    """Media processing or validation error"""
    pass

class BusinessValidationError(InstagramApiError):
    """Business validation error"""
    pass

def error_handler(f: Callable) -> Callable:
    """
    Decorator for consistent error handling
    
    Args:
        f: Function to wrap
        
    Returns:
        Wrapped function with error handling
    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
            
        except AuthenticationError as e:
            logger.error(f"Authentication error: {e.message}")
            return jsonify({
                'status': 'error',
                'error': 'authentication_error',
                'message': e.message,
                'error_code': e.error_code
            }), 401
            
        except RateLimitError as e:
            logger.warning(f"Rate limit error: {e.message}")
            return jsonify({
                'status': 'error',
                'error': 'rate_limit_error',
                'message': e.message,
                'error_code': e.error_code,
                'retry_after': get_retry_after()
            }), 429
            
        except MediaError as e:
            logger.error(f"Media error: {e.message}")
            return jsonify({
                'status': 'error',
                'error': 'media_error',
                'message': e.message,
                'error_code': e.error_code
            }), 400
            
        except BusinessValidationError as e:
            logger.error(f"Business validation error: {e.message}")
            return jsonify({
                'status': 'error',
                'error': 'business_validation_error',
                'message': e.message,
                'error_code': e.error_code
            }), 422
            
        except Exception as e:
            logger.exception("Unexpected error")
            
            # Track error in monitoring
            monitor = ApiMonitor()
            endpoint = request.endpoint or 'unknown'
            monitor.track_error(endpoint, str(e))
            
            return jsonify({
                'status': 'error',
                'error': 'internal_error',
                'message': 'An unexpected error occurred',
                'request_id': generate_request_id()
            }), 500
    
    return wrapper

def init_error_handlers(app: Flask):
    """
    Initialize Flask error handlers
    
    Args:
        app: Flask application instance
    """
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'status': 'error',
            'error': 'not_found',
            'message': 'The requested resource was not found'
        }), 404
    
    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify({
            'status': 'error',
            'error': 'method_not_allowed',
            'message': f'Method {request.method} not allowed for {request.path}'
        }), 405
    
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({
            'status': 'error',
            'error': 'bad_request',
            'message': 'Invalid request parameters'
        }), 400

def get_retry_after() -> int:
    """
    Get retry after time in seconds
    
    Returns:
        int: Seconds to wait before retry
    """
    # Default to 60 seconds
    return 60

def generate_request_id() -> str:
    """
    Generate unique request ID for error tracking
    
    Returns:
        str: Unique request ID
    """
    from uuid import uuid4
    return str(uuid4())

def parse_instagram_error(response: Dict[str, Any]) -> Optional[InstagramApiError]:
    """
    Parse Instagram API error response
    
    Args:
        response: API error response
        
    Returns:
        InstagramApiError if error recognized, None otherwise
    """
    if not response or 'error' not in response:
        return None
        
    error = response['error']
    message = error.get('message', 'Unknown error')
    code = error.get('code')
    
    # Authentication errors
    if code in [190, 10, 200]:
        return AuthenticationError(message, code)
    
    # Rate limit errors
    if code in [4, 613, 17, 32]:
        return RateLimitError(message, code)
    
    # Media errors
    if code in [24, 25, 26, 27, 28]:
        return MediaError(message, code)
    
    # Business validation
    if code in [100, 110, 190]:
        return BusinessValidationError(message, code)
    
    return InstagramApiError(message, code)