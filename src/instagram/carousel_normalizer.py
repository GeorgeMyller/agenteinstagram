from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import os
import logging
from PIL import Image
from datetime import datetime
import tempfile

from ..utils.config import Config

logger = logging.getLogger(__name__)

@dataclass
class ImageMetadata:
    width: int
    height: int
    aspect_ratio: float
    file_path: Path
    format: str
    orientation: str  # 'portrait', 'landscape', or 'square'
    size_bytes: int

@dataclass
class NormalizedImage:
    original_path: Path
    normalized_path: Path
    width: int
    height: int
    processing_time: float
    created_at: datetime = field(default_factory=datetime.now)

@dataclass
class NormalizationOptions:
    target_aspect_ratio: float = 1.0  # Square
    max_width: int = 1080
    max_height: int = 1080
    padding_color: Tuple[int, int, int] = (255, 255, 255)  # White
    quality: int = 95
    format: str = "JPEG"

class CarouselNormalizer:
    """Normalizes images for Instagram carousel posts to ensure consistent display"""
    
    def __init__(self):
        self.config = Config.get_instance()
        
    def normalize_carousel_images(
        self,
        image_paths: List[str],
        options: Optional[NormalizationOptions] = None
    ) -> List[str]:
        """
        Normalizes a list of images for carousel posts
        
        Args:
            image_paths: List of image file paths
            options: Normalization options
            
        Returns:
            List of normalized image file paths
        """
        try:
            if not image_paths:
                return []
                
            if options is None:
                options = NormalizationOptions()
                
            # Create temp directory for normalized images
            temp_dir = Path(tempfile.mkdtemp(prefix="carousel_norm_"))
                
            # Process each image
            normalized_paths = []
            for i, path in enumerate(image_paths):
                try:
                    original_path = Path(path)
                    if not original_path.exists():
                        logger.warning(f"Image not found: {path}")
                        continue
                        
                    # Get image metadata
                    metadata = self._get_image_metadata(original_path)
                    
                    # Create output path
                    output_name = f"norm_{i}_{original_path.name}"
                    output_path = temp_dir / output_name
                    
                    # Normalize image
                    normalized = self._normalize_image(
                        metadata, 
                        output_path, 
                        options
                    )
                    
                    normalized_paths.append(str(normalized.normalized_path))
                    
                except Exception as e:
                    logger.error(f"Error normalizing image {path}: {e}")
                    # If we fail to normalize, use the original
                    normalized_paths.append(path)
                    
            return normalized_paths
            
        except Exception as e:
            logger.error(f"Error in carousel normalization: {e}")
            # If normalization fails, return original paths
            return image_paths
            
    def _get_image_metadata(self, file_path: Path) -> ImageMetadata:
        """Extract metadata from an image file"""
        with Image.open(file_path) as img:
            width, height = img.size
            aspect_ratio = width / height
            
            # Determine orientation
            if abs(aspect_ratio - 1.0) < 0.01:  # Within 1% of square
                orientation = "square"
            elif aspect_ratio > 1.0:
                orientation = "landscape"
            else:
                orientation = "portrait"
                
            return ImageMetadata(
                width=width,
                height=height,
                aspect_ratio=aspect_ratio,
                file_path=file_path,
                format=img.format,
                orientation=orientation,
                size_bytes=file_path.stat().st_size
            )
            
    def _normalize_image(
        self,
        metadata: ImageMetadata,
        output_path: Path,
        options: NormalizationOptions
    ) -> NormalizedImage:
        """Normalize a single image"""
        start_time = datetime.now()
        
        with Image.open(metadata.file_path) as img:
            # Resize if needed
            if (metadata.width > options.max_width or 
                metadata.height > options.max_height):
                img = self._resize_image(
                    img, 
                    options.max_width, 
                    options.max_height
                )
                width, height = img.size
            else:
                width, height = metadata.width, metadata.height
                
            # Create canvas with target aspect ratio
            if abs(metadata.aspect_ratio - options.target_aspect_ratio) > 0.01:
                img = self._pad_to_aspect_ratio(
                    img, 
                    options.target_aspect_ratio,
                    options.padding_color
                )
                
            # Save normalized image
            img.save(
                output_path, 
                format=options.format, 
                quality=options.quality
            )
            
        processing_time = (datetime.now() - start_time).total_seconds()
        
        return NormalizedImage(
            original_path=metadata.file_path,
            normalized_path=output_path,
            width=width,
            height=height,
            processing_time=processing_time
        )
        
    def _resize_image(
        self,
        img: Image.Image,
        max_width: int,
        max_height: int
    ) -> Image.Image:
        """Resize image to fit within specified dimensions"""
        width, height = img.size
        aspect_ratio = width / height
        
        if width > max_width:
            width = max_width
            height = int(width / aspect_ratio)
            
        if height > max_height:
            height = max_height
            width = int(height * aspect_ratio)
            
        return img.resize((width, height), Image.LANCZOS)
        
    def _pad_to_aspect_ratio(
        self,
        img: Image.Image,
        target_ratio: float,
        padding_color: Tuple[int, int, int]
    ) -> Image.Image:
        """Pad image to achieve target aspect ratio"""
        width, height = img.size
        current_ratio = width / height
        
        if abs(current_ratio - target_ratio) < 0.01:
            return img
            
        if current_ratio > target_ratio:
            # Image is wider than target, add vertical padding
            new_height = int(width / target_ratio)
            padded = Image.new(
                "RGB", 
                (width, new_height), 
                padding_color
            )
            paste_y = (new_height - height) // 2
            padded.paste(img, (0, paste_y))
            return padded
        else:
            # Image is taller than target, add horizontal padding
            new_width = int(height * target_ratio)
            padded = Image.new(
                "RGB", 
                (new_width, height), 
                padding_color
            )
            paste_x = (new_width - width) // 2
            padded.paste(img, (paste_x, 0))
            return padded