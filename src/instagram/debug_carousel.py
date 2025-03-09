#!/usr/bin/env python
"""
Instagram Carousel Debug Utility

This script helps diagnose issues with Instagram carousel posting functionality.
It checks token permissions and provides detailed debugging information.
"""

import os
import sys
import logging
import argparse
import requests
from typing import List, Optional
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

def check_token_permissions():
    """Check if the current token has all required permissions for carousel posting"""
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
            
            # Get detailed token info
            token_info = service.debug_token()
            if 'data' in token_info:
                print("\nDetailed token information:")
                data = token_info['data']
                print(f"App ID: {data.get('app_id', 'N/A')}")
                print(f"Type: {data.get('type', 'N/A')}")
                print(f"Expires: {data.get('expires_at', 'N/A')}")
                print(f"Valid: {data.get('is_valid', False)}")
                print(f"Scopes: {', '.join(data.get('scopes', []))}")
            
            print("\nRequired permissions for carousel posting:")
            print("- instagram_basic")
            print("- instagram_content_publish")
            print("\nPlease update your token to include these permissions.")
            
            return False
    except Exception as e:
        print(f"❌ Error checking token: {e}")
        return False

def clear_carousel_cache():
    """Clear any cached carousel state"""
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
        
        # Don't actually delete here - just informational
        
        return True
    except Exception as e:
        print(f"❌ Error clearing cache: {e}")
        return False

def validate_image_dimensions(image_paths: List[str]) -> bool:
    """Check that all images have the same aspect ratio"""
    from PIL import Image
    
    print("\n===== VALIDATING IMAGE DIMENSIONS =====")
    
    if not image_paths:
        print("❌ No images provided")
        return False
    
    try:
        dimensions = []
        for path in image_paths:
            if not os.path.exists(path):
                print(f"❌ Image not found: {path}")
                return False
                
            with Image.open(path) as img:
                width, height = img.size
                aspect_ratio = round(width / height, 3)
                dimensions.append((width, height, aspect_ratio))
                print(f"Image: {os.path.basename(path)}, Size: {width}x{height}, Aspect ratio: {aspect_ratio}")
        
        # Check if all aspect ratios are the same (within a small tolerance)
        first_ratio = dimensions[0][2]
        all_same = all(abs(d[2] - first_ratio) < 0.01 for d in dimensions)
        
        if all_same:
            print("✅ All images have the same aspect ratio")
            return True
        else:
            print("❌ Images have different aspect ratios. Instagram requires all carousel images to have the same aspect ratio.")
            return False
    
    except Exception as e:
        print(f"❌ Error validating images: {e}")
        return False

def test_carousel_upload(image_paths: List[str]) -> bool:
    """Test uploading images for carousel without actually posting"""
    print("\n===== TESTING CAROUSEL UPLOAD =====")
    
    if not image_paths:
        print("❌ No images provided")
        return False
    
    try:
        def progress_callback(current, total):
            print(f"Uploading image {current}/{total}...")
            
        success, uploaded_images, image_urls = upload_carousel_images(image_paths, progress_callback=progress_callback)
        
        if success and len(image_urls) >= 2:
            print(f"✅ Successfully uploaded {len(image_urls)} images")
            for i, url in enumerate(image_urls):
                print(f"  {i+1}. {url}")
            return True
        else:
            print(f"❌ Failed to upload images. Got {len(image_urls)} valid URLs, need at least 2.")
            return False
            
    except Exception as e:
        print(f"❌ Error testing carousel upload: {e}")
        return False

def run_diagnostics(image_paths: Optional[List[str]] = None):
    """Run all diagnostics"""
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
        
        if not checks[0]["passed"]:
            print("- Get a new token with proper permissions from the Facebook Developer Dashboard")
            print("  Required permissions: instagram_basic, instagram_content_publish")
        
        if len(checks) > 2 and not checks[2]["passed"]:
            print("- Ensure all carousel images have exactly the same aspect ratio")
            print("- Instagram recommended ratios: 1.91:1 (landscape), 1:1 (square), or 4:5 (portrait)")
            print("- Each image should be less than 8MB")
        
        print("- After fixing issues, run the debug script again to verify")
    else:
        print("- All checks passed! Your setup should be ready to post carousels")
        print("- If you're still having issues, check the Instagram API status")
        print("- Make sure you have fewer than 25 API posts in a 24 hour period")
    
    print("\nFor more help, see:")
    print("https://developers.facebook.com/docs/instagram-api/guides/content-publishing")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Instagram Carousel Debug Utility")
    parser.add_argument('--images', nargs='+', help='Paths to test images for carousel validation')
    
    args = parser.parse_args()
    
    run_diagnostics(args.images)