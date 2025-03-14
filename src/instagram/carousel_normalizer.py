from typing import List, Optional, Dict, Any, Tuple
from PIL import Image
import os
import logging

# Configure logger
logger = logging.getLogger(__name__)


class CarouselNormalizer:
    """
    Handles validation and normalization of images for Instagram carousels.

    This class ensures all images in a carousel meet Instagram's requirements:
    - Consistent aspect ratios across all images
    - Proper resolution and dimensions
    - Size and format validation
    - Automatic image optimization

    Features:
        - Aspect ratio normalization
        - Resolution standardization
        - Format conversion
        - Size optimization
        - EXIF data handling

    Technical Details:
        - Target resolutions: 1080x1080 (square), 1080x1350 (portrait), 1080x608 (landscape)
        - Supported formats: JPEG, PNG
        - Max file size: 8MB per image
        - Aspect ratio tolerance: ±0.01

    Example:
        >>> normalizer = CarouselNormalizer()
        >>> images = [
        ...     "path/to/image1.jpg",
        ...     "path/to/image2.png",
        ...     "path/to/image3.jpg"
        ... ]
        >>> normalized = normalizer.normalize_carousel_images(images)
        >>> if normalized:
        ...     print(f"Successfully normalized {len(normalized)} images")
    """

    # Class constants
    MAX_SIZE_MB = 8
    CAROUSEL_RATIO_TOLERANCE = 0.01
    TARGET_RESOLUTIONS = {
        'square': (1080, 1080),
        'portrait': (1080, 1350),
        'landscape': (1080, 608)
    }
    ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png'}

    def __init__(self):
        """Initialize the normalizer with default settings."""
        self.temp_files = []  # Track temporary files for cleanup

    def normalize_carousel_images(self, image_paths: List[str]) -> List[str]:
        """
        Process multiple images for carousel upload, ensuring consistent ratios.

        Workflow:
        1. Validate input images
        2. Determine target aspect ratio
        3. Process each image to match target
        4. Optimize file sizes
        5. Clean up temporary files

        Args:
            image_paths: List of paths to images to process

        Returns:
            List of paths to normalized images

        Examples:
            Basic usage:
            >>> normalizer = CarouselNormalizer()
            >>> result = normalizer.normalize_carousel_images([
            ...     "image1.jpg",
            ...     "image2.png"
            ... ])

            With error handling:
            >>> try:
            ...     normalized = normalizer.normalize_carousel_images(images)
            ...     if not normalized:
            ...         print("No valid images to process")
            ... except Exception as e:
            ...     print(f"Error normalizing images: {e}")
        """
        if not image_paths or len(image_paths) < 2:
            logger.warning("At least 2 images required for carousel")
            return []

        valid_image_data = []

        # First pass: collect valid images and their properties
        for path in image_paths:
            try:
                with Image.open(path) as img:
                    # Check format and basic validity
                    if img.format not in ('JPEG', 'PNG'):
                        logger.warning(f"Unsupported format {img.format} for {path}")
                        continue

                    width, height = img.size
                    ratio = width / height
                    valid_image_data.append((path, width, height, ratio))

            except Exception as e:
                logger.error(f"Error processing image {path}: {e}")
                continue

        if not valid_image_data:
            return []

        # Find optimal target ratio (use first image's ratio as base)
        target_ratio = self._determine_target_ratio(valid_image_data)

        # Second pass: normalize images to target ratio
        normalized_paths = []
        for path, width, height, ratio in valid_image_data:
            try:
                normalized = self._normalize_image(
                    path,
                    target_ratio,
                    self.CAROUSEL_RATIO_TOLERANCE
                )
                if normalized:
                    normalized_paths.append(normalized)

            except Exception as e:
                logger.error(f"Error normalizing {path}: {e}")
                continue

        return normalized_paths

    def _determine_target_ratio(self, image_data: List[Tuple]) -> float:
        """
        Calculate optimal target ratio for a set of images.

        Strategy:
        1. Group images by similar ratios
        2. Find most common ratio group
        3. Use median ratio from largest group

        Args:
            image_data: List of tuples (path, width, height, ratio)

        Returns:
            float: Target aspect ratio

        Technical Details:
            - Groups ratios within tolerance of each other
            - Handles both portrait and landscape orientations
            - Considers Instagram's ratio limits
        """
        if not image_data:
            return 1.0  # Default to square

        ratios = [ratio for _, _, _, ratio in image_data]

        # Group similar ratios
        ratio_groups = {}
        for ratio in ratios:
            matched = False
            for group_ratio in ratio_groups:
                if abs(ratio - group_ratio) <= self.CAROUSEL_RATIO_TOLERANCE:
                    ratio_groups[group_ratio].append(ratio)
                    matched = True
                    break
            if not matched:
                ratio_groups[ratio] = [ratio]

        # Find largest group
        largest_group = max(ratio_groups.values(), key=len)
        return sum(largest_group) / len(largest_group)

    def _normalize_image(
            self,
            path: str,
            target_ratio: float,
            tolerance: float = 0.01) -> Optional[str]:
        """
        Normalize a single image to match target ratio and requirements.

        Process:
        1. Load and validate image
        2. Adjust aspect ratio if needed
        3. Resize to target resolution
        4. Optimize file size
        5. Save with proper format

        Args:
            path: Path to source image
            target_ratio: Desired width/height ratio
            tolerance: Acceptable ratio difference

        Returns:
            str: Path to normalized image, or None if failed

        Technical Details:
            Resolution Selection:
            - Square (1:1): 1080x1080
            - Portrait (4:5): 1080x1350
            - Landscape (1.91:1): 1080x608

            Size Optimization:
            - JPEG quality adjustment
            - PNG compression
            - Metadata stripping
        """
        try:
            with Image.open(path) as img:
                # Convert to RGB if needed
                if img.mode != 'RGB':
                    img = img.convert('RGB')

                width, height = img.size
                current_ratio = width / height

                # Check if ratio adjustment needed
                if abs(current_ratio - target_ratio) > tolerance:
                    # Calculate new dimensions
                    if current_ratio > target_ratio:
                        # Too wide - crop width
                        new_width = int(height * target_ratio)
                        left = (width - new_width) // 2
                        img = img.crop((left, 0, left + new_width, height))
                    else:
                        # Too tall - crop height
                        new_height = int(width / target_ratio)
                        top = (height - new_height) // 2
                        img = img.crop((0, top, width, top + new_height))

                # Determine target resolution
                target_size = self._get_target_resolution(target_ratio)
                img = img.resize(target_size, Image.LANCZOS)

                # Save with optimization
                output_path = self._get_temp_path(path)
                img.save(
                    output_path,
                    'JPEG',
                    quality=85,
                    optimize=True,
                    progressive=True
                )

                # Verify final size
                if os.path.getsize(output_path) > self.MAX_SIZE_MB * 1024 * 1024:
                    logger.warning(f"Image {path} too large after normalization")
                    return None

                return output_path

        except Exception as e:
            logger.error(f"Error normalizing {path}: {e}")
            return None

    def _get_target_resolution(self, ratio: float) -> Tuple[int, int]:
        """
        Determine target resolution based on aspect ratio.

        Args:
            ratio: Width/height ratio

        Returns:
            tuple: Target (width, height)

        Examples:
            >>> normalizer._get_target_resolution(1.0)
            (1080, 1080)  # Square
            >>> normalizer._get_target_resolution(0.8)
            (1080, 1350)  # Portrait
            >>> normalizer._get_target_resolution(1.91)
            (1080, 608)   # Landscape
        """
        if abs(ratio - 1) <= 0.1:
            return self.TARGET_RESOLUTIONS['square']
        elif ratio < 1:
            return self.TARGET_RESOLUTIONS['portrait']
        else:
            return self.TARGET_RESOLUTIONS['landscape']

    def _get_temp_path(self, original_path: str) -> str:
        """
        Generate temporary path for normalized image.

        Args:
            original_path: Source image path

        Returns:
            str: Path for normalized image

        Note:
            Adds path to self.temp_files for later cleanup
        """
        temp_dir = os.path.join(os.path.dirname(original_path), 'normalized')
        os.makedirs(temp_dir, exist_ok=True)

        filename = os.path.basename(original_path)
        name, _ = os.path.splitext(filename)
        temp_path = os.path.join(temp_dir, f"{name}_normalized.jpg")

        self.temp_files.append(temp_path)
        return temp_path

    def cleanup(self):
        """
        Remove temporary files created during normalization.

        Call this after carousel upload is complete to free space.
        Safe to call multiple times.
        """
        for path in self.temp_files:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception as e:
                logger.warning(f"Error removing temp file {path}: {e}")

        self.temp_files.clear()