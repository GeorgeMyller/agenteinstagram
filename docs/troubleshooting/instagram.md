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

#### Error 24 - User Rate Limit
**Problem**: Too many requests
**Solutions**:
1. Rate limiting is automatically implemented in our service.r service.
2. Use exponential backoff for retries in your integrations if needed. in your integrations if needed.
3. Batch operations when possible.

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
   Format: JPEG/PNG/WebP
   Aspect Ratio: 1:1 to 1.91:1
   Resolution: 320x320 minimum
   Size: <8MB
   ```
3. Check detailed error messages in logs using `python monitor.py`.3. Check logs for detailed error messages using `python monitor.py`

#### Error 2207001 - Media Upload FailedFailed
**Problem**: Upload process failedpload process failed
**Solutions**:
1. Check network connectivity
2. Verify file isn't corruptedupted
3. Try reducing file size
4. Use our automatic optimization:utomatic optimization:
   ```python
   from instagram.media_optimizer import optimize_mediamizer import optimize_media
   optimize_media(file_path)imize_media(file_path)
   ```   ```
5. Check detailed error messages in logs using `python monitor.py`.rror messages using `python monitor.py`

### Carousel Specific Issues

#### Error 2207024 - Invalid Carousel7024 - Invalid Carousel
**Problem**: Carousel validation failed
**Solutions**:
1. Verify all images meet requirements:meet requirements:
   - Same aspect ratioo
   - 2-10 images only
   - All images < 8MB
2. Check carousel sequence2. Check carousel sequence
3. Validate media before upload using project validation tools.validation tools in your project

#### Error 35001 - Carousel Publish Failed01 - Carousel Publish Failed
**Problem**: Publishing process failed
**Solutions**:
1. Check all image URLs are accessibleaccessible
2. Verify caption length (≤2200 characters)2. Verify caption length (≤2200 characters)
3. Check hashtag count (≤30)ag count (≤30)
4. Validate media before upload using project validation tools.4. Validate media before upload using the validation tools in your project

## Debug Toolsg Tools

### Token Validation Token Validation
```bash```bash
curl -X GET "https://graph.facebook.com/v22.0/debug_token?input_token={token}&access_token={app-token}".facebook.com/v22.0/debug_token?input_token={token}&access_token={app-token}"
```

### Media Container Status Media Container Status
```bash```bash
curl -X GET "https://graph.facebook.com/v22.0/{container-id}?fields=status_code,status"/graph.facebook.com/v22.0/{container-id}?fields=status_code,status"
```

### Rate Limit Check Rate Limit Check
```bash```bash
curl -X GET "https://graph.facebook.com/v22.0/me/content_publishing_limit"s://graph.facebook.com/v22.0/me/content_publishing_limit"
``````

## Best Practices

### Media Preparation
1. Always validate media before upload upload
2. Use our built-in optimization tools2. Use our built-in optimization tools
3. Keep aspect ratios consistentios consistent
4. Compress media appropriately

### Error Handling
1. Implement proper retry logictry logic
2. Use exponential backoff2. Use exponential backoff
3. Log detailed error informationor information
4. Monitor rate limits
5. Implement robust logging and error tracking.

### Token Managemen
1. Store tokens securely2. Implement token refresh
2. Implement token refreshken expiration
3. Monitor token expiration4. Use appropriate scopes
4. Use appropriate scopes

## Monitoring

### Health Checksion
1. Regular token validation2. Media container status monitoring
2. Media container status monitoringit tracking
3. Rate limit tracking
4. Error rate monitoring
5. Logging and Error Handlingling

### Logging
Important fields to log: to log:
- Request ID- Request ID
- Error codes
- HTTP status- HTTP status
- Response body
- Media metadata

## Recovery Procedures

### Failed Upload Recovery### Failed Upload Recovery
1. Check error logs
2. Verify media statusus
3. Retry with optimizationimization
4. Clear temporary filesfiles

### Rate Limit Recovery### Rate Limit Recovery
1. Implement backoff
2. Queue requestss
3. Batch operations
4. Monitor limits

### Token Issues Recovery### Token Issues Recovery
1. Refresh tokenken
2. Verify permissions2. Verify permissions
3. Check app status
4. Update credentials

## Prevention

### Media Validation### Media Validation
- Pre-validate all media
- Check formats and sizesand sizes
- Verify aspect ratiosratios
- Test with sample contente content

### Performance Optimization### Performance Optimization
- Compress media
- Batch requestss
- Cache responses
- Monitor usage

### Monitoring Setup### Monitoring Setup
- Set up alerts
- Monitor rate limits- Monitor rate limits
- Track error rates
- Log key metrics

## Getting Help

### Official Resourcesesources
- [Instagram Graph API Documentation](https://developers.facebook.com/docs/instagram-api/)ocumentation](https://developers.facebook.com/docs/instagram-api/)
- [Media Requirements](https://developers.facebook.com/docs/instagram-api/reference/ig-media)ts](https://developers.facebook.com/docs/instagram-api/reference/ig-media)
- [Error Codes](https://developers.facebook.com/docs/instagram-api/reference/error-codes)/developers.facebook.com/docs/instagram-api/reference/error-codes)

### Our Support### Our Support
1. Check debug endpoints (if available in your setup)
2. Review log files (`logs/app.log`, `logs/monitoring.log`)2. Review log files





Remember to always test in development first and maintain proper error handling throughout your implementation.4. Open GitHub issue3. Use validation tools provided in the project.3. Use validation tools
4. Open GitHub issue

Remember to always test in development first and maintain proper error handling throughout your implementation.
