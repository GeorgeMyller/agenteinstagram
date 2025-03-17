from typing import Optional, Dict, Any
import logging
import os
from datetime import datetime
from src.utils.resource_manager import ResourceManager
from src.utils.config import ConfigManager

logger = logging.getLogger(__name__)

class Message:
    """
    Message handler class that processes and extracts data from various message types.
    Supports different message formats including text, audio, image, document, and video.

    Features:
        - Automatic message type detection
        - Resource management for media files
        - Temporary file cleanup
        - Group/private message handling
        - Base64 media decoding
        
    Message Types:
        - TYPE_TEXT: Text messages and commands
        - TYPE_AUDIO: Voice messages and audio files
        - TYPE_IMAGE: Photos and image files
        - TYPE_DOCUMENT: Document attachments
        - TYPE_VIDEO: Video messages and reels

    Scope Types:
        - SCOPE_GROUP: Messages from group chats
        - SCOPE_PRIVATE: Direct messages
    
    Example:
        >>> msg = Message(raw_message_data)
        >>> if msg.message_type == Message.TYPE_IMAGE:
        ...     # Process image with automatic cleanup
        ...     with resource_manager.temp_file(suffix='.jpg') as temp_path:
        ...         temp_path.write_bytes(msg.image_base64_bytes)
    """
    
    TYPE_TEXT = "conversation"
    TYPE_AUDIO = "audioMessage"
    TYPE_IMAGE = "imageMessage"
    TYPE_DOCUMENT = "documentMessage"
    TYPE_VIDEO = "videoMessage"
    
    SCOPE_GROUP = "group"
    SCOPE_PRIVATE = "private"
    
    def __init__(self, raw_data):
        """
        Initialize message processor with raw message data.

        Args:
            raw_data (dict): Raw message data in either simple or complete format.
                           Complete format includes 'data', 'event', 'instance', etc.
                           Simple format contains only message content.

        Example:
            Complete format:
            {
                "event": "message",
                "instance": "instance_id",
                "data": {
                    "message": {
                        "conversation": "Hello"
                    }
                }
            }

            Simple format:
            {
                "message": {
                    "conversation": "Hello"
                }
            }
        """
        self.resource_manager = ResourceManager()
        self.config = ConfigManager()
        
        # Handle different message formats
        if "data" not in raw_data:
            self.data = {
                "event": None,
                "instance": None,
                "destination": None,
                "date_time": None,
                "server_url": None,
                "apikey": None,
                "data": raw_data
            }
        else:
            self.data = raw_data
            
        self.extract_common_data()
        self.extract_specific_data()

    def extract_common_data(self):
        """
        Extract common metadata from the message.
        
        Processes and sets attributes for:
        - Message source and destination
        - Timestamps and IDs
        - User information
        - Message type and status
        - Group/private chat context
        
        Example metadata structure:
            {
                "remoteJid": "1234567890@g.us",
                "id": "msg_123",
                "fromMe": false,
                "timestamp": "1234567890",
                "pushName": "User Name",
                "status": "received"
            }
        """
        self.event = self.data.get("event")
        self.instance = self.data.get("instance")
        self.destination = self.data.get("destination")
        self.date_time = self.data.get("date_time")
        self.server_url = self.data.get("server_url")
        self.apikey = self.data.get("apikey")
        
        data = self.data.get("data", {})
        key = data.get("key", {})
        message = data.get("message", {})
        
        # Core message attributes
        self.remote_jid = key.get("remoteJid")
        self.message_id = key.get("id")
        self.from_me = key.get("fromMe")
        self.push_name = data.get("pushName")
        self.status = data.get("status")
        self.instance_id = data.get("instanceId")
        self.source = data.get("source")
        self.message_timestamp = data.get("messageTimestamp")
        
        # Determine message type
        if message.get("imageMessage"):
            self.message_type = self.TYPE_IMAGE
        elif message.get("videoMessage"):
            self.message_type = self.TYPE_VIDEO
        elif message.get("audioMessage"):
            self.message_type = self.TYPE_AUDIO
        elif message.get("documentMessage"):
            self.message_type = self.TYPE_DOCUMENT
        elif message.get("conversation"):
            self.message_type = self.TYPE_TEXT
        else:
            self.message_type = None
            
        self.sender = data.get("sender")
        self.participant = key.get("participant")

        self.determine_scope()

    def determine_scope(self):
        """
        Determine if message is from a group or private chat.
        Sets scope-related attributes based on the message context.
        
        Group messages (ends with @g.us):
            - Sets group_id from JID
            - Sets phone from participant ID
            
        Private messages (ends with @s.whatsapp.net):
            - Sets phone from JID
            - Sets group_id to None
            
        Example:
            Group: "123456789@g.us" -> group_id="123456789"
            Private: "987654321@s.whatsapp.net" -> phone="987654321"
        """
        if self.remote_jid.endswith("@g.us"):
            self.scope = self.SCOPE_GROUP
            self.group_id = self.remote_jid.split("@")[0]
            self.phone = self.participant.split("@")[0] if self.participant else None
        elif self.remote_jid.endswith("@s.whatsapp.net"):
            self.scope = self.SCOPE_PRIVATE
            self.phone = self.remote_jid.split("@")[0]
            self.group_id = None
        else:
            self.scope = "unknown"
            self.phone = None
            self.group_id = None

    def extract_specific_data(self):
        """
        Extract data specific to the message type.
        Delegates to appropriate handler based on message_type.
        
        Supported message types:
        - Text: Plain text messages
        - Audio: Voice messages and audio files
        - Image: Photos and images
        - Document: File attachments
        - Video: Video messages and reels
        
        Each type has its own extraction method that handles:
        - Media decoding (if applicable)
        - Resource management
        - Metadata extraction
        - Temporary file handling
        """
        type_handlers = {
            self.TYPE_TEXT: self.extract_text_message,
            self.TYPE_AUDIO: self.extract_audio_message,
            self.TYPE_IMAGE: self.extract_image_message,
            self.TYPE_DOCUMENT: self.extract_document_message,
            self.TYPE_VIDEO: self.extract_video_message
        }
        
        handler = type_handlers.get(self.message_type)
        if handler:
            handler()

    def extract_text_message(self):
        """
        Extract plain text from message.
        Sets text_message attribute with conversation content.
        """
        self.text_message = self.data["data"]["message"].get("conversation")

    def extract_audio_message(self):
        """
        Extract audio message data and metadata.
        
        Processes:
        - Base64 encoded audio data
        - Audio format and duration
        - Codec information
        - Waveform data (if available)
        
        Example audio metadata:
            {
                "url": "https://example.com/audio.mp3",
                "mimetype": "audio/mp4",
                "fileSha256": "hash",
                "seconds": 30,
                "ptt": true
            }
        """
        audio_data = self.data["data"]["message"]["audioMessage"]
        self.audio_base64_bytes = self.data["data"]["message"].get("base64")
        self.audio_url = audio_data.get("url")
        self.audio_mimetype = audio_data.get("mimetype")
        self.audio_file_sha256 = audio_data.get("fileSha256")
        self.audio_file_length = audio_data.get("fileLength")
        self.audio_duration_seconds = audio_data.get("seconds")
        self.audio_media_key = audio_data.get("mediaKey")
        self.audio_ptt = audio_data.get("ptt")
        self.audio_file_enc_sha256 = audio_data.get("fileEncSha256")
        self.audio_direct_path = audio_data.get("directPath")
        self.audio_waveform = audio_data.get("waveform")
        self.audio_view_once = audio_data.get("viewOnce", False)

    def extract_image_message(self):
        """
        Extract and process image message with resource management.
        
        Features:
        - Automatic base64 decoding
        - Temporary file creation
        - Resource cleanup scheduling
        - Caption extraction
        
        Example:
            Image data is saved to a temporary file and registered
            for cleanup after 2 hours. The temporary path is stored
            in self.image_path for processing.
            
        Note:
            Uses ResourceManager for automatic cleanup of temp files.
        """
        message_data = self.data["data"]["message"].get("imageMessage", {})
        self.image_caption = message_data.get("caption")
        
        # Debug log to verify imageMessage and base64 attribute
        logger.debug(f"imageMessage data: {message_data}")
        
        # Get image data
        self.image_base64 = message_data.get("base64")
        if self.image_base64:
            try:
                import base64
                self.image_base64_bytes = base64.b64decode(self.image_base64)
                
                # Save image using resource manager
                with self.resource_manager.temp_file(suffix='.jpg') as temp_path:
                    temp_path.write_bytes(self.image_base64_bytes)
                    self.image_path = str(temp_path)
                    self.resource_manager.register_resource(temp_path, lifetime_hours=2)
                    
                logger.info(f"Image saved to temporary file: {self.image_path}")
                
            except Exception as e:
                logger.error(f"Error processing image: {e}")
                self.image_base64_bytes = None
                self.image_path = None

    def extract_document_message(self):
        """
        Extract and process document attachments with resource management.
        
        Features:
        - Original filename preservation
        - Automatic base64 decoding
        - Temporary file handling
        - Resource cleanup after 1 hour
        
        The document is saved to a temporary file with its original
        extension and registered for cleanup. The path is stored in
        self.document_path for processing.
        """
        message_data = self.data["data"]["message"].get("documentMessage", {})
        self.document_filename = message_data.get("fileName")
        
        self.document_base64 = message_data.get("base64")
        if self.document_base64:
            try:
                import base64
                self.document_base64_bytes = base64.b64decode(self.document_base64)
                
                # Save document using resource manager
                with self.resource_manager.temp_file(suffix=os.path.splitext(self.document_filename)[1]) as temp_path:
                    temp_path.write_bytes(self.document_base64_bytes)
                    self.document_path = str(temp_path)
                    self.resource_manager.register_resource(temp_path, lifetime_hours=1)
                    
                logger.info(f"Document saved to temporary file: {self.document_path}")
                
            except Exception as e:
                logger.error(f"Error processing document: {e}")
                self.document_base64_bytes = None
                self.document_path = None

    def extract_video_message(self):
        """
        Extract and process video message with resource management.
        
        Features:
        - Video caption extraction
        - Base64 decoding
        - Temporary MP4 file creation
        - Extended cleanup time (3 hours)
        
        Videos are given a longer cleanup window due to potentially
        longer processing times. The temporary path is stored in
        self.video_path for further processing.
        """
        message_data = self.data["data"]["message"].get("videoMessage", {})
        self.video_caption = message_data.get("caption")
        
        # Debug log to verify videoMessage and base64 attribute
        logger.debug(f"videoMessage data: {message_data}")
        
        # Get video data
        self.video_base64 = message_data.get("base64")
        if not self.video_base64:
            logger.error(f"No video data found in message (ID: {self.message_id})")
            self.video_base64_bytes = None
            self.video_path = None
            return
            
        try:
            import base64
            self.video_base64_bytes = base64.b64decode(self.video_base64)
            
            # Save video using resource manager
            with self.resource_manager.temp_file(suffix='.mp4') as temp_path:
                temp_path.write_bytes(self.video_base64_bytes)
                self.video_path = str(temp_path)
                self.resource_manager.register_resource(temp_path, lifetime_hours=3)
                
            logger.info(f"Video saved to temporary file: {self.video_path}")
            
        except Exception as e:
            logger.error(f"Error processing video: {e}")
            self.video_base64_bytes = None
            self.video_path = None