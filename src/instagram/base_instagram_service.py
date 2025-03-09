import os
import time
import json
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
import random
import math

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('InstagramAPI')

class AuthenticationError(Exception):
    """Raised when there are issues with authentication"""
    def __init__(self, message, error_code=None, error_subcode=None, fbtrace_id=None):
        self.error_code = error_code
        self.error_subcode = error_subcode
        self.fbtrace_id = fbtrace_id
        super().__init__(message)

class PermissionError(Exception):
    """Raised when the app lacks necessary permissions"""
    def __init__(self, message, error_code=None, error_subcode=None, fbtrace_id=None):
        self.error_code = error_code
        self.error_subcode = error_subcode
        self.fbtrace_id = fbtrace_id
        super().__init__(message)

class RateLimitError(Exception):
    """Raised when rate limits are hit"""
    def __init__(self, message, retry_seconds=300, error_code=None, error_subcode=None, fbtrace_id=None):
        self.retry_seconds = retry_seconds
        self.error_code = error_code
        self.error_subcode = error_subcode
        self.fbtrace_id = fbtrace_id
        super().__init__(message)

class MediaError(Exception):
    """Raised when there are issues with the media"""
    def __init__(self, message, error_code=None, error_subcode=None, fbtrace_id=None):
        self.error_code = error_code
        self.error_subcode = error_subcode
        self.fbtrace_id = fbtrace_id
        super().__init__(message)

class TemporaryServerError(Exception):
    """Raised for temporary server issues"""
    def __init__(self, message, error_code=None, error_subcode=None, fbtrace_id=None):
        self.error_code = error_code
        self.error_subcode = error_subcode
        self.fbtrace_id = fbtrace_id
        super().__init__(message)

class InstagramAPIError(Exception):
    """Base class for Instagram API errors"""
    def __init__(self, message, error_code=None, error_subcode=None, fbtrace_id=None):
        self.error_code = error_code
        self.error_subcode = error_subcode
        self.fbtrace_id = fbtrace_id
        super().__init__(message)

class RateLimitHandler:
    """Handles rate limiting with exponential backoff"""
    
    INITIAL_DELAY = 5  # Initial delay in seconds (increased from 2)
    MAX_DELAY = 3600  # Maximum delay in seconds (1 hour)
    MAX_ATTEMPTS = 5  # Maximum retry attempts
    RATE_LIMIT_CODES = [4, 17, 32, 613]  # Extended list of rate limit error codes
    RATE_LIMIT_SUBCODES = [2207051]  # Specific subcode for application request limit
    
    @classmethod
    def is_rate_limit_error(cls, error_code, error_subcode=None):
        """Check if an error is related to rate limiting"""
        if error_code in cls.RATE_LIMIT_CODES:
            if error_subcode is None or error_subcode in cls.RATE_LIMIT_SUBCODES:
                return True
        return False
    
    @classmethod
    def calculate_backoff_time(cls, attempt, base_delay=None):
        """Calculate backoff time with jitter"""
        if base_delay is None:
            base_delay = cls.INITIAL_DELAY
            
        # For application request limit (subcode 2207051), use longer delays
        if attempt == 0:
            delay = 300  # Start with 5 minutes for first attempt
        else:
            delay = min(cls.MAX_DELAY, base_delay * (2 ** attempt))
            
        # Add jitter (±25%) to avoid thundering herd problem
        jitter = random.uniform(0.75, 1.25)
        return delay * jitter

