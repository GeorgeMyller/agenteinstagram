# Media Validation Tool

## Overview
This guide explains how to use the media validation tools to ensure your content meets Instagram requirements.

## Image Requirements
- Format: JPEG/PNG
- Aspect ratio: 4:5 to 1.91:1
- Minimum resolution: 320x320 pixels
- Maximum file size: 8MB

## Video Requirements
- Format: MP4 (H.264 codec)
- Aspect ratio: 4:5 to 1.91:1 (feed videos)
- Aspect ratio: 9:16 (reels)
- Resolution: Minimum 500 pixels wide
- Duration: 3-60 seconds (feed videos)
- Duration: 3-90 seconds (reels)
- Maximum file size: 100MB

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

1. **Incorrect format**
   - Use the built-in video converter to convert to MP4 format
   - The converter handles codec and format requirements automatically

2. **Duration issues**
   - Trim video if too long
   - Loop or extend if too short
   - Use the video editor tool

3. **Resolution too low**
   - Upscale with quality preservation
   - Re-record in higher quality
   - Use better camera settings

## Using the Validation Tools

### Image Validation
```python
from src.instagram import InstagramMediaService

media_service = InstagramMediaService()
is_valid, message = media_service.validate_media("image.jpg")
if not is_valid:
    print(f"Validation failed: {message}")
```

### Video Validation
```python
from src.instagram import InstagramVideoProcessor

processor = InstagramVideoProcessor()
is_valid, message = processor.validate_video("video.mp4")
if not is_valid:
    print(f"Validation failed: {message}")
```

## Video Processing Options

### Optimizing Videos
The video processor can automatically optimize videos for Instagram:
- Correct aspect ratio
- Proper resolution
- Optimal bitrate
- Compatible codecs

```python
from src.instagram import InstagramVideoProcessor

processor = InstagramVideoProcessor()
optimized_path = processor.optimize_video("input.mp4", target_type="reels")
```

### Custom Processing
You can customize video processing with these options:
- Target width/height
- Remove audio
- Custom bitrate
- Quality settings

## Handling Different Media Types

### Regular Feed Videos
- Use `target_type="video"` 
- Aspect ratio between 4:5 and 1.91:1
- Duration 3-60 seconds

### Reels
- Use `target_type="reels"`
- Fixed 9:16 aspect ratio
- Duration 3-90 seconds

## Best Practices

1. **Always validate before posting**
   ```python
   if processor.validate_video(video_path)[0]:
       # Safe to proceed with posting
   ```

2. **Use optimized videos**
   ```python
   optimized = processor.optimize_video(video_path)
   if optimized:
       # Use optimized version for posting
   ```

3. **Handle validation failures**
   ```python
   is_valid, message = processor.validate_video(video_path)
   if not is_valid:
       # Show error message to user
       # Suggest fixes based on message
   ```

## Troubleshooting

Common validation errors and solutions:

1. **"Video too large"**
   - Use the optimize_video method
   - Reduce resolution or duration

2. **"Invalid aspect ratio"**
   - The optimizer will automatically adjust aspect ratio
   - Or manually crop video to correct ratio

3. **"Duration out of range"**
   - Trim video to acceptable length
   - Check target_type requirements
