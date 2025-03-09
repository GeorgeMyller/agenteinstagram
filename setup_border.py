#!/usr/bin/env python
"""
Script to create a basic border image for Instagram carousel posts.
This creates a simple white border with a transparent center.
"""

from PIL import Image, ImageDraw
import os
from src.utils.paths import Paths

def create_border_image():
    """Create a basic border image if one doesn't already exist"""
    assets_dir = os.path.join(Paths.ROOT_DIR, "assets")
    os.makedirs(assets_dir, exist_ok=True)
    
    border_path = os.path.join(assets_dir, "moldura.png")
    
    # Skip if the file already exists
    if os.path.exists(border_path):
        print(f"Border image already exists at {border_path}")
        return border_path
    
    # Create a border image (white frame with transparent center)
    width, height = 1200, 1200
    border_width = 20  # Width of the border in pixels
    
    # Create a transparent image
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Draw white rectangle border
    draw.rectangle(
        [(0, 0), (width, height)],  # Outer rectangle (full image)
        outline=(255, 255, 255, 255),
        width=border_width
    )
    
    # Save the image
    img.save(border_path)
    print(f"Created border image at {border_path}")
    return border_path

if __name__ == "__main__":
    create_border_image()
    print("Run this script to create a default border image.")
    print("You can replace it with your own custom border image with the same filename.")
