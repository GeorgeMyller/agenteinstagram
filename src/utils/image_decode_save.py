from dataclasses import dataclass, field
from typing import Optional, Tuple
from pathlib import Path
import os
import logging
import base64
from datetime import datetime
import uuid
from io import BytesIO
from PIL import Image

from src.utils.paths import Paths

logger = logging.getLogger(__name__)

@dataclass
class DecodedImage:
    file_path: Path
    width: int
    height: int
    format: str
    size_bytes: int
    processing_time: float
    mime_type: str
    created_at: datetime = field(default_factory=datetime.now)

class ImageDecodeSaver:
    """
    Handles decoding and saving base64-encoded images
    
    Methods:
        process: Decode and save a base64 image
        decode: Convert base64 string to image data
        save_image: Save image data to a file
    """
    
    @classmethod
    def process(
        cls,
        base64_data: Optional[str],
        prefix: str = "img_",
        output_dir: Optional[str] = None
    ) -> str:
        """
        Process a base64-encoded image string
        
        Args:
            base64_data: Base64-encoded image data
            prefix: Filename prefix
            output_dir: Directory to save to (default: temp)
            
        Returns:
            File path of saved image
        """
        start_time = datetime.now()
        
        try:
            if not base64_data:
                raise ValueError("No image data provided")
            
            # Decode image
            image_data, mime_type, format_name = cls.decode(base64_data)
            
            # Determine output path
            if output_dir:
                output_path = Path(output_dir)
            else:
                output_path = Paths.temp_dir
            
            # Ensure directory exists
            output_path.mkdir(exist_ok=True, parents=True)
            
            # Generate unique filename with proper extension
            extension = format_name.lower()
            if extension == "jpeg":
                extension = "jpg"
            
            filename = f"{prefix}{uuid.uuid4()}.{extension}"
            file_path = output_path / filename
            
            # Save the image
            cls.save_image(image_data, file_path)
            
            # Get image info
            with Image.open(file_path) as img:
                width, height = img.size
                
            # Create result data
            processing_time = (datetime.now() - start_time).total_seconds()
            
            result = DecodedImage(
                file_path=file_path,
                width=width,
                height=height,
                format=format_name,
                size_bytes=file_path.stat().st_size,
                processing_time=processing_time,
                mime_type=mime_type
            )
            
            logger.debug(
                f"Image processed: {file_path} ({width}x{height}, "
                f"{result.size_bytes/1024:.1f}KB)"
            )
            
            return str(file_path)
            
        except Exception as e:
            logger.error(f"Failed to process image: {str(e)}")
            raise
    
    @staticmethod
    def decode(
        base64_data: str
    ) -> Tuple[BytesIO, str, str]:
        """
        Decode base64 image data
        
        Args:
            base64_data: Base64-encoded image data
            
        Returns:
            Tuple of (image_data, mime_type, format_name)
        """
        try:
            # Handle data URI format
            if "," in base64_data:
                header, encoded = base64_data.split(",", 1)
                mime_type = header.split(":")[1].split(";")[0] if ":" in header else "image/jpeg"
            else:
                encoded = base64_data
                mime_type = "image/jpeg"  # Default
            
            # Decode the image
            img_data = base64.b64decode(encoded)
            image_data = BytesIO(img_data)
            
            # Get format name from mime type
            format_map = {
                "image/jpeg": "JPEG",
                "image/jpg": "JPEG",
                "image/png": "PNG",
                "image/gif": "GIF",
                "image/webp": "WEBP"
            }
            format_name = format_map.get(mime_type, "JPEG")
            
            # Validate image by opening it
            with Image.open(image_data) as img:
                if img.format:
                    format_name = img.format
                    
                # Reset seek position
                image_data.seek(0)
                
            return image_data, mime_type, format_name
        
        except Exception as e:
            logger.error(f"Failed to decode image: {e}")
            raise ValueError(f"Invalid image data: {str(e)}")
    
    @staticmethod
    def save_image(
        image_data: BytesIO,
        file_path: Path
    ) -> None:
        """
        Save image data to file
        
        Args:
            image_data: Image data as BytesIO
            file_path: Path to save the image
        """
        try:
            with open(file_path, "wb") as f:
                f.write(image_data.getvalue())
        except Exception as e:
            logger.error(f"Failed to save image to {file_path}: {e}")
            raise



