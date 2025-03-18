import os
import time
import logging
import tempfile
from typing import List, Tuple, Optional, Dict
from PIL import Image, UnidentifiedImageError
import numpy as np

logger = logging.getLogger('CarouselNormalizer')

class CarouselNormalizer:
    """
    Utility class to normalize images for Instagram carousels.
    Instagram requires all images in a carousel to have the same aspect ratio.
    """
    
    # Instagram recommended aspect ratios
    RECOMMENDED_RATIOS = {
        'square': 1.0,         # 1:1
        'portrait': 0.8,       # 4:5
        'landscape': 1.91      # 1.91:1
    }
    
    # Instagram's supported aspect ratio range
    MIN_ASPECT_RATIO = 0.8     # 4:5 portrait (width/height)
    MAX_ASPECT_RATIO = 1.91    # 1.91:1 landscape
    
    # Instagram's size requirements
    MIN_WIDTH = 320
    MAX_WIDTH = 1440
    MIN_HEIGHT = 320
    MAX_HEIGHT = 1440
    
    # Maximum file size (in bytes)
    MAX_FILE_SIZE = 8 * 1024 * 1024  # 8MB
    
    @staticmethod
    def get_image_aspect_ratio(image_path: str) -> float:
        """Get the aspect ratio of an image (width/height)"""
        if not os.path.exists(image_path):
            logger.error(f"Image file not found: {image_path}")
            return 0
            
        try:
            with Image.open(image_path) as img:
                width, height = img.size
                return round(width / height, 3)
        except UnidentifiedImageError:
            logger.error(f"Could not identify image file: {image_path}")
            return 0
        except Exception as e:
            logger.error(f"Error getting aspect ratio for {image_path}: {str(e)}")
            return 0
    
    @staticmethod
    def get_image_info(image_path: str) -> Dict:
        """Get detailed information about an image"""
        if not os.path.exists(image_path):
            logger.error(f"Image file not found: {image_path}")
            return {}
            
        try:
            with Image.open(image_path) as img:
                file_size = os.path.getsize(image_path)
                file_size_mb = file_size / (1024 * 1024)
                width, height = img.size
                aspect_ratio = round(width / height, 3)
                
                return {
                    'path': image_path,
                    'format': img.format,
                    'mode': img.mode,
                    'width': width,
                    'height': height,
                    'aspect_ratio': aspect_ratio,
                    'file_size': file_size,
                    'file_size_mb': round(file_size_mb, 2)
                }
        except UnidentifiedImageError:
            logger.error(f"Could not identify image file: {image_path}")
            return {}
        except Exception as e:
            logger.error(f"Error getting image info for {image_path}: {str(e)}")
            return {}
    
    @staticmethod
    def validate_for_instagram(image_path: str) -> Tuple[bool, List[str]]:
        """
        Validate if an image meets Instagram's requirements
        Returns (is_valid, issues)
        """
        issues = []
        
        # Check if file exists
        if not os.path.exists(image_path):
            return False, ["File does not exist"]
        
        try:
            info = CarouselNormalizer.get_image_info(image_path)
            if not info:
                return False, ["Failed to get image information"]
            
            # Check dimensions
            if info['width'] < CarouselNormalizer.MIN_WIDTH:
                issues.append(f"Width too small: {info['width']}px (min: {CarouselNormalizer.MIN_WIDTH}px)")
            if info['height'] < CarouselNormalizer.MIN_HEIGHT:
                issues.append(f"Height too small: {info['height']}px (min: {CarouselNormalizer.MIN_HEIGHT}px)")
            if info['width'] > CarouselNormalizer.MAX_WIDTH:
                issues.append(f"Width too large: {info['width']}px (max: {CarouselNormalizer.MAX_WIDTH}px)")
            if info['height'] > CarouselNormalizer.MAX_HEIGHT:
                issues.append(f"Height too large: {info['height']}px (max: {CarouselNormalizer.MAX_HEIGHT}px)")
            
            # Check aspect ratio
            if info['aspect_ratio'] < CarouselNormalizer.MIN_ASPECT_RATIO:
                issues.append(f"Aspect ratio too narrow: {info['aspect_ratio']} (min: {CarouselNormalizer.MIN_ASPECT_RATIO})")
            if info['aspect_ratio'] > CarouselNormalizer.MAX_ASPECT_RATIO:
                issues.append(f"Aspect ratio too wide: {info['aspect_ratio']} (max: {CarouselNormalizer.MAX_ASPECT_RATIO})")
            
            # Check file size
            if info['file_size'] > CarouselNormalizer.MAX_FILE_SIZE:
                issues.append(f"File size too large: {info['file_size_mb']}MB (max: {CarouselNormalizer.MAX_FILE_SIZE / (1024*1024)}MB)")
            
            return len(issues) == 0, issues
            
        except Exception as e:
            logger.error(f"Error validating image {image_path}: {str(e)}")
            return False, [f"Validation error: {str(e)}"]
    
    @staticmethod
    def get_most_common_ratio(image_paths: List[str]) -> float:
        """Find the most common aspect ratio in a list of images"""
        if not image_paths:
            return CarouselNormalizer.RECOMMENDED_RATIOS['square']
        
        # Filter out non-existent files first
        valid_paths = [path for path in image_paths if os.path.exists(path)]
        if not valid_paths:
            logger.warning("No valid image files found in provided paths")
            return CarouselNormalizer.RECOMMENDED_RATIOS['square']
            
        ratios = []
        for path in valid_paths:
            ratio = CarouselNormalizer.get_image_aspect_ratio(path)
            if ratio > 0:
                ratios.append(ratio)
                
        if not ratios:
            return CarouselNormalizer.RECOMMENDED_RATIOS['square']
            
        # Round ratios to 2 decimal places for comparing
        rounded_ratios = [round(r, 2) for r in ratios]
        unique_ratios = set(rounded_ratios)
        
        # If all images already have the same ratio, return that
        if len(unique_ratios) == 1:
            return ratios[0]
            
        # Count occurrences of each ratio
        ratio_counts = {}
        for ratio in rounded_ratios:
            if ratio in ratio_counts:
                ratio_counts[ratio] += 1
            else:
                ratio_counts[ratio] = 1
        
        # Find most common ratio
        most_common = max(ratio_counts, key=ratio_counts.get)
        
        # Return the actual ratio (not rounded)
        idx = rounded_ratios.index(most_common)
        return ratios[idx]
    
    @staticmethod
    def get_best_instagram_ratio(current_ratio: float) -> float:
        """
        Find the closest Instagram recommended ratio
        """
        # If already within Instagram's supported range, keep it
        if CarouselNormalizer.MIN_ASPECT_RATIO <= current_ratio <= CarouselNormalizer.MAX_ASPECT_RATIO:
            return current_ratio
            
        # Otherwise find the closest recommended ratio
        rec_ratios = CarouselNormalizer.RECOMMENDED_RATIOS
        diffs = {r: abs(current_ratio - ratio) for r, ratio in rec_ratios.items()}
        closest = min(diffs, key=diffs.get)
        return rec_ratios[closest]
    
    @staticmethod
    def resize_to_instagram_limits(img: Image.Image) -> Image.Image:
        """Resize image if it exceeds Instagram's maximum dimensions"""
        width, height = img.size
        max_dimension = 1080  # Instagram's recommended max dimension
        
        # Calculate scaling factor
        if width > height:
            if width > max_dimension:
                scale = max_dimension / width
                new_width = max_dimension
                new_height = int(height * scale)
            else:
                return img
        else:
            if height > max_dimension:
                scale = max_dimension / height
                new_height = max_dimension
                new_width = int(width * scale)
            else:
                return img

        # Ensure dimensions are even numbers
        new_width = new_width - (new_width % 2)
        new_height = new_height - (new_height % 2)
        
        # Use high quality resizing
        resized = img.resize((new_width, new_height), Image.LANCZOS)
        logger.info(f"Resized image from {width}x{height} to {new_width}x{new_height}")
        return resized

    @staticmethod
    def validate_dimensions(width: int, height: int) -> Tuple[bool, List[str]]:
        """Validate image dimensions against Instagram's requirements"""
        issues = []
        
        if width > CarouselNormalizer.MAX_WIDTH or height > CarouselNormalizer.MAX_HEIGHT:
            issues.append(f"Image size {width}x{height} exceeds Instagram's maximum dimensions")
            
        if width < CarouselNormalizer.MIN_WIDTH or height < CarouselNormalizer.MIN_HEIGHT:
            issues.append(f"Image size {width}x{height} is below Instagram's minimum dimensions")
            
        return len(issues) == 0, issues
    
    @staticmethod
    def normalize_image(image_path: str, target_ratio: float) -> Optional[str]:
        """
        Resize and normalize the image to match the target aspect ratio
        """
        try:
            with Image.open(image_path) as img:
                # Convert to RGB if needed
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # First resize to Instagram limits
                resized = CarouselNormalizer.resize_to_instagram_limits(img)
                
                # Get current dimensions
                width, height = resized.size
                current_ratio = width / height
                
                # Create temp file
                file_ext = os.path.splitext(image_path)[1] or '.jpg'
                temp_file = tempfile.NamedTemporaryFile(suffix=file_ext, delete=False)
                temp_path = temp_file.name
                temp_file.close()
                
                # If ratios are close enough, just save
                if abs(current_ratio - target_ratio) < 0.01:
                    resized.save(temp_path, 'JPEG', quality=95)
                    return temp_path
                
                # Calculate dimensions for target ratio
                if current_ratio > target_ratio:
                    new_width = int(height * target_ratio)
                    crop_width = (width - new_width) // 2
                    crop_box = (crop_width, 0, crop_width + new_width, height)
                else:
                    new_height = int(width / target_ratio)
                    crop_height = (height - new_height) // 2
                    crop_box = (0, crop_height, width, crop_height + new_height)
                
                # Crop and save
                cropped = resized.crop(crop_box)
                cropped.save(temp_path, 'JPEG', quality=95)
                
                logger.info(f"Normalized image ratio from {current_ratio:.3f} to {target_ratio:.3f}")
                return temp_path
                
        except Exception as e:
            logger.error(f"Error normalizing image {image_path}: {str(e)}")
            return None
    
    @staticmethod
    def find_best_target_ratio(image_paths: List[str]) -> float:
        """Find the best target ratio that will work with Instagram's requirements"""
        if not image_paths:
            return CarouselNormalizer.RECOMMENDED_RATIOS['square']
            
        # First try the most common ratio
        most_common = CarouselNormalizer.get_most_common_ratio(image_paths)
        
        # Check if this ratio is within Instagram's limits
        if CarouselNormalizer.MIN_ASPECT_RATIO <= most_common <= CarouselNormalizer.MAX_ASPECT_RATIO:
            return most_common
            
        # If not, find the closest valid Instagram ratio
        return CarouselNormalizer.get_best_instagram_ratio(most_common)
    
    @staticmethod
    def normalize_carousel_images(image_paths: List[str]) -> List[str]:
        """
        Normalize all images to the most common aspect ratio
        Returns a list of paths to normalized images
        """
        if not image_paths:
            return []
            
        if len(image_paths) < 2:
            return image_paths
            
        # Filter out non-existent files
        valid_paths = [path for path in image_paths if os.path.exists(path)]
        if not valid_paths:
            logger.warning("No valid image files found in provided paths")
            return []
        
        # Log diagnostic information about the original images
        logger.info("Original image information:")
        for path in valid_paths:
            info = CarouselNormalizer.get_image_info(path)
            if info:
                logger.info(f"- {os.path.basename(path)}: {info['width']}x{info['height']}, "
                           f"ratio: {info['aspect_ratio']}, size: {info['file_size_mb']}MB")
            
        # Get best target ratio that will work with Instagram
        target_ratio = CarouselNormalizer.find_best_target_ratio(valid_paths)
        logger.info(f"Target aspect ratio for carousel: {target_ratio:.3f}")
        
        # Track any temporary files we create
        temp_files = []
        
        # Normalize all images
        normalized_paths = []
        for path in valid_paths:
            norm_path = CarouselNormalizer.normalize_image(path, target_ratio)
            if norm_path:
                normalized_paths.append(norm_path)
                # If this is a new temporary file, track it
                if norm_path != path:
                    temp_files.append(norm_path)
            
        # If something went wrong and we didn't get any normalized paths,
        # return the original valid paths
        if not normalized_paths:
            logger.warning("Normalization failed, returning original valid paths")
            return valid_paths
        
        # Validate normalized images for Instagram
        all_valid = True
        for path in normalized_paths:
            is_valid, issues = CarouselNormalizer.validate_for_instagram(path)
            if not is_valid:
                all_valid = False
                logger.warning(f"Normalized image {path} still has issues: {', '.join(issues)}")
            
        if not all_valid:
            logger.warning("Some normalized images may not meet Instagram requirements")
        else:
            logger.info("All normalized images meet Instagram requirements")
            
        # Log diagnostic information about the normalized images
        logger.info("Normalized image information:")
        for path in normalized_paths:
            info = CarouselNormalizer.get_image_info(path)
            if info:
                logger.info(f"- {os.path.basename(path)}: {info['width']}x{info['height']}, "
                           f"ratio: {info['aspect_ratio']}, size: {info['file_size_mb']}MB")
            
        return normalized_paths