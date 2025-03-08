import os
import time
import json
import random
import re
import requests
from dotenv import load_dotenv

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
        
        # Basic retry and rate limit settings
        self.max_retries = 3
        self.base_delay = 5  # Base delay in seconds between retries
        self.state_file = 'api_state.json'
        self.container_cache = {}  # Cache for container IDs

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
            wait_time = 60  # Default 1 minute
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

    def _make_request_with_retry(self, method, url, payload):
        """
        Make API request with basic retry logic
        """
        last_error = None
        
        for attempt in range(self.max_retries):
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
        
        response_data = self._make_request_with_retry(requests.post, url, payload)
        if response_data and 'id' in response_data:
            container_id = response_data['id']
            print(f"Media container created with ID: {container_id}")
            
            # Cache the container ID
            self.container_cache[cache_key] = {
                'id': container_id,
                'timestamp': time.time()
            }
            
            return container_id
        return None

    def verify_media_status(self, media_id, max_attempts=3, delay=20):
        """
        Verify if a media post exists and is published.
        """
        for attempt in range(max_attempts):
            if attempt > 0:
                print(f"Checking status (attempt {attempt + 1}/{max_attempts})...")
                time.sleep(delay)
            
            url = f'https://graph.facebook.com/v22.0/{media_id}'
            params = {
                'access_token': self.access_token,
                'fields': 'id,status_code,status'
            }
            
            try:
                response = requests.get(url, params=params)
                data = response.json()
                
                if 'error' in data:
                    print(f"Error checking status: {data['error'].get('message', 'Unknown error')}")
                    continue
                
                if 'id' in data:
                    status = data.get('status_code') or data.get('status')
                    if status in ('FINISHED', 'PUBLISHED'):
                        print(f"Post found with status: {status}")
                        return True
                    else:
                        print(f"Post status: {status}")
            except Exception as e:
                print(f"Error checking status: {str(e)}")
                
        return False

    def publish_media(self, media_container_id):
        """
        Publishes the media container to Instagram.
        """
        # Wait for container processing
        time.sleep(10)
        
        url = f'{self.base_url}/media_publish'
        payload = {
            'creation_id': media_container_id,
            'access_token': self.access_token
        }
        
        response_data = self._make_request_with_retry(requests.post, url, payload)
        
        # If normal publish failed, check if it was actually published anyway
        if not response_data or 'id' not in response_data:
            print("Publish request failed, checking if post was published anyway...")
            if self.verify_media_status(media_container_id):
                print("Post was published successfully despite API error")
                return media_container_id
            return None
            
        post_id = response_data['id']
        print(f"Publication initiated with ID: {post_id}")
        
        # Verify the post status
        if self.verify_media_status(post_id):
            print("Post publication confirmed!")
            return post_id
            
        # Try with original container ID if post_id verification fails
        if media_container_id != post_id and self.verify_media_status(media_container_id):
            print("Post publication confirmed with container ID!")
            return media_container_id
            
        print("Could not confirm post publication")
        return None

    def post_image(self, image_url, caption):
        """
        Handles the full flow of creating and publishing an Instagram post.
        """
        print("Starting Instagram image publication...")

        media_container_id = self.create_media_container(image_url, caption)
        if not media_container_id:
            print("Failed to create media container.")
            return None

        # Add a small delay for container stabilization
        wait_time = random.randint(15, 30)
        print(f"Waiting {wait_time} seconds for container stabilization...")
        time.sleep(wait_time)

        post_id = self.publish_media(media_container_id)
        if post_id:
            print(f"Process completed successfully! Post ID: {post_id}")
            return post_id

        print("Final verification of post status...")
        time.sleep(30)
        
        # One last verification attempt
        if self.verify_media_status(media_container_id, max_attempts=2, delay=15):
            print("Post verified and confirmed on Instagram!")
            return media_container_id

        print("Could not confirm post publication after multiple attempts.")
        return None

