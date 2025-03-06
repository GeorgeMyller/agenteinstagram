# Common Issues and Solutions

This guide covers the most common issues you might encounter while using Agent Social Media and their solutions.

## Installation Issues

### Python Version Mismatch
**Problem**: Error about Python version requirement not me
**Solution**:
1. Install Python 3.12 or newer
2. Create a new virtual environment:
   ```bash
   python3.12 -m venv venv
   source venv/bin/activate  # or venv\Scripts\activate on Windows
   ```

### FFmpeg Missing
**Problem**: Video processing fails with FFmpeg-related errors
**Solution**:
- On macOS: `brew install ffmpeg`
- On Ubuntu: `sudo apt install ffmpeg`
- On Windows: Download from [FFmpeg website](https://ffmpeg.org/download.html)

## Configuration Issues

### Missing Environment Variables
**Problem**: "Environment variable X not found" errors
**Solution**:
1. Copy `.env.example` to `.env`
2. Fill in all required variables
3. Run validation script:
   ```bash
   python scripts/validate_setup.py
   ```

### Invalid API Keys
**Problem**: Authentication errors with Instagram/Imgur
**Solution**:
1. Verify tokens using:
   ```bash
   python scripts/validate_tokens.py
   ```
2. Regenerate tokens if expired
3. Check permission scopes

## Instagram Issues

### Post Upload Failures

#### Error 2207026 (Invalid Media Format)
**Problem**: Video format not accepted by Instagram
**Solution**:
1. Ensure video meets requirements:
   - Codec: H.264
   - Audio: AAC
   - Resolution: ≥600x600
   - Duration: 3-90s (Reels)
2. Use automatic optimization:
   ```python
   from instagram.video_processor import optimize_video
   optimize_video(video_path)
   ```

#### Error 190 (Invalid/Expired Token)
**Problem**: Instagram API token expired
**Solution**:
1. Generate new token in Meta Developer Console
2. Update `.env` file
3. Restart the application

### Carousel Issues

#### Images Not Showing
**Problem**: Carousel images missing or not loading
**Solution**:
1. Check file permissions
2. Verify image paths
3. Clear the carousel state:
   ```bash
   curl -X POST http://localhost:5001/debug/carousel/clear
   ```

#### Upload Stuck
**Problem**: Carousel upload appears frozen
**Solution**:
1. Check logs in `logs/app_debug.log`
2. Clear error queue:
   ```bash
   curl -X POST http://localhost:5001/debug/error-queue/clear
   ```
3. Restart the process

## Performance Issues

### High Memory Usage
**Problem**: Application using too much memory
**Solution**:
1. Clear temp directories:
   ```bash
   rm -rf temp/*
   ```
2. Reduce MAX_CAROUSEL_IMAGES in settings
3. Enable automatic cleanup:
   ```python
   cleanup_interval_minutes = 30
   ```

### Slow Video Processing
**Problem**: Video processing takes too long
**Solution**:
1. Check FFmpeg installation
2. Reduce video quality settings
3. Use smaller video files
4. Enable hardware acceleration

## Integration Issues

### Webhook Not Receiving Events
**Problem**: Webhook endpoint not getting messages
**Solution**:
1. Verify webhook URL is correc
2. Check network/firewall settings
3. Test with debug endpoint:
   ```bash
   curl http://localhost:5001/debug/send-tes
   ```

### Rate Limiting
**Problem**: Too many requests errors
**Solution**:
1. Implement exponential backoff
2. Reduce request frequency
3. Use bulk operations where possible

## Development Issues

### Type Checking Errors
**Problem**: mypy reporting type errors
**Solution**:
1. Install type stubs:
   ```bash
   pip install -r requirements-dev.tx
   ```
2. Add type annotations
3. Use `# type: ignore` when needed

### Test Failures
**Problem**: Unit tests failing
**Solution**:
1. Update test dependencies
2. Check test data fixtures
3. Run specific test for details:
   ```bash
   pytest tests/unit/test_carousel_poster.py -v
   ```

## Getting Help

If you're still having issues:

1. Check the logs:
   ```bash
   tail -f logs/app_debug.log
   ```

2. Enable debug mode in `.env`:
   ```
   DEBUG=True
   LOG_LEVEL=DEBUG
   ```

3. Use the debug endpoints:
   - `/debug/carousel`
   - `/debug/send-test`
   - `/debug/error-queue`

4. Open an issue on GitHub with:
   - Error message
   - Relevant logs
   - Steps to reproduce
   - Environment details
