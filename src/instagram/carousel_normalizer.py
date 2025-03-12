import os
from typing import List, Optional, Dict, Any
from PIL import Image
import logging

# Configure logger
logger = logging.getLogger(__name__)


class CarouselNormalizer:
    """Handles validation and normalization of carousel images."""

    MIN_DIMENSION = 320
    MAX_DIMENSION = 1440
    TARGET_RATIO = 1.0  # Square aspect ratio
    RATIO_TOLERANCE = 0.01  # 1% tolerance
    MAX_SIZE = 8 * 1024 * 1024  # 8MB
    SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png'}

    def validate_image_file(self, image_path: str) -> bool:
        """Validates a single image file."""
        try:
            from PIL import Image
            import os

            # Check if file exists and has valid extension
            if not os.path.exists(image_path):
                raise ValueError(f"File not found: {image_path}")

            _, ext = os.path.splitext(image_path)
            if ext.lower() not in self.SUPPORTED_FORMATS:
                raise ValueError(f"Unsupported format: {ext}")

            # Check file size
            if os.path.getsize(image_path) > self.MAX_SIZE:
                raise ValueError(f"File too large: {os.path.getsize(image_path)} bytes (max: {self.MAX_SIZE})")

            # Check dimensions and aspect ratio
            with Image.open(image_path) as img:
                width, height = img.size

                if width < self.MIN_DIMENSION or height < self.MIN_DIMENSION:
                    raise ValueError(f"Image too small: {width}x{height} (min: {self.MIN_DIMENSION}x{self.MIN_DIMENSION})")

                if width > self.MAX_DIMENSION or height > self.MAX_DIMENSION:
                    raise ValueError(f"Image too large: {width}x{height} (max: {self.MAX_DIMENSION}x{self.MAX_DIMENSION})")

                ratio = width / height
                if abs(ratio - self.TARGET_RATIO) > self.RATIO_TOLERANCE:
                    raise ValueError(f"Invalid aspect ratio: {ratio:.2f} (target: {self.TARGET_RATIO})")

            return True

        except Exception as e:
            logger.error(f"Image validation failed for {image_path}: {str(e)}")
            return False

    def normalize_carousel_images(self, image_paths: List[str]) -> List[str]:
        """Normalizes a list of images for carousel posting."""
        if not image_paths:
            raise ValueError("No images provided")

        normalized_paths = []
        target_ratio = None

        # First pass: determine target ratio from first valid image
        for path in image_paths:
            try:
                with Image.open(path) as img:
                    width, height = img.size
                    ratio = width / height
                    if self.MIN_DIMENSION <= min(width, height) and max(width, height) <= self.MAX_DIMENSION:
                        target_ratio = ratio
                        break
            except Exception as e:
                logger.warning(f"Could not process {path}: {str(e)}")
                continue

        if target_ratio is None:
            raise ValueError("No valid images found to determine target ratio")

        # Second pass: normalize all images
        for path in image_paths:
            try:
                normalized_path = self._normalize_single_image(path, target_ratio)
                if normalized_path:
                    normalized_paths.append(normalized_path)
            except Exception as e:
                logger.warning(f"Failed to normalize {path}: {str(e)}")
                continue

        if len(normalized_paths) < 2:
            raise ValueError(f"Not enough valid images after normalization: {len(normalized_paths)} (min: 2)")

        return normalized_paths

    def _normalize_single_image(self, image_path: str, target_ratio: float) -> Optional[str]:
        """Normalizes a single image to match the target ratio."""
        try:
            from PIL import Image
            import os

            with Image.open(image_path) as img:
                width, height = img.size
                current_ratio = width / height

                # Calculate new dimensions
                if abs(current_ratio - target_ratio) <= self.RATIO_TOLERANCE:
                    # Ratio is already good, just resize if needed
                    if max(width, height) > self.MAX_DIMENSION:
                        scale = self.MAX_DIMENSION / max(width, height)
                        new_width = int(width * scale)
                        new_height = int(height * scale)
                        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                else:
                    # Need to crop to match ratio
                    if current_ratio > target_ratio:
                        # Image is too wide
                        new_width = int(height * target_ratio)
                        crop_box = ((width - new_width) // 2, 0,
                                     (width + new_width) // 2, height)
                    else:
                        # Image is too tall
                        new_height = int(width / target_ratio)
                        crop_box = (0, (height - new_height) // 2,
                                    width, (height + new_height) // 2)
                    img = img.crop(crop_box)

                # Convert to RGB if needed
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')

                # Save normalized image
                normalized_path = os.path.join(
                    os.path.dirname(image_path),
                    f"normalized_{os.path.basename(image_path)}"
                )
                img.save(normalized_path, 'JPEG', quality=95)

                return normalized_path

        except Exception as e:
            logger.error(f"Failed to normalize {image_path}: {str(e)}")
            return None

    def get_image_info(self, image_path: str) -> Dict[str, Any]:
        """Gets basic information about an image file."""
        try:
            from PIL import Image
            import os

            with Image.open(image_path) as img:
                return {
                    'width': img.size[0],
                    'height': img.size[1],
                    'format': img.format,
                    'mode': img.mode,
                    'size_bytes': os.path.getsize(image_path)
                }
        except Exception as e:
            logger.error(f"Failed to get image info for {image_path}: {str(e)}")
            return None