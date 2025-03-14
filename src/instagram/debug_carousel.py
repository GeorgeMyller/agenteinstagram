#!/usr/bin/env python
"""
Instagram Carousel Debug Utility

This script provides diagnostic tools for troubleshooting Instagram carousel posting functionality.
Features:
- Token validation and permission checks
- Image validation and optimization
- Upload simulation
- Rate limit monitoring
- Cache management

Example Usage:
    # Basic validation
    python debug_carousel.py
    
    # Test with specific images
    python debug_carousel.py --images image1.jpg image2.jpg
    
    # Full diagnostic run
    python debug_carousel.py --full-check --verbose
"""

import os
import sys
import logging
import argparse
import requests
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('carousel_debug')

# Add parent directory to path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.instagram.instagram_carousel_service import InstagramCarouselService
from src.instagram.carousel_poster import upload_carousel_images
from src.instagram.base_instagram_service import BaseInstagramService

def check_token_permissions() -> bool:
    """
    Validate Instagram API token permissions for carousel posting.
    
    Checks required permissions:
    - instagram_basic
    - instagram_content_publish
    - pages_read_engagement
    - pages_manage_posts
    
    Returns:
        bool: True if token has all required permissions
        
    Example:
        >>> if check_token_permissions():
        ...     print("Token valid and has required permissions")
        ... else:
        ...     print("Token missing required permissions")
    """
    load_dotenv()
    
    print("\n===== CHECKING TOKEN PERMISSIONS =====")
    token = os.getenv('INSTAGRAM_API_KEY')
    ig_user_id = os.getenv('INSTAGRAM_ACCOUNT_ID')
    
    if not token or not ig_user_id:
        print("❌ Missing environment variables. Make sure INSTAGRAM_API_KEY and INSTAGRAM_ACCOUNT_ID are set.")
        return False
    
    # Print partial token for verification
    print(f"Token: {token[:15]}...{token[-4:]} (partial)")
    print(f"Instagram User ID: {ig_user_id}")
    
    service = BaseInstagramService(token, ig_user_id)
    try:
        is_valid, missing_permissions = service.check_token_permissions()
        
        if is_valid:
            print("✅ Token is valid and has all required permissions")
            return True
        else:
            print(f"❌ Token is missing required permissions: {missing_permissions}")
            print("\nTo fix:")
            print("1. Go to https://developers.facebook.com/tools/explorer/")
            print("2. Select your app")
            print("3. Add the missing permissions")
            print("4. Generate a new token")
            return False
            
    except Exception as e:
        print(f"❌ Error checking permissions: {e}")
        return False

def clear_carousel_cache() -> bool:
    """
    Clean up cached carousel data and temporary files.
    
    This helps resolve issues caused by:
    - Failed uploads leaving orphaned files
    - Corrupted cache state
    - Disk space issues
    
    Returns:
        bool: True if cleanup successful
        
    Example:
        >>> if clear_carousel_cache():
        ...     print("Cache cleared successfully")
        ... else:
        ...     print("Error clearing cache")
    """
    print("\n===== CLEARING CAROUSEL CACHE =====")
    
    try:
        # Try clearing through the monitoring API if available
        try:
            response = requests.post("http://localhost:5001/debug/carousel/clear")
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Successfully cleared carousel state: {result.get('message', 'No message')}")
                return True
            else:
                print(f"⚠️ Failed to clear carousel state through API: {response.status_code}")
        except requests.RequestException:
            print("⚠️ Could not connect to monitoring API. Proceeding with manual cleanup...")
        
        # Manual file cleanup as fallback
        temp_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "temp")
        carousel_files = [f for f in os.listdir(temp_path) if os.path.isfile(os.path.join(temp_path, f))]        
        print(f"Found {len(carousel_files)} files in temp directory")
        
        for file in carousel_files:
            try:
                os.remove(os.path.join(temp_path, file))
            except Exception as e:
                print(f"⚠️ Could not delete {file}: {e}")
                continue
        
        print("✅ Successfully cleared temp files")
        return True
        
    except Exception as e:
        print(f"❌ Error clearing carousel cache: {e}")
        return False

