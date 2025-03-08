import os
import time
import json
import random
import re
import requests
from dotenv import load_dotenv
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)  # Consistent logging

class InstagramAPIError(Exception):
    """Base class for Instagram API errors."""
    def __init__(self, message, code=None, subcode=None, fbtrace_id=None):
        super().__init__(message)
        self.code = code
        self.subcode = subcode
        self.fbtrace_id = fbtrace_id

    def __str__(self):
        return f"{super().__str__()} (Code: {self.code}, Subcode: {self.subcode}, Trace ID: {self.fbtrace_id})"

class AuthenticationError(InstagramAPIError):
    """Raised for authentication failures (token expired, invalid, etc.)."""
    pass

class PermissionError(InstagramAPIError):
    """Raised for permission-related errors."""
    pass

class RateLimitError(InstagramAPIError):
    """Raised when rate limits are exceeded."""
    def __init__(self, message, retry_after=300, code=None, subcode=None, fbtrace_id=None):
        super().__init__(message, code, subcode, fbtrace_id)
        self.retry_after = retry_after

class MediaError(InstagramAPIError):
    """Raised for errors related to media (upload, format, etc.)."""
    pass

class TemporaryServerError(InstagramAPIError):
    """Raised for temporary server errors (retryable)."""
    pass


class BaseInstagramService:
    """Base class for common Instagram API functionality."""
    API_VERSION = "v22.0"
    BASE_URL = f"https://graph.facebook.com/{API_VERSION}"

    def __init__(self, access_token, user_id):
        self.access_token = access_token
        self.user_id = user_id
        self.session = requests.Session()  # Use a session for connection pooling
        self.last_request_time = 0
        self.min_request_interval = 1  # Minimum seconds between requests
        self.rate_limit_window = {}  # Track rate limits per endpoint


    def _make_request(self, method, endpoint, params=None, data=None, files=None, retries=3):
        """Makes an API request with retries and error handling."""
        url = f"{self.BASE_URL}/{endpoint}"
        params = params or {}
        params['access_token'] = self.access_token  # Always include access token

        for attempt in range(retries):
            self._respect_rate_limits(endpoint)
            try:
                if method.upper() == "GET":
                    response = self.session.get(url, params=params)
                elif method.upper() == "POST":
                    response = self.session.post(url, params=params, data=data, files=files)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
                data = response.json()

                if 'error' in data:
                    return self._handle_error(data['error'], endpoint, attempt, retries)

                self.last_request_time = time.time()
                return data

            except requests.exceptions.RequestException as e:
                logger.warning(f"Request attempt {attempt + 1} failed: {e}")
                if attempt < retries - 1:
                    sleep_time = self._calculate_retry_delay(attempt)
                    logger.info(f"Retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                else:
                    logger.error(f"Request failed after multiple retries: {e}")
                    raise  # Re-raise the exception after all retries

    def _handle_error(self, error_data, endpoint, attempt, retries):
      """Handles API errors, raising specific exceptions."""
      code = error_data.get('code')
      subcode = error_data.get('error_subcode')
      message = error_data.get('message', 'Unknown error')
      fbtrace_id = error_data.get('fbtrace_id')

      if code in [190, 104]:  # Token expired/invalid
          raise AuthenticationError(message, code, subcode, fbtrace_id)
      elif code in [200, 10, 803]:  # Permission errors
          raise PermissionError(message, code, subcode, fbtrace_id)
      elif code in [4, 17, 32, 613]:  # Rate limit errors
          # Extract retry-after if available.
          retry_after = 300 # Default 5 minutes
          if 'error_data' in error_data and 'error_subcode' in error_data:
            if error_data['error_subcode'] == 2207051:  # Application request limit reached
                retry_after = 900  # 15 minutes
          if 'minutes' in message.lower():
                try:
                    import re
                    time_match = re.search(r'(\d+)\s*minutes?', message.lower())
                    if time_match:
                        retry_after = int(time_match.group(1)) * 60
                except:
                    pass
          self.rate_limit_window[endpoint] = int(time.time()) + retry_after
          raise RateLimitError(message, retry_after, code, subcode, fbtrace_id)
      elif code == 2207026: #Video format error
          raise MediaError(message, code, subcode, fbtrace_id)
      elif code in [1, 2] or 'OAuthException' in str(error_data):  # Temporary server errors
            if attempt < retries -1:
              sleep_time = self._calculate_retry_delay(attempt)
              logger.info(f"Retrying in {sleep_time} seconds...")
              time.sleep(sleep_time)
              return None
            else:
              raise TemporaryServerError(message, code, subcode, fbtrace_id)
      else:
          # For unknown errors, retry a few times and then raise a generic exception
          if attempt < retries - 1:
              sleep_time = self._calculate_retry_delay(attempt)
              logger.info(f"Retrying in {sleep_time} seconds...")
              time.sleep(sleep_time)
              return None
          else:
              raise InstagramAPIError(message, code, subcode, fbtrace_id)


    def _calculate_retry_delay(self, attempt):
        """Calculates exponential backoff delay."""
        return 2 ** attempt + random.uniform(0, 1)  # Add some jitter

    def _respect_rate_limits(self, endpoint):
        """Ensures requests respect rate limits."""
        current_time = time.time()
        if endpoint in self.rate_limit_window and self.rate_limit_window[endpoint] > current_time:
            wait_time = self.rate_limit_window[endpoint] - current_time
            logger.warning(f"Rate limit hit for {endpoint}. Waiting {wait_time:.1f} seconds.")
            time.sleep(wait_time)

        elapsed = current_time - self.last_request_time
        if elapsed < self.min_request_interval:
            sleep_time = self.min_request_interval - elapsed
            time.sleep(sleep_time)

class InstagramPostService(BaseInstagramService):
    """Handles creating and publishing Instagram posts (primarily images)."""
    def __init__(self, access_token=None, user_id=None):
        load_dotenv()
        access_token = access_token or os.getenv('INSTAGRAM_API_KEY')
        user_id = user_id or os.getenv("INSTAGRAM_ACCOUNT_ID")

        if not access_token or not user_id:
          raise ValueError("INSTAGRAM_API_KEY and INSTAGRAM_ACCOUNT_ID must be set.")

        super().__init__(access_token, user_id)
        self.token_expires_at = None  # Initialize token expiration time
        self._validate_token()  # Validate token and get expiration time

    def _validate_token(self):
      """Validates the access token and retrieves its expiration time."""
      try:
          response = self._make_request(
              "GET",
              "debug_token",
              params={
                  "input_token": self.access_token,
              },
          )
          if response and 'data' in response and response['data'].get('is_valid'):
            logger.info("Token de acesso validado com sucesso.")
            if 'instagram_basic' not in response['data'].get('scopes', []) or \
                'instagram_content_publish' not in response['data'].get('scopes', []):
                logger.warning("Token may not have necessary permissions for posting")
            # Store the token expiration time, if available
            self.token_expires_at = response['data'].get('expires_at')
            if self.token_expires_at:
                logger.info(f"Token will expire at: {datetime.fromtimestamp(self.token_expires_at)}")
          else:
                logger.error("Access token is invalid or expired.")
                raise AuthenticationError("Access token is invalid or expired.")

      except InstagramAPIError as e:
          logger.error(f"Error validating token: {e}")
          raise  # Re-raise the exception to halt execution if the token is invalid

    def _refresh_token(self):
        """Refreshes the access token.  (Instagram uses long-lived tokens, so this might not be strictly necessary,
        but it's good practice to have a refresh mechanism.)
        """
        # Check if we have a long-lived token. If not, we can't refresh.
        if not os.getenv("INSTAGRAM_API_KEY"):
            raise AuthenticationError("Cannot refresh token. No long-lived access token available.")

        logger.info("Refreshing Instagram access token...")
        try:
            response = self._make_request(
                "GET",
                "oauth/access_token",
                params={
                    "grant_type": "ig_refresh_token",
                    "client_secret": os.getenv("INSTAGRAM_CLIENT_SECRET"),  #  use client secret
                    "access_token": self.access_token,
                },
            )

            self.access_token = response['access_token']
            self.token_expires_at = time.time() + response['expires_in']
            logger.info(f"Token refreshed. New expiration: {datetime.fromtimestamp(self.token_expires_at)}")

            # Update the .env file (DANGEROUS - see notes below)
            self._update_env_file("INSTAGRAM_API_KEY", self.access_token)


        except InstagramAPIError as e:
            logger.error(f"Error refreshing token: {e}")
            raise  # Re-raise to handle the error higher up


    def _update_env_file(self, key, new_value):
        """
        Updates the .env file with the new token.
        WARNING: Modifying the .env file directly is generally a BAD IDEA
        because it can lead to accidental commits of sensitive information.
        A much better approach is to use a secrets management system or
        instruct the user to manually update their .env file.  This method
        is included *only* for demonstration/convenience in a local development
        environment and should NOT be used in production.
        """
        try:
            with open(".env", "r") as f:
                lines = f.readlines()

            updated_lines = []
            found = False
            for line in lines:
                if line.startswith(f"{key}="):
                    updated_lines.append(f"{key}={new_value}\n")
                    found = True
                else:
                    updated_lines.append(line)
            if not found:
                updated_lines.append(f"{key}={new_value}\n")

            with open(".env", "w") as f:
                f.writelines(updated_lines)

            logger.warning(
                ".env file updated.  THIS IS GENERALLY NOT RECOMMENDED FOR PRODUCTION. "
                "Consider using a secrets management solution instead."
            )

        except Exception as e:
            logger.error(f"Error updating .env file: {e}")
            # Do NOT raise the exception here.  It's better to continue
            # with the (potentially) old .env value than to crash the app.


    def create_media_container(self, image_url, caption):
        """Creates a media container for the post."""
        endpoint = f"{self.user_id}/media"
        # Token refresh check before making any API calls
        if self.token_expires_at and time.time() > self.token_expires_at - 60:  # 60-second buffer
            self._refresh_token()
        try:
            response = self._make_request(
                "POST",
                endpoint,
                data={
                    "image_url": image_url,
                    "caption": caption,
                },
            )
            return response['id']
        except InstagramAPIError as e:
          logger.error(f"Error creating media container: {e}")
          raise

    def publish_media(self, container_id):
      """Publishes the media container."""
      endpoint = f"{self.user_id}/media_publish"
      # Token refresh check before making any API calls
      if self.token_expires_at and time.time() > self.token_expires_at - 60:  # 60-second buffer
          self._refresh_token()
      try:
          response = self._make_request(
              "POST",
              endpoint,
              data={
                  "creation_id": container_id,
              },
          )
          return response['id']
      except InstagramAPIError as e:
          logger.error(f"Error publishing media: {e}")
          raise

    def post_image(self, image_url, caption):
        """Handles the full flow of creating and publishing an Instagram post."""
        # Token refresh check before making any API calls
        if self.token_expires_at and time.time() > self.token_expires_at - 60:  # 60-second buffer
          self._refresh_token()
        try:
            container_id = self.create_media_container(image_url, caption)
            if not container_id:
                raise MediaError("Failed to create media container")

            # Increased wait time and more robust status checking (adapted from previous code)
            status = self.wait_for_container_status(container_id)  # Use the wait_for_container_status
            if status != 'FINISHED':
                raise MediaError(f"Container did not finish processing. Status: {status}")

            post_id = self.publish_media(container_id)
            if not post_id:
                raise MediaError("Failed to publish media")

            return post_id

        except InstagramAPIError as e:
            logger.error(f"Error posting image: {e}")
            raise

    def wait_for_container_status(self, container_id: str, max_attempts: int = 30, delay: int = 5) -> str:
        """Verifica o status do container até estar pronto ou falhar."""
        # Token refresh check before making any API calls
        if self.token_expires_at and time.time() > self.token_expires_at - 60:
            self._refresh_token()
        endpoint = f"{container_id}"  # Removed BASE_URL, using _make_request
        params = {
            'fields': 'status_code,status',
        }
        for attempt in range(max_attempts):
            try:
                data = self._make_request('GET', endpoint, params=params)  # Using _make_request
                if not data:
                    logger.warning(f"Failed to get container status (attempt {attempt + 1}/{max_attempts})")
                    time.sleep(delay)
                    continue

                status = data.get('status_code', '')
                logger.info(f"Container status (attempt {attempt + 1}/{max_attempts}): {status}")
                if status == 'FINISHED':
                    return status
                elif status in ['ERROR', 'EXPIRED']:
                    logger.error(f"Container failed with status: {status}")
                    return status  # Return immediately on error

                time.sleep(delay)

            except RateLimitError as e:
                logger.warning(f"Rate limit hit while checking status. Waiting {e.retry_after}s...")
                time.sleep(e.retry_after)
            except Exception as e:
                logger.error(f"Error checking container status: {str(e)}")
                time.sleep(delay)

        logger.error(f"Container status check timed out after {max_attempts} attempts.")
        return 'TIMEOUT'  # Return specific timeout status