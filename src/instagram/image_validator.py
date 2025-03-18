"""
Instagram Image Validator

Validates images meet Instagram requirements before upload.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set, Union
from pathlib import Path
import os
import logging
from PIL import Image, ImageOps
from ..utils.config import Config
from ..utils.resource_manager import ResourceManager

logger = logging.getLogger(__name__)

@dataclass
class ValidationResult:
    is_valid: bool
    message: str
    validation_time: float
    details: Dict[str, str] = field(default_factory=dict)

@dataclass
class ImageValidationRules:
    min_width: int = 320
    min_height: int = 320
    max_width: int = 1080
    max_height: int = 1350
    max_aspect_ratio: float = 1.91  # Height can be up to 1.91 times the width
    min_aspect_ratio: float = 0.8  # Width can be up to 1.25 times the height
    allowed_formats: Set[str] = field(default_factory=lambda: {"JPEG", "PNG"})
    max_file_size_mb: float = 8.0

class InstagramImageValidator:
    """Validates and optimizes images for Instagram requirements"""
    
    # Instagram image requirements
    MAX_SIZE_MB = 8
    MIN_WIDTH = 320
    MAX_WIDTH = 1440
    MIN_HEIGHT = 320
    MAX_HEIGHT = 1440
    ASPECT_RATIO_TOLERANCE = 0.01
    ALLOWED_FORMATS = [".jpg", ".jpeg", ".png"]  # Removed .heic from allowed formats
    
    def __init__(self):
        self.config = Config.get_instance()
        self.resource_manager = ResourceManager.get_instance()
        
    def process_single_photo(self, image_path: Union[str, Path]) -> Dict:
        """
        Process a single photo for Instagram posting
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Dict containing processed image info or error details
        """
        try:
            image_path = Path(image_path)
            
            # Validate file existence and format
            if not image_path.exists():
                return {"status": "error", "message": "Image file does not exist"}
                
            if image_path.suffix.lower() not in self.ALLOWED_FORMATS:
                return {
                    "status": "error",
                    "message": f"Invalid image format. Must be one of: {', '.join(self.ALLOWED_FORMATS)}"
                }
            
            # Open and validate image
            try:
                image = Image.open(image_path)
            except Exception as e:
                return {"status": "error", "message": f"Failed to open image: {e}"}
            
            # Check dimensions
            width, height = image.size
            if width < self.MIN_WIDTH or height < self.MIN_HEIGHT:
                return {
                    "status": "error",
                    "message": f"Image too small. Minimum dimensions: {self.MIN_WIDTH}x{self.MIN_HEIGHT}"
                }
                
            if width > self.MAX_WIDTH or height > self.MAX_HEIGHT:
                # Resize image
                try:
                    resized_path = self._resize_image(image, image_path)
                    if not resized_path:
                        return {"status": "error", "message": "Failed to resize image"}
                    return {
                        "status": "success",
                        "message": "Image resized successfully",
                        "image_path": str(resized_path)
                    }
                except Exception as e:
                    return {"status": "error", "message": f"Failed to resize image: {e}"}
            
            # Check file size
            file_size = os.path.getsize(image_path) / (1024 * 1024)  # Convert to MB
            if file_size > self.MAX_SIZE_MB:
                try:
                    optimized_path = self._optimize_image(image, image_path)
                    if not optimized_path:
                        return {"status": "error", "message": "Failed to optimize image"}
                    return {
                        "status": "success",
                        "message": "Image optimized successfully",
                        "image_path": str(optimized_path)
                    }
                except Exception as e:
                    return {"status": "error", "message": f"Failed to optimize image: {e}"}
            
            # Image meets requirements
            return {
                "status": "success",
                "message": "Image meets requirements",
                "image_path": str(image_path)
            }
            
        except Exception as e:
            logger.error(f"Error processing image: {e}")
            return {"status": "error", "message": str(e)}
            
    def validate_carousel(self, image_paths: List[Union[str, Path]]) -> Dict:
        """Validate a set of images for carousel posting"""
        try:
            results = []
            first_aspect_ratio = None
            
            for i, path in enumerate(image_paths):
                # Process each image
                result = self.process_single_photo(path)
                if result["status"] == "error":
                    return {
                        "status": "error",
                        "message": f"Image {i+1}: {result['message']}"
                    }
                    
                # Get aspect ratio
                image = Image.open(result["image_path"])
                width, height = image.size
                aspect_ratio = width / height
                
                # Check if aspect ratios match
                if first_aspect_ratio is None:
                    first_aspect_ratio = aspect_ratio
                elif abs(aspect_ratio - first_aspect_ratio) > self.ASPECT_RATIO_TOLERANCE:
                    return {
                        "status": "error",
                        "message": f"Image {i+1} has different aspect ratio"
                    }
                    
                results.append({
                    "original_path": str(path),
                    "processed_path": result["image_path"],
                    "width": width,
                    "height": height
                })
                
            return {
                "status": "success",
                "message": "All images validated successfully",
                "images": results
            }
            
        except Exception as e:
            logger.error(f"Error validating carousel: {e}")
            return {"status": "error", "message": str(e)}
            
    def _convert_heic(self, image_path: Path) -> Optional[Path]:
        """This method is deprecated as HEIC support has been removed"""
        logger.warning("HEIC format is no longer supported")
        return None
            
    def _resize_image(self, image: Image.Image, original_path: Path) -> Optional[Path]:
        """Resize image to meet Instagram requirements"""
        try:
            width, height = image.size
            aspect_ratio = width / height
            
            if width > self.MAX_WIDTH:
                width = self.MAX_WIDTH
                height = int(width / aspect_ratio)
            
            if height > self.MAX_HEIGHT:
                height = self.MAX_HEIGHT
                width = int(height * aspect_ratio)
                
            resized = image.resize((width, height), Image.LANCZOS)
            
            with self.resource_manager.temp_file(suffix='.jpg') as temp_path:
                resized.save(temp_path, format='JPEG', quality=95)
                return Path(temp_path)
                
        except Exception as e:
            logger.error(f"Error resizing image: {e}")
            return None
            
    def _optimize_image(self, image: Image.Image, original_path: Path) -> Optional[Path]:
        """Optimize image to meet size requirements"""
        try:
            quality = 95
            min_quality = 70
            
            while quality >= min_quality:
                with self.resource_manager.temp_file(suffix='.jpg') as temp_path:
                    image.save(temp_path, format='JPEG', quality=quality)
                    
                    if os.path.getsize(temp_path) / (1024 * 1024) <= self.MAX_SIZE_MB:
                        return Path(temp_path)
                        
                quality -= 5
                
            return None
            
        except Exception as e:
            logger.error(f"Error optimizing image: {e}")
            return None
