# Instagram API Troubleshooting

This guide focuses specifically on Instagram API issues and their solutions.

## Common Instagram API Errors

### Authentication Errors

#### Error 190 - Access Token Invalid
**Problem**: Token validation failed
**Solutions**:
1. Check token expiration
2. Verify correct permissions are granted:
   - instagram_basic
   - instagram_content_publish
   - instagram_manage_insights
3. Generate new token in Meta Developer Console

#### Error 24 - User Rate Limi
**Problem**: Too many requests
**Solutions**:
1. Implement rate limiting (built into our service)
2. Use exponential backoff for retries
3. Batch operations when possible

### Media Upload Errors

#### Error 2207026 - Media Processing Failed
**Problem**: Media format not supported
**Solutions**:
1. Video Requirements:
   ```
   Format: MP4/MOV
   Codec: H.264
   Audio: AAC
   Aspect Ratio: 1:1 to 1.91:1
   Resolution: 600x600 minimum
   Duration: 3-90 seconds
   ```
2. Image Requirements:
   ```
   Format: JPEG/PNG
   Aspect Ratio: 1:1 to 1.91:1
   Resolution: 320x320 minimum
   Size: <8MB
   ```

#### Error 2207001 - Media Upload Failed
**Problem**: Upload process failed
**Solutions**:
1. Check network connectivity
2. Verify file isn't corrupted
3. Try reducing file size
4. Use our automatic optimization:
   ```python
   from instagram.media_optimizer import optimize_media
   optimize_media(file_path)
   ```

### Carousel Specific Issues

#### Error 2207024 - Invalid Carousel
**Problem**: Carousel validation failed
**Solutions**:
1. Verify all images meet requirements:
   - Same aspect ratio
   - 2-10 images only
   - All images < 8MB
2. Check carousel sequence
3. Validate media before upload

#### Error 35001 - Carousel Publish Failed
**Problem**: Publishing process failed
**Solutions**:
1. Check all image URLs are accessible
2. Verify caption length (≤2200 characters)
3. Check hashtag count (≤30)

## Debug Tools

### Token Validation
```bash
curl -X GET "https://graph.facebook.com/v22.0/debug_token?input_token={token}&access_token={app-token}"
```

### Media Container Status
```bash
curl -X GET "https://graph.facebook.com/v22.0/{container-id}?fields=status_code,status"
```

### Rate Limit Check
```bash
curl -X GET "https://graph.facebook.com/v22.0/me/content_publishing_limit"
```

## Best Practices

### Media Preparation
1. Always validate media before upload
2. Use our built-in optimization tools
3. Keep aspect ratios consisten
4. Compress media appropriately

### Error Handling
1. Implement proper retry logic
2. Use exponential backoff
3. Log detailed error information
4. Monitor rate limits

### Token Managemen
1. Store tokens securely
2. Implement token refresh
3. Monitor token expiration
4. Use appropriate scopes

## Monitoring

### Health Checks
1. Regular token validation
2. Media container status monitoring
3. Rate limit tracking
4. Error rate monitoring

### Logging
Important fields to log:
- Request ID
- Error codes
- HTTP status
- Response body
- Media metadata

## Recovery Procedures

### Failed Upload Recovery
1. Check error logs
2. Verify media status
3. Retry with optimization
4. Clear temporary files

### Rate Limit Recovery
1. Implement backoff
2. Queue requests
3. Batch operations
4. Monitor limits

### Token Issues Recovery
1. Refresh token
2. Verify permissions
3. Check app status
4. Update credentials

## Prevention

### Media Validation
- Pre-validate all media
- Check formats and sizes
- Verify aspect ratios
- Test with sample conten

### Performance Optimization
- Compress media
- Batch requests
- Cache responses
- Monitor usage

### Monitoring Setup
- Set up alerts
- Monitor rate limits
- Track error rates
- Log key metrics

## Getting Help

### Official Resources
- [Instagram Graph API Documentation](https://developers.facebook.com/docs/instagram-api/)
- [Media Requirements](https://developers.facebook.com/docs/instagram-api/reference/ig-media)
- [Error Codes](https://developers.facebook.com/docs/instagram-api/reference/error-codes)

### Our Suppor
1. Check debug endpoints
2. Review log files
3. Use validation tools
4. Open GitHub issue

Remember to always test in development first and maintain proper error handling throughout your implementation.
