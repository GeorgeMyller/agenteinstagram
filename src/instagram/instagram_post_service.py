import os
import time
import json
import random
import re
import requests
from dotenv import load_dotenv
from datetime import datetime, timedelta

class InstagramPostService:
    load_dotenv()

    def __init__(self):
        # Core account configuration
        self.instagram_account_id = os.getenv("INSTAGRAM_ACCOUNT_ID")
        if not self.instagram_account_id:
            raise ValueError("INSTAGRAM_ACCOUNT_ID não configurado")
            
        self.access_token = os.getenv('INSTAGRAM_API_KEY')
        if not self.access_token:
            raise ValueError("INSTAGRAM_API_KEY não configurado")
            
        self.base_url = f'https://graph.facebook.com/v22.0/{self.instagram_account_id}'
        
        # Rate limiting and retry settings
        self.max_retries = 3
        self.base_delay = 5  # Base delay in seconds between retries
        self.state_file = 'api_state.json'
        self.container_cache = {}  # Cache for container IDs
        
        # Rate limit tracking
        self.last_request_time = 0
        self.min_request_interval = 2  # Minimum seconds between requests
        self.rate_limit_window = {}  # Track rate limits per endpoint
        
        # Load previous state if available
        self._load_state()
        
        # Validate token before proceeding
        self._validate_token()

    def _validate_token(self):
        """Valida o token de acesso antes de fazer requisições."""
        url = f"https://graph.facebook.com/v22.0/debug_token"
        params = {
            "input_token": self.access_token,
            "access_token": self.access_token
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if 'data' in data and data['data'].get('is_valid'):
                print("Token de acesso validado com sucesso.")
                
                # Verificar se tem permissão para publicar
                if 'instagram_basic' not in data['data'].get('scopes', []) or \
                   'instagram_content_publish' not in data['data'].get('scopes', []):
                    print("Token pode não ter permissões para publicar. Verifique se as permissões 'instagram_basic' e 'instagram_content_publish' estão habilitadas.")
            else:
                print("Token de acesso inválido ou expirado.")
                raise ValueError("Token de acesso inválido ou expirado.")
        except Exception as e:
            print(f"Erro ao validar token: {e}")
            raise ValueError("Erro ao validar token.")

    def _load_state(self):
        """Load previous API state if available"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    if 'container_cache' in state:
                        # Convert timestamps back to numeric values
                        for key, data in state['container_cache'].items():
                            if 'timestamp' in data:
                                data['timestamp'] = float(data['timestamp'])
                        self.container_cache = state['container_cache']
                    if 'rate_limit_window' in state:
                        self.rate_limit_window = state['rate_limit_window']
        except Exception as e:
            print(f"Failed to load API state: {str(e)}")

    def _save_state(self):
        """Save current API state for future use"""
        try:
            state = {
                'container_cache': self.container_cache,
                'rate_limit_window': self.rate_limit_window
            }
            with open(self.state_file, 'w') as f:
                json.dump(state, f)
        except Exception as e:
            print(f"Failed to save API state: {str(e)}")

    def _handle_error_response(self, response_data):
        """
        Handle different types of Instagram API errors
        Returns: (should_retry, retry_delay, error_msg)
        """
        if 'error' not in response_data:
            return False, 0, "Unknown error occurred"

        error = response_data['error']
        error_code = error.get('code')
        error_subcode = error.get('error_subcode')
        error_msg = error.get('message', 'Unknown error')
        
        print(f"API Error: Code {error_code}, Subcode {error_subcode}, Message: {error_msg}")
        
        # Authentication errors
        if error_code in [190, 104]:
            return False, 0, f"Authentication error: {error_msg}"
        
        # Permission errors
        elif error_code in [200, 10, 803]:
            return False, 0, f"Permission error: {error_msg}"
        
        # Rate limit errors - retry after delay
        elif error_code in [4, 17, 32, 613]:
            # For Application request limit (code 4), use longer backoff
            if error_code == 4:
                wait_time = 120  # Default 2 minutes for rate limits
                if error_subcode == 2207051:  # Application request limit 
                    wait_time = 180  # 3 minutes
                
                # Record the rate limit in our tracking
                endpoint = "general"  # Default endpoint bucket
                self.rate_limit_window[endpoint] = int(time.time()) + wait_time
                self._save_state()
            else:
                wait_time = 60  # Default 1 minute
            
            # Try to extract time from message if available
            if 'minutes' in error_msg.lower():
                try:
                    time_match = re.search(r'(\d+)\s*minutes?', error_msg.lower())
                    if time_match:
                        wait_time = int(time_match.group(1)) * 60
                except:
                    pass
            return True, wait_time, f"Rate limit hit. Waiting {wait_time} seconds."
        
        # Media format errors
        elif error_code == 2207026:
            return False, 0, f"Media format error: {error_msg}"
        
        # Server errors - usually temporary
        elif error_code in [1, 2] or 'OAuthException' in str(error):
            return True, 30, f"Temporary server error: {error_msg}"
        
        # Handle other common errors
        if error_code == 100 and "nonexisting field (permalink)" in error_msg:
            return True, 20, "Permalink not available yet"
        
        # For other errors, we'll retry once
        return True, 15, f"API error: {error_msg}"

    def _respect_rate_limits(self, endpoint="general"):
        """Respect rate limits by waiting if needed"""
        # Check if we're in a rate limit window for this endpoint
        current_time = int(time.time())
        if endpoint in self.rate_limit_window and self.rate_limit_window[endpoint] > current_time:
            wait_time = self.rate_limit_window[endpoint] - current_time
            print(f"Respecting rate limit for {endpoint}. Waiting {wait_time} seconds...")
            time.sleep(wait_time)
            return
        
        # Ensure minimum time between requests
        elapsed = current_time - self.last_request_time
        if elapsed < self.min_request_interval:
            sleep_time = self.min_request_interval - elapsed
            print(f"Respecting minimum interval. Waiting {sleep_time} seconds...")
            time.sleep(sleep_time)
        
        self.last_request_time = int(time.time())

    def _make_request_with_retry(self, method, url, payload, endpoint="general"):
        """
        Make API request with retry logic and rate limit handling
        """
        last_error = None
        
        for attempt in range(self.max_retries):
            # Respect rate limits before making request
            self._respect_rate_limits(endpoint)
            
            try:
                print(f"Making request to: {url}")
                print(f"Payload: {payload}")
                
                response = method(url, data=payload)
                response_data = response.json()
                
                print(f"API response: {response_data}")
                
                # Check for errors
                if 'error' in response_data:
                    should_retry, retry_delay, error_msg = self._handle_error_response(response_data)
                    last_error = error_msg
                    
                    if should_retry and attempt < self.max_retries - 1:
                        delay = self.base_delay * (2 ** attempt)
                        delay = max(delay, retry_delay)
                        print(f"Attempt {attempt + 1} failed. Retrying in {delay} seconds...")
                        time.sleep(delay)
                        continue
                    elif not should_retry:
                        print(f"Non-recoverable error: {error_msg}")
                        return None
                
                # Success
                return response_data
                
            except requests.exceptions.RequestException as e:
                last_error = str(e)
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2 ** attempt)
                    print(f"Request failed: {str(e)}. Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    print(f"All retry attempts failed: {str(e)}")
        
        if last_error:
            print(f"Error: {last_error}")
        return None

    def create_media_container(self, image_url, caption):
        """
        Creates a media container for the post with basic retry logic.
        """
        # Check container cache first
        cache_key = f"{image_url}:{caption[:50]}"
        if cache_key in self.container_cache and time.time() - self.container_cache[cache_key]['timestamp'] < 3600:
            container_id = self.container_cache[cache_key]['id']
            print(f"Reusing cached container ID: {container_id}")
            return container_id
        
        url = f'{self.base_url}/media'
        payload = {
            'image_url': image_url,
            'caption': caption,
            'access_token': self.access_token
        }
        
        response_data = self._make_request_with_retry(requests.post, url, payload, "media_create")
        if response_data and 'id' in response_data:
            container_id = response_data['id']
            print(f"Media container created with ID: {container_id}")
            
            # Cache the container ID
            self.container_cache[cache_key] = {
                'id': container_id,
                'timestamp': time.time()
            }
            self._save_state()
            
            return container_id
        return None

    def verify_media_status(self, media_id, max_attempts=5, delay=30):
        """
        Verify if a media post exists and is published with enhanced error handling.
        """
        known_status = {
            'PUBLISHED': True,
            'FINISHED': True,
            'IN_PROGRESS': None,  # Still processing
            'ERROR': False,
            'EXPIRED': False,
            'SCHEDULED': None  # Wait for scheduled time
        }
        
        for attempt in range(max_attempts):
            if attempt > 0:
                wait_time = delay * (1.5 ** attempt)  # Exponential backoff
                print(f"Checking status (attempt {attempt + 1}/{max_attempts}), waiting {int(wait_time)} seconds...")
                time.sleep(wait_time)
            
            # Respect rate limits
            self._respect_rate_limits("media_status")
            
            url = f'https://graph.facebook.com/v22.0/{media_id}'
            params = {
                'access_token': self.access_token,
                'fields': 'id,status_code,status,permalink'
            }
            
            try:
                print(f"Checking status for media ID: {media_id}")
                response = requests.get(url, params=params)
                data = response.json()
                
                if 'error' in data:
                    error = data['error']
                    error_code = error.get('code')
                    error_msg = error.get('message', 'Unknown error')
                    print(f"Error checking status: {error_msg} (Code: {error_code})")
                    
                    # Handle specific error cases
                    if error_code == 4:  # Rate limit
                        wait_time = delay * 2
                        print(f"Rate limit hit, waiting {wait_time} seconds...")
                        time.sleep(wait_time)
                        continue
                    elif error_code == 100:  # Invalid parameter
                        if "Page ID" in error_msg:
                            print("Media might have been deleted or never existed")
                            return False
                    
                    # For other errors, continue trying
                    continue
                
                if 'id' in data:
                    status = data.get('status_code') or data.get('status', 'UNKNOWN')
                    print(f"Post status: {status}")
                    
                    # Check if we have a permalink (usually means post is live)
                    if data.get('permalink'):
                        print(f"Post is live with permalink: {data['permalink']}")
                        return True
                    
                    # Handle known status
                    if status in known_status:
                        result = known_status[status]
                        if result is not None:  # We have a definitive answer
                            return result
                        # For None results (like IN_PROGRESS), we continue waiting
                        print(f"Post is still processing (status: {status})")
                        continue
                    
                    # For unknown status, if we have an ID and no error, assume success
                    if attempt == max_attempts - 1:
                        print(f"Unknown status '{status}' but post ID exists")
                        return True
                
            except Exception as e:
                print(f"Error checking status: {str(e)}")
                if attempt == max_attempts - 1:
                    print("Max retries reached with errors")
                    return False
                
        print("Could not confirm post status after maximum attempts")
        return False

    def publish_media(self, media_container_id):
        """
        Publishes the media container to Instagram with enhanced verification.
        """
        # Initial stabilization wait
        wait_time = 30  # Longer initial wait to ensure container is ready
        print(f"Waiting {wait_time} seconds for container processing...")
        time.sleep(wait_time)
        
        # First verify if the container is ready
        if not self.verify_media_status(media_container_id, max_attempts=3, delay=20):
            print("Media container not ready for publishing")
            return None
        
        url = f'{self.base_url}/media_publish'
        payload = {
            'creation_id': media_container_id,
            'access_token': self.access_token
        }
        
        response_data = self._make_request_with_retry(requests.post, url, payload, "media_publish")
        
        if not response_data:
            print("Failed to get response from publish endpoint")
            # Check if it was published anyway
            if self.verify_media_status(media_container_id, max_attempts=4, delay=45):
                print("Post was published successfully despite API error")
                return media_container_id
            return None
        
        if 'id' in response_data:
            post_id = response_data['id']
            print(f"Publication initiated with ID: {post_id}")
            
            # Give Instagram time to process before verification
            time.sleep(45)
            
            # Verify with new post ID first
            if self.verify_media_status(post_id, max_attempts=4, delay=30):
                print("Post publication confirmed with new ID!")
                return post_id
            
            # If that fails, try with original container ID
            if post_id != media_container_id:
                print("Trying verification with original container ID...")
                if self.verify_media_status(media_container_id, max_attempts=3, delay=30):
                    print("Post publication confirmed with container ID!")
                    return media_container_id
        
        print("Could not confirm post publication")
        return None

    def post_image(self, image_url, caption):
        """
        Handles the full flow of creating and publishing an Instagram post with enhanced error handling.
        """
        print("Starting Instagram image publication...")

        media_container_id = self.create_media_container(image_url, caption)
        if not media_container_id:
            print("Failed to create media container.")
            return None

        # Add a delay for container stabilization
        wait_time = 45  # Increased initial wait time
        print(f"Waiting {wait_time} seconds for container stabilization...")
        time.sleep(wait_time)

        # Verify container before attempting to publish
        print("Verifying media container...")
        if not self.verify_media_status(media_container_id, max_attempts=3, delay=20):
            print("Media container verification failed")
            return None

        post_id = self.publish_media(media_container_id)
        if post_id:
            print(f"Process completed successfully! Post ID: {post_id}")
            return post_id

        print("Final verification of post status...")
        time.sleep(60)  # Extended wait for final check
        
        # One last verification attempt with longer delays
        if self.verify_media_status(media_container_id, max_attempts=3, delay=45):
            print("Post verified and confirmed on Instagram!")
            return media_container_id

        print("Could not confirm post publication after multiple attempts.")
        return None

