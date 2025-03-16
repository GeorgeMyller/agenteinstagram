"""
Instagram Image Validator

Validates images meet Instagram requirements before upload.
"""

import os
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from PIL import Image

logger = logging.getLogger(__name__)

class InstagramImageValidator:
    """Validates images for Instagram compliance"""
    
    def __init__(self):
        """Initialize validator with Instagram requirements"""
        # Image size requirements
        self.min_width = 320
        self.min_height = 320
        self.max_width = 1440
        self.max_height = 1440
        
        # Aspect ratio requirements
        self.min_aspect_ratio = 4.0/5.0  # 0.8
        self.max_aspect_ratio = 1.91
        
        # File requirements
        self.allowed_formats = {'JPEG', 'PNG'}
        self.max_file_size_mb = 8
    
    def process_single_photo(self, image_path: str) -> Dict[str, Any]:
        """
        Validate a single photo
        
        Args:
            image_path: Path to image file
            
        Returns:
            Dict with validation results
        """
        try:
            # Basic file checks
            if not os.path.exists(image_path):
                return {
                    'status': 'error',
                    'message': 'File not found',
                    'file': image_path
                }
                
            file_size_mb = os.path.getsize(image_path) / (1024 * 1024)
            if file_size_mb > self.max_file_size_mb:
                return {
                    'status': 'error',
                    'message': f'File too large ({file_size_mb:.1f}MB > {self.max_file_size_mb}MB)',
                    'file': image_path
                }
            
            # Image validation
            with Image.open(image_path) as img:
                # Check format
                if img.format not in self.allowed_formats:
                    return {
                        'status': 'error',
                        'message': f'Invalid format: {img.format}. Must be JPEG or PNG',
                        'file': image_path
                    }
                
                # Check dimensions
                width, height = img.size
                aspect_ratio = width / height
                
                if width < self.min_width or height < self.min_height:
                    return {
                        'status': 'error',
                        'message': f'Image too small: {width}x{height}. Minimum {self.min_width}x{self.min_height}',
                        'file': image_path
                    }
                
                if width > self.max_width or height > self.max_height:
                    return {
                        'status': 'error',
                        'message': f'Image too large: {width}x{height}. Maximum {self.max_width}x{self.max_height}',
                        'file': image_path
                    }
                
                if aspect_ratio < self.min_aspect_ratio:
                    return {
                        'status': 'error',
                        'message': f'Image too narrow. Aspect ratio {aspect_ratio:.2f} < {self.min_aspect_ratio}',
                        'file': image_path
                    }
                
                if aspect_ratio > self.max_aspect_ratio:
                    return {
                        'status': 'error',
                        'message': f'Image too wide. Aspect ratio {aspect_ratio:.2f} > {self.max_aspect_ratio}',
                        'file': image_path
                    }
                
                # Check color mode
                if img.mode not in ['RGB', 'RGBA']:
                    return {
                        'status': 'error',
                        'message': f'Invalid color mode: {img.mode}. Must be RGB or RGBA',
                        'file': image_path
                    }
            
            return {
                'status': 'success',
                'message': 'Image valid',
                'file': image_path,
                'dimensions': f'{width}x{height}',
                'aspect_ratio': aspect_ratio,
                'size_mb': file_size_mb
            }
            
        except Exception as e:
            logger.error(f"Error validating image {image_path}: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'file': image_path
            }
    
    def process_carousel(self, image_paths: List[str]) -> Dict[str, Any]:
        """
        Validate multiple photos for a carousel
        
        Args:
            image_paths: List of image file paths
            
        Returns:
            Dict with validation results for all images
        """
        if len(image_paths) < 2:
            return {
                'status': 'error',
                'message': 'Carousel requires at least 2 images',
                'images': []
            }
        
        if len(image_paths) > 10:
            return {
                'status': 'error',
                'message': 'Carousel limited to 10 images maximum',
                'images': image_paths[:10]
            }
        
        results = []
        for path in image_paths:
            result = self.process_single_photo(path)
            results.append(result)
        
        # Check if all images are valid
        if all(r['status'] == 'success' for r in results):
            return {
                'status': 'success',
                'message': 'All images valid',
                'images': results
            }
        else:
            return {
                'status': 'error',
                'message': 'One or more images invalid',
                'images': results
            }
    
    def normalize_image(self, image_path: str, output_path: Optional[str] = None) -> Optional[str]:
        """
        Normalize image to meet Instagram requirements
        
        Args:
            image_path: Path to input image
            output_path: Optional path for normalized image
            
        Returns:
            str: Path to normalized image if successful, None otherwise
        """
        try:
            if not output_path:
                filename = os.path.splitext(os.path.basename(image_path))[0]
                output_path = os.path.join(
                    os.path.dirname(image_path),
                    f"{filename}_normalized.jpg"
                )
            
            with Image.open(image_path) as img:
                # Convert to RGB if needed
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Resize if needed
                width, height = img.size
                aspect_ratio = width / height
                
                if aspect_ratio < self.min_aspect_ratio:
                    # Image too narrow, add padding
                    new_width = int(height * self.min_aspect_ratio)
                    new_img = Image.new('RGB', (new_width, height), 'white')
                    paste_x = (new_width - width) // 2
                    new_img.paste(img, (paste_x, 0))
                    img = new_img
                
                elif aspect_ratio > self.max_aspect_ratio:
                    # Image too wide, add padding
                    new_height = int(width / self.max_aspect_ratio)
                    new_img = Image.new('RGB', (width, new_height), 'white')
                    paste_y = (new_height - height) // 2
                    new_img.paste(img, (0, paste_y))
                    img = new_img
                
                # Scale down if too large
                width, height = img.size
                if width > self.max_width or height > self.max_height:
                    scale = min(
                        self.max_width / width,
                        self.max_height / height
                    )
                    new_size = (
                        int(width * scale),
                        int(height * scale)
                    )
                    img = img.resize(new_size, Image.LANCZOS)
                
                # Save with optimal quality
                img.save(
                    output_path,
                    'JPEG',
                    quality=95,
                    optimize=True
                )
                
                return output_path
                
        except Exception as e:
            logger.error(f"Error normalizing image {image_path}: {e}")
            return None