class BaseInstagramService:
    """Base class for Instagram API services with common functionality"""
    
    API_VERSION = "v22.0"  # Latest stable version
    base_url = f"https://graph.facebook.com/{API_VERSION}"
    min_request_interval = 1  # Minimum seconds between requests
    
    def __init__(self, access_token, ig_user_id):
        """Initialize with access token and Instagram user ID"""
        self.access_token = access_token
        self.ig_user_id = ig_user_id
        self.last_request_time = 0
        self.rate_limit_window = {}
        
        # Configure session with retries
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,  # Number of retries for failed requests
            backoff_factor=0.5,  # Factor to apply between attempts
            status_forcelist=[500, 502, 503, 504]  # HTTP status codes to retry on
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
    
    def _make_request(self, method, endpoint, params=None, data=None, headers=None, retry_attempt=0):
        """Make an API request with enhanced rate limiting and error handling"""
        url = f"{self.base_url}/{endpoint}"
        
        # Add access token to params
        if params is None:
            params = {}
        params['access_token'] = self.access_token
        
        # Respect rate limits with minimum interval between requests
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        
        try:
            logger.info(f"Making {method} request to {endpoint}")
            if data:
                logger.info(f"With data: {data}")
            
            response = self.session.request(method, url, params=params, data=data, headers=headers)
            self.last_request_time = time.time()
            
            # Process rate limit headers if present
            if 'x-business-use-case-usage' in response.headers:
                self._process_rate_limit_headers(response.headers)
            
            # Log response status
            logger.info(f"Response status: {response.status_code}")
            
            if response.status_code == 403:
                try:
                    error_json = response.json()
                    if 'error' in error_json:
                        error = error_json['error']
                        error_code = error.get('code')
                        error_subcode = error.get('error_subcode')
                        error_message = error.get('message', '')
                        fb_trace_id = error.get('fbtrace_id')
                        
                        logger.error(f"{error_code} {error_message} (Subcode: {error_subcode})")
                        
                        # Handle application request limit specifically
                        if error_subcode == 2207051:
                            retry_seconds = 300  # Start with 5 minutes
                            if retry_attempt < RateLimitHandler.MAX_ATTEMPTS:
                                backoff_time = RateLimitHandler.calculate_backoff_time(retry_attempt, retry_seconds)
                                logger.warning(f"Application request limit reached. Backing off for {backoff_time:.2f} seconds. Attempt {retry_attempt+1}/{RateLimitHandler.MAX_ATTEMPTS}")
                                time.sleep(backoff_time)
                                return self._make_request(method, endpoint, params, data, headers, retry_attempt + 1)
                            
                        raise RateLimitError(error_message, retry_seconds, error_code, error_subcode, fb_trace_id)
                        
                except ValueError:
                    raise InstagramAPIError("Failed to parse error response")
            
            response.raise_for_status()
            result = response.json() if response.content else None
            
            if result and 'error' in result:
                error = result['error']
                error_code = error.get('code')
                error_message = error.get('message', '')
                error_subcode = error.get('error_subcode')
                fb_trace_id = error.get('fbtrace_id')
                
                if error_code in [190, 104]:  # Token errors
                    raise AuthenticationError(error_message, error_code, error_subcode, fb_trace_id)
                elif error_code in [200, 10, 803]:  # Permission errors
                    raise PermissionError(error_message, error_code, error_subcode, fb_trace_id)
                elif RateLimitHandler.is_rate_limit_error(error_code, error_subcode):
                    retry_seconds = self._get_retry_after(error)
                    if retry_attempt < RateLimitHandler.MAX_ATTEMPTS:
                        backoff_time = RateLimitHandler.calculate_backoff_time(retry_attempt, retry_seconds)
                        logger.warning(f"Rate limit hit. Backing off for {backoff_time:.2f} seconds. Attempt {retry_attempt+1}/{RateLimitHandler.MAX_ATTEMPTS}")
                        time.sleep(backoff_time)
                        return self._make_request(method, endpoint, params, data, headers, retry_attempt + 1)
                    raise RateLimitError(error_message, retry_seconds, error_code, error_subcode, fb_trace_id)
                elif error_code in [1, 2]:  # Temporary server errors
                    raise TemporaryServerError(error_message, error_code, error_subcode, fb_trace_id)
                else:
                    raise InstagramAPIError(error_message, error_code, error_subcode, fb_trace_id)
            
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            raise InstagramAPIError(f"Request failed: {str(e)}")
    
    def _process_rate_limit_headers(self, headers):
        """Process rate limit information from response headers"""
        usage_header = headers.get('x-business-use-case-usage')
        if usage_header:
            try:
                usage_data = json.loads(usage_header)
                for app_id, metrics in usage_data.items():
                    if isinstance(metrics, list) and metrics:
                        rate_data = metrics[0]
                        if 'estimated_time_to_regain_access' in rate_data:
                            self.rate_limit_window[app_id] = time.time() + rate_data['estimated_time_to_regain_access']
            except json.JSONDecodeError:
                logger.warning("Failed to parse rate limit headers")
    
    def _get_retry_after(self, error):
        """Extract retry after time from error response"""
        # Default retry time increased to 5 minutes for application request limit
        retry_seconds = 300
        
        # Check for specific error subcodes
        if error.get('error_subcode') == 2207051:  # Application request limit
            retry_seconds = 900  # 15 minutes
        
        # Try to extract time from error message
        message = error.get('message', '').lower()
        if 'minutes' in message:
            try:
                import re
                time_match = re.search(r'(\d+)\s*minutes?', message)
                if time_match:
                    retry_seconds = int(time_match.group(1)) * 60
            except:
                pass
        
        return retry_seconds

    def check_token_permissions(self):
        """Check if the access token has the necessary permissions"""
        try:
            response = self._make_request('GET', 'debug_token', params={'input_token': self.access_token})
            if not response or 'data' not in response:
                return False, ["Unable to verify token"]
            
            token_data = response['data']
            if not token_data.get('is_valid', False):
                return False, ["Token is invalid or expired"]
            
            scopes = token_data.get('scopes', [])
            required_permissions = ['instagram_basic', 'instagram_content_publish']
            missing = [p for p in required_permissions if p not in scopes]
            
            return len(missing) == 0, missing
            
        except Exception as e:
            logger.error(f"Error checking token permissions: {e}")
            return False, [str(e)]
    
    def get_app_usage_info(self):
        """Get current app usage and rate limit information"""
        try:
            result = requests.get(
                f"{self.base_url}/me",
                params={
                    'access_token': self.access_token,
                    'debug': 'all',
                    'fields': 'id,name'
                }
            )
            
            headers = result.headers
            debug_info = result.json().get('__debug', {})
            
            usage_info = {
                'app_usage': debug_info.get('app_usage', {}),
                'page_usage': debug_info.get('page_usage', {}),
                'headers': {
                    'x-app-usage': headers.get('x-app-usage'),
                    'x-ad-account-usage': headers.get('x-ad-account-usage'),
                    'x-business-use-case-usage': headers.get('x-business-use-case-usage'),
                    'x-fb-api-version': headers.get('facebook-api-version')
                }
            }
            
            return usage_info
        except Exception as e:
            logging.error(f"Error getting usage info: {str(e)}")
            return {'error': str(e)}