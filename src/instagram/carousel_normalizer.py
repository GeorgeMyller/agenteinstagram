import os
import time
import logging
import tempfile
from typing import List, Tuple
from PIL import Image
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
    
    @staticmethod
    def get_image_aspect_ratio(image_path: str) -> float:
        """Get the aspect ratio of an image (width/height)"""
        try:
            with Image.open(image_path) as img:
                width, height = img.size
                return round(width / height, 3)
        except Exception as e:
            logger.error(f"Error getting aspect ratio for {image_path}: {str(e)}")
            return 0
    
    @staticmethod
    def get_most_common_ratio(image_paths: List[str]) -> float:
        """Find the most common aspect ratio in a list of images"""
        if not image_paths:
            return CarouselNormalizer.RECOMMENDED_RATIOS['square']
            
        ratios = []
        for path in image_paths:
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
        rec_ratios = CarouselNormalizer.RECOMMENDED_RATIOS
        diffs = {r: abs(current_ratio - ratio) for r, ratio in rec_ratios.items()}
        closest = min(diffs, key=diffs.get)
        return rec_ratios[closest]
    
    @staticmethod
    def normalize_image(image_path: str, target_ratio: float) -> str:
        """
        Resize the image to match the target aspect ratio
        Returns path to the normalized image
        """
        try:
            # Create a temp file with same extension
            file_ext = os.path.splitext(image_path)[1]
            temp_file = tempfile.NamedTemporaryFile(suffix=file_ext, delete=False)
            temp_path = temp_file.name
            temp_file.close()
            
            with Image.open(image_path) as img:
                orig_width, orig_height = img.size
                orig_ratio = orig_width / orig_height
                
                # If ratios are close enough, no need to modify
                if abs(orig_ratio - target_ratio) < 0.01:
                    # Just make a copy to the temp file
                    img.save(temp_path, quality=95)
                    return temp_path
                
                # Calculate new dimensions
                if orig_ratio > target_ratio:
                    # Image is wider than target ratio, need to crop width
                    new_width = int(orig_height * target_ratio)
                    new_height = orig_height
                else:
                    # Image is taller than target ratio, need to crop height
                    new_width = orig_width
                    new_height = int(orig_width / target_ratio)
                
                # Calculate crop box (centered)
                left = (orig_width - new_width) // 2
                top = (orig_height - new_height) // 2
                right = left + new_width
                bottom = top + new_height
                
                # Crop and save
                cropped = img.crop((left, top, right, bottom))
                cropped.save(temp_path, quality=95)
                
                logger.info(f"Normalized image {image_path} from {orig_width}x{orig_height} (ratio: {orig_ratio:.3f}) "
                           f"to {new_width}x{new_height} (ratio: {target_ratio:.3f})")
                
                return temp_path
                
        except Exception as e:
            logger.error(f"Error normalizing image {image_path}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return image_path  # Return original on error
    
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
            
        # Get most common aspect ratio
        target_ratio = CarouselNormalizer.get_most_common_ratio(image_paths)
        logger.info(f"Target aspect ratio for carousel: {target_ratio:.3f}")
        
        # Normalize all images
        normalized_paths = []
        for path in image_paths:
            norm_path = CarouselNormalizer.normalize_image(path, target_ratio)
            normalized_paths.append(norm_path)
            
        return normalized_paths