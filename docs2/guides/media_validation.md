# Media Validation Tool

The `validate_media.py` script helps you verify that your media files meet Instagram's requirements before attempting to upload them.

## Usage

```bash
./scripts/validate_media.py [--type {image,video,auto}] FILES...
```

### Examples

Validate a single image:
```bash
./scripts/validate_media.py path/to/image.jpg
```

Validate multiple videos:
```bash
./scripts/validate_media.py video1.mp4 video2.mp4 --type video
```

Validate mixed media:
```bash
./scripts/validate_media.py *.jpg *.mp4
```

## Requirements Checked

### Images
- Format: JPEG or PNG only
- Size: Maximum 8MB
- Dimensions: Minimum 320x320 pixels
- Aspect Ratio: Between 0.8 and 1.91 (4:5 to 1.91:1)

### Videos
- Format: MP4 or MOV
- Codec: H.264 video, AAC audio
- Duration: 3-90 seconds
- Resolution: Minimum 600x600 pixels
- Aspect Ratio: Between 0.8 and 1.91
- Size: Maximum 100MB

## Error Messages

The tool provides detailed feedback about any issues found:

```
Validating: example.jpg
==================================================
❌ File has the following issues:
  • File too large: 12.5MB (max 8MB)
  • Invalid aspect ratio: 2.5 (must be between 0.8 and 1.91)
```

## Common Issues and Solutions

### Image Issues

1. **File too large**
   - Use image compression
   - Reduce dimensions if unnecessarily large
   - Convert to JPEG if using PNG

2. **Invalid aspect ratio**
   - Crop image to supported ratio
   - Common ratios: 1:1 (square), 4:5 (portrait), 1.91:1 (landscape)

### Video Issues

1. **Incorrect codec**
   - Convert using FFmpeg:
     ```bash
     ffmpeg -i input.mp4 -c:v libx264 -c:a aac output.mp4
     ```

2. **Duration issues**
   - Trim video if too long
   - Loop or extend if too shor
   - Use our video editor tool

3. **Resolution too low**
   - Upscale with quality preservation
   - Re-record in higher quality
   - Use better camera settings

## Integration with Workflow

The validation tool is integrated into our main workflow:
- Pre-upload validation
- Batch processing
- Automated optimization

### Automated Usage

```python
from scripts.validate_media import validate_image, validate_video

# In your code
def process_media(file_path: str):
    if file_path.endswith(('.jpg', '.jpeg', '.png')):
        is_valid, issues = validate_image(file_path)
    elif file_path.endswith(('.mp4', '.mov')):
        is_valid, issues = validate_video(file_path)

    if not is_valid:
        # Handle issues or optimize automatically
        pass
```

## Best Practices

1. **Always validate before upload**
   - Saves time and API calls
   - Prevents failed uploads
   - Better user experience

2. **Use appropriate tools**
   - Image editing for aspect ratio
   - Video compression for size
   - Format conversion when needed

3. **Monitor changes**
   - Instagram requirements may change
   - Keep tool updated
   - Check official documentation

## Suppor

If you encounter issues:
1. Check the troubleshooting guide
2. Review Instagram's current requirements
3. Open an issue on GitHub
4. Contact support team

Remember to always test media files before attempting to upload them to Instagram to ensure the best possible success rate for your posts.
