from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging
from src.utils.resource_manager import ResourceManager
from src.utils.config import Config

logger = logging.getLogger(__name__)

@dataclass
class MessageMetadata:
    remote_jid: str
    id: str
    timestamp: datetime
    from_me: bool = False
    group_id: Optional[str] = None
    user_id: Optional[str] = None

@dataclass
class MessageContent:
    type: str
    text: Optional[str] = None
    image_base64: Optional[str] = None
    video_base64: Optional[str] = None
    image_caption: Optional[str] = None
    video_caption: Optional[str] = None
    document_base64: Optional[str] = None
    document_filename: Optional[str] = None

@dataclass
class Message:
    # Constants
    TYPE_TEXT = "text"
    TYPE_IMAGE = "image"
    TYPE_VIDEO = "video"
    TYPE_DOCUMENT = "document"
    
    SCOPE_PRIVATE = "private"
    SCOPE_GROUP = "group"
    
    # Data fields
    metadata: MessageMetadata
    content: MessageContent
    raw_data: Dict[str, Any] = field(default_factory=dict)
    
    def __init__(self, data: Dict[str, Any]):
        self.resource_manager = ResourceManager()
        self.config = Config.get_instance()
        
        self.raw_data = data
        self._extract_metadata()
        self._extract_content()
    
    def _extract_metadata(self) -> None:
        """Extract message metadata from raw data"""
        msg_data = self.raw_data.get('data', {}).get('message', {})
        
        self.metadata = MessageMetadata(
            remote_jid=msg_data.get('key', {}).get('remoteJid', ''),
            id=msg_data.get('key', {}).get('id', ''),
            timestamp=datetime.fromtimestamp(
                msg_data.get('messageTimestamp', 0)
            ),
            from_me=msg_data.get('key', {}).get('fromMe', False),
            group_id=msg_data.get('key', {}).get('remoteJid', '')
                if '@g.us' in msg_data.get('key', {}).get('remoteJid', '')
                else None,
            user_id=msg_data.get('key', {}).get('participant', '')
        )
    
    def _extract_content(self) -> None:
        """Extract message content from raw data"""
        msg_data = self.raw_data.get('data', {}).get('message', {})
        
        # Determine message type and content
        content_type = self.TYPE_TEXT
        text = None
        image_base64 = None
        video_base64 = None
        image_caption = None
        video_caption = None
        document_base64 = None
        document_filename = None
        
        if 'conversation' in msg_data:
            content_type = self.TYPE_TEXT
            text = msg_data['conversation']
        
        elif 'imageMessage' in msg_data:
            content_type = self.TYPE_IMAGE
            image_base64 = msg_data['imageMessage'].get('base64', '')
            image_caption = msg_data['imageMessage'].get('caption', '')
            
        elif 'videoMessage' in msg_data:
            content_type = self.TYPE_VIDEO
            video_base64 = msg_data['videoMessage'].get('base64', '')
            video_caption = msg_data['videoMessage'].get('caption', '')
            
        elif 'documentMessage' in msg_data:
            content_type = self.TYPE_DOCUMENT
            document_base64 = msg_data['documentMessage'].get('base64', '')
            document_filename = msg_data['documentMessage'].get('fileName', '')
        
        self.content = MessageContent(
            type=content_type,
            text=text,
            image_base64=image_base64,
            video_base64=video_base64,
            image_caption=image_caption,
            video_caption=video_caption,
            document_base64=document_base64,
            document_filename=document_filename
        )
    
    @property
    def message_type(self) -> str:
        return self.content.type
    
    @property
    def text_message(self) -> Optional[str]:
        return self.content.text
    
    @property
    def scope(self) -> str:
        return self.SCOPE_GROUP if self.metadata.group_id else self.SCOPE_PRIVATE
    
    @property
    def remote_jid(self) -> str:
        return self.metadata.remote_jid
    
    @property
    def group_id(self) -> Optional[str]:
        return self.metadata.group_id