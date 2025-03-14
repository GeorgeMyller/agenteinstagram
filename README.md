# Instagram Agent Social Media API

Automated Instagram content publishing with support for images, videos, and carousels.

## Features

- Single image posts
- Multi-image carousels
- Video posts with thumbnails
- Rate limit handling
- Error recovery
- Performance monitoring
- Secure credential management

## Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your Instagram API credentials
```

## Quick Start

1. Configure credentials in `.env`:
```
INSTAGRAM_API_KEY=your_api_key_here
INSTAGRAM_ACCOUNT_ID=your_account_id
```

2. Basic Usage:
```python
from src.instagram_send import InstagramSend

# Post a single image
result = InstagramSend.send_instagram(
    image_path="path/to/image.jpg",
    caption="My first post!"
)

# Post a carousel
images = ["image1.jpg", "image2.jpg", "image3.jpg"]
result = InstagramSend.send_instagram_carousel(
    image_paths=images,
    caption="My first carousel!"
)

# Post a video
result = InstagramSend.send_instagram_video(
    video_path="video.mp4",
    caption="Check out my video!"
)
```

## Advanced Usage

### Error Handling

```python
from src.instagram.errors import RateLimitError, MediaError

try:
    result = InstagramSend.send_instagram(image_path, caption)
except RateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after} seconds")
    time.sleep(e.retry_after)
    retry_upload()
except MediaError as e:
    if e.is_size_error():
        compressed = compress_image(image_path)
        result = InstagramSend.send_instagram(compressed, caption)
```

### Monitoring

```python
from src.utils.monitor import ApiMonitor

# Track API usage
with ApiMonitor() as monitor:
    try:
        result = instagram.post_image(image_path)
        monitor.track_api_call(
            "post_image",
            success=True,
            duration=1.2
        )
    except Exception as e:
        monitor.track_error("post_image", str(e))

# Get statistics
stats = monitor.get_statistics()
print(f"Error Rate: {stats['error_rate']:.2%}")
```

### Carousel Management

```python
from src.instagram.carousel_normalizer import CarouselNormalizer

# Prepare carousel images
normalizer = CarouselNormalizer()
images = [
    "photo1.jpg",
    "photo2.jpg",
    "photo3.jpg"
]

try:
    # Normalize images
    normalized = normalizer.normalize_carousel_images(images)
    
    # Upload carousel
    result = InstagramSend.send_instagram_carousel(
        image_paths=normalized,
        caption="My normalized carousel!"
    )
finally:
    # Clean up temporary files
    normalizer.cleanup()
```

### Configuration Management

```python
from src.utils.config import Config

# Get configuration
config = Config.get_instance()

# Update settings
config.update_setting('MAX_RETRIES', 5)

# Check configuration
if config.is_valid():
    instagram = InstagramAPI(config.get_credentials())
```

## Development

### Running Tests

```bash
# Run all tests
python -m pytest

# Run specific test file
python -m pytest tests/test_carousel.py

# Run with coverage
python -m pytest --cov=src
```

### Debugging

Use the carousel debug utility for troubleshooting:

```bash
# Basic validation
python src/instagram/debug_carousel.py

# Test with specific images
python src/instagram/debug_carousel.py --images image1.jpg image2.jpg
```

Monitor API usage and performance:

```bash
# Start monitoring server
python src/monitor.py

# View dashboard
open http://localhost:5001/dashboard
```

## API Documentation

### Single Image Post

```python
from src.instagram_send import InstagramSend

# Basic post
result = InstagramSend.send_instagram(
    image_path="photo.jpg",
    caption="Hello Instagram!"
)

# With advanced options
result = InstagramSend.send_instagram(
    image_path="photo.jpg",
    caption="Hello Instagram!",
    location_id="123456789",
    user_tags=[{
        "username": "friend",
        "x": 0.5,
        "y": 0.5
    }],
    first_comment="First comment!",
)
```

### Carousel Post

```python
# Simple carousel
result = InstagramSend.send_instagram_carousel(
    image_paths=["img1.jpg", "img2.jpg"],
    caption="My carousel!"
)

# Advanced carousel
result = InstagramSend.send_instagram_carousel(
    image_paths=["img1.jpg", "img2.jpg"],
    caption="My carousel!",
    location_id="123456789",
    user_tags=[
        [{
            "username": "friend1",
            "x": 0.5,
            "y": 0.5
        }],
        [{
            "username": "friend2",
            "x": 0.3,
            "y": 0.7
        }]
    ],
    first_comment="First comment!",
)
```

### Video Post

```python
# Simple video post
result = InstagramSend.send_instagram_video(
    video_path="video.mp4",
    caption="Check out my video!"
)

# Advanced video post
result = InstagramSend.send_instagram_video(
    video_path="video.mp4",
    caption="Check out my video!",
    cover_image="thumbnail.jpg",
    location_id="123456789",
    share_to_feed=True
)
```

## Error Handling

The API uses specialized exception classes for different error scenarios:

```python
from src.instagram.errors import (
    AuthenticationError,
    RateLimitError,
    MediaError,
    BusinessValidationError
)

try:
    result = instagram.post_image(image_path)
except AuthenticationError as e:
    if e.code == 190:  # Invalid token
        refresh_token()
    elif e.code == 200:  # Permission error
        request_permissions()
except RateLimitError as e:
    if e.is_temporary():
        time.sleep(e.retry_after)
        retry_request()
except MediaError as e:
    if e.is_format_error():
        convert_video_format()
    elif e.is_size_error():
        compress_video()
except BusinessValidationError as e:
    if e.requires_business_account():
        convert_to_business()
    elif e.is_policy_violation():
        review_content_guidelines()
```

## Configuration

The application can be configured through:
1. Environment variables
2. Configuration file
3. Runtime settings

### Environment Variables

Required:
- `INSTAGRAM_API_KEY`: Your Instagram API key
- `INSTAGRAM_ACCOUNT_ID`: Your Instagram account ID
- `AUTHORIZED_GROUP_ID`: Authorized group ID for webhooks

Optional:
- `MAX_RETRIES`: Maximum retry attempts (default: 3)
- `RATE_LIMIT_WINDOW`: Rate limit window in seconds (default: 3600)
- `MAX_REQUESTS_PER_WINDOW`: Max requests per window (default: 200)
- `LOG_LEVEL`: Logging level (default: INFO)

### Configuration File

Create `config.json`:

```json
{
    "api": {
        "base_url": "https://graph.facebook.com/v16.0",
        "timeout": 30
    },
    "storage": {
        "temp_dir": "/path/to/temp",
        "max_size_gb": 10
    },
    "features": {
        "enable_carousel": true,
        "enable_video": true
    }
}
```

## Monitoring

The monitoring system tracks:
- API call volumes and rates
- Error counts and types
- Response times
- Resource usage
- Rate limit status

### Dashboard

Access the monitoring dashboard:
```bash
python src/monitor.py
open http://localhost:5001/dashboard
```

### Statistics API

Get current statistics:
```python
from src.utils.monitor import ApiMonitor

monitor = ApiMonitor()
stats = monitor.get_statistics()

print(f"Total Calls: {stats['total_calls']}")
print(f"Error Rate: {stats['error_rate']:.2%}")
print(f"Average Response: {stats['avg_duration']:.2f}s")
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License - see LICENSE file for details