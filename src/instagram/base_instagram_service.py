import os
import time
import json
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('InstagramAPI')

class AuthenticationError(Exception):
    """Raised when there are issues with authentication"""
    pass

class PermissionError(Exception):
    """Raised when the app lacks necessary permissions"""
    pass

class RateLimitError(Exception):
    """Raised when rate limits are hit"""
    def __init__(self, message, retry_seconds=300):
        self.retry_seconds = retry_seconds
        super().__init__(message)

class MediaError(Exception):
    """Raised when there are issues with the media"""
    pass

class TemporaryServerError(Exception):
    """Raised for temporary server issues"""
    pass

class InstagramAPIError(Exception):
    """Base class for Instagram API errors"""
    def __init__(self, message, error_code=None, error_subcode=None, fb_trace_id=None):
        self.error_code = error_code
        self.error_subcode = error_subcode
        self.fb_trace_id = fb_trace_id
        super().__init__(message)

class BaseInstagramService:
    """Base class for Instagram API services with common functionality"""
    
    API_VERSION = "v22.0"  # Latest stable version
    
    def __init__(self, access_token, ig_user_id):
        """Initialize with access token and Instagram user ID"""
        self.access_token = access_token
        self.ig_user_id = ig_user_id
        self.base_url = f'https://graph.facebook.com/{self.API_VERSION}'
        
        # Configure session with retries
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        
        # Rate limiting configuration
        self.rate_limit_window = {}
        self.last_request_time = 0
        self.min_request_interval = 1.0  # Minimum seconds between requests
    
    def _make_request(self, method, endpoint, params=None, data=None, headers=None):
        """Make an API request with rate limiting and error handling"""
        url = f"{self.base_url}/{endpoint}"
        
        # Add access token to params
        if params is None:
            params = {}
        params['access_token'] = self.access_token
        
        # Respect rate limits
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        
        try:
            response = self.session.request(method, url, params=params, data=data, headers=headers)
            self.last_request_time = time.time()
            
            # Handle rate limit headers
            if 'x-business-use-case-usage' in response.headers:
                self._process_rate_limit_headers(response.headers)
            
            response.raise_for_status()
            result = response.json() if response.content else None
            
            if result and 'error' in result:
                error = result['error']
                error_code = error.get('code')
                error_message = error.get('message', '')
                error_subcode = error.get('error_subcode')
                fb_trace_id = error.get('fbtrace_id')
                
                if error_code in [190, 104]:
                    raise AuthenticationError(error_message, error_code, error_subcode, fb_trace_id)
                elif error_code in [200, 10, 803]:
                    raise PermissionError(error_message, error_code, error_subcode, fb_trace_id)
                elif error_code in [4, 17, 32, 613]:
                    retry_after = self._get_retry_after(error)
                    raise RateLimitError(error_message, retry_after)
                elif error_code in [1, 2, 4, 17, 341]:
                    raise TemporaryServerError(error_message, error_code, error_subcode, fb_trace_id)
                else:
                    raise InstagramAPIError(error_message, error_code, error_subcode, fb_trace_id)
            
            return result
            
        except requests.exceptions.RequestException as e:
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
        # Default retry time
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