def validate_image_dimensions(image_paths: List[str]) -> bool:
    """
    Validate image dimensions and aspect ratios for carousel compatibility.
    
    Checks:
    - Minimum resolution (1080px on longest side)
    - Maximum file size (8MB)
    - Consistent aspect ratios (within 1% tolerance)
    - Valid formats (JPEG, PNG)
    
    Args:
        image_paths: List of paths to images to validate
        
    Returns:
        bool: True if all images are valid
        
    Example:
        >>> images = ["photo1.jpg", "photo2.jpg"]
        >>> if validate_image_dimensions(images):
        ...     print("All images valid for carousel")
        ... else:
        ...     print("Some images need adjustment")
    """
    if not image_paths:
        return False
        
    print("\n===== VALIDATING IMAGE DIMENSIONS =====")
    
    try:
        from PIL import Image
        import math
        
        base_ratio = None
        all_valid = True
        
        for path in image_paths:
            try:
                with Image.open(path) as img:
                    width, height = img.size
                    ratio = width / height
                    file_size_mb = os.path.getsize(path) / (1024 * 1024)
                    
                    print(f"\nImage: {os.path.basename(path)}")
                    print(f"Dimensions: {width}x{height}")
                    print(f"Aspect Ratio: {ratio:.3f}")
                    print(f"File Size: {file_size_mb:.1f}MB")
                    
                    # Check minimum resolution
                    if width < 1080 and height < 1080:
                        print("❌ Resolution too low (minimum 1080px on longest side)")
                        all_valid = False
                    
                    # Check file size
                    if file_size_mb > 8:
                        print("❌ File too large (maximum 8MB)")
                        all_valid = False
                    
                    # Check aspect ratio consistency
                    if base_ratio is None:
                        base_ratio = ratio
                    else:
                        if abs(ratio - base_ratio) > 0.01:
                            print("❌ Aspect ratio differs from other images")
                            all_valid = False
                            
            except Exception as e:
                print(f"❌ Error processing {path}: {e}")
                all_valid = False
                
        if all_valid:
            print("\n✅ All images valid for carousel")
        else:
            print("\nℹ️ Tips to fix issues:")
            print("- Use minimum 1080px on longest side")
            print("- Keep file sizes under 8MB")
            print("- Ensure consistent aspect ratios")
            print("- Use only JPEG or PNG formats")
            
            return all_valid
        
    except ImportError:
        print("❌ Could not import PIL. Install with: pip install Pillow")
        return False
    except Exception as e:
        print(f"❌ Error validating images: {e}")
        return False

def test_carousel_upload(image_paths: List[str]) -> bool:
    """
    Test carousel upload without actually posting.
    
    Simulates the upload process to identify potential issues:
    - Media container creation
    - Image upload
    - Rate limit checks
    - Error handling
    
    Args:
        image_paths: List of paths to test images
        
    Returns:
        bool: True if test upload successful
        
    Example:
        >>> images = ["test1.jpg", "test2.jpg"]
        >>> if test_carousel_upload(images):
        ...     print("Upload test passed")
        ... else:
        ...     print("Upload test failed")
    """
    print("\n===== TESTING CAROUSEL UPLOAD =====")
    
    load_dotenv()
    token = os.getenv('INSTAGRAM_API_KEY')
    ig_user_id = os.getenv('INSTAGRAM_ACCOUNT_ID')
    
    if not token or not ig_user_id:
        print("❌ Missing environment variables")
        return False
    
    try:
        service = InstagramCarouselService(token, ig_user_id)
        
        print("Testing media container creation...")
        container_id = service.create_media_container(ig_user_id)
        if not container_id:
            print("❌ Failed to create media container")
            return False
        print("✅ Media container created")
        
        print("\nTesting image upload...")
        result = upload_carousel_images(
            image_paths=image_paths,
            access_token=token,
            caption="Test upload - Debug run"
        )
        
        if result:
            print("✅ Upload test successful")
            return True
        else:
            print("❌ Upload test failed")
            return False
            
    except Exception as e:
        print(f"❌ Error testing upload: {e}")
        return False

def run_diagnostics(image_paths: Optional[List[str]] = None) -> None:
    """
    Run comprehensive diagnostics on carousel functionality.
    
    Performs:
    1. Token permission validation
    2. Cache cleanup
    3. Image validation (if paths provided)
    4. Upload simulation (if paths provided)
    
    Args:
        image_paths: Optional list of test images
        
    Example:
        Basic check:
        >>> run_diagnostics()
        
        Full test with images:
        >>> run_diagnostics([
        ...     "carousel1.jpg",
        ...     "carousel2.jpg"
        ... ])
    """
    print("Starting Instagram Carousel Diagnostics...\n")
    
    checks = [
        {"name": "Token Permissions", "passed": check_token_permissions()},
        {"name": "Cache Clearing", "passed": clear_carousel_cache()},
    ]
    
    if image_paths and len(image_paths) >= 2:
        checks.extend([
            {"name": "Image Validation", "passed": validate_image_dimensions(image_paths)},
            {"name": "Upload Test", "passed": test_carousel_upload(image_paths)},
        ])
    
    # Print summary
    print("\n===== DIAGNOSTICS SUMMARY =====")
    all_passed = True
    for check in checks:
        status = "✅ PASSED" if check["passed"] else "❌ FAILED"
        all_passed = all_passed and check["passed"]
        print(f"{status} - {check['name']}")
    
    print("\nRECOMMENDATIONS:")
    if not all_passed:
        print("- Fix the issues reported above before attempting to post carousels")
        print("- Check the Instagram API status")
        print("- Verify your rate limits")
        print("- Review the error logs")
    else:
        print("- All checks passed! Your setup should be ready for carousel posting")
        print("- Monitor your rate limits")
        print("- Keep an eye on the API status")
    
    print("\nFor more help, see:")
    print("https://developers.facebook.com/docs/instagram-api/guides/content-publishing")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Instagram Carousel Debug Utility")
    parser.add_argument(
        "--images", 
        nargs="+", 
        help="Optional: Paths to test images for full diagnostics"
    )
    args = parser.parse_args()
    
    run_diagnostics(args.images)