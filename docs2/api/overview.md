# API Reference

This section provides detailed documentation for all available API endpoints and services.

## Base URL

All API endpoints are relative to:
```
http://localhost:5001
```

## Authentication

Currently, the API uses basic configuration through environment variables. Ensure your `.env` file contains valid credentials for:
- Instagram API
- Imgur API
- Evolution API

## Available Endpoints

### Webhook Endpoin
`POST /messages-upsert`

Main webhook endpoint for receiving messages and commands.

### Debug Endpoints

#### Carousel Status
`GET /debug/carousel`

Returns current carousel state and configuration.

#### Test Message
`GET /debug/send-test`

Test the message sending functionality.

#### Service Tes
`GET /debug/test-carousel-service`

Test carousel service components.

#### Error Queue
`GET /debug/error-queue`

View the status of the carousel error queue.

#### Video Validation
`GET /debug/video-validation`

Test video file validation.

## Response Forma

All API responses follow this general format:

```json
{
    "success": true|false,
    "message": "Description of the result",
    "data": {
        // Response data specific to each endpoin
    },
    "error": {
        "code": "ERROR_CODE",
        "description": "Error description if success is false"
    }
}
```

## Error Codes

Common error codes you might encounter:

| Code | Description |
|------|-------------|
| 400  | Bad Request - Invalid parameters |
| 401  | Unauthorized - Authentication failed |
| 403  | Forbidden - Missing permissions |
| 404  | Not Found - Resource doesn't exist |
| 429  | Too Many Requests - Rate limit exceeded |
| 500  | Internal Server Error |

## Rate Limiting

The API implements rate limiting to prevent abuse:
- 100 requests per minute for most endpoints
- 30 requests per minute for Instagram posting endpoints
- 10 requests per minute for video processing

## Examples

### Upload an Image
```bash
curl -X POST http://localhost:5001/messages-upser
  -H "Content-Type: application/json"
  -d '{
    "type": "image",
    "data": {
      "base64": "..."
    }
  }'
```

### Start a Carousel
```bash
curl -X POST http://localhost:5001/messages-upser
  -H "Content-Type: application/json"
  -d '{
    "text": "iniciar carrossel",
    "group_id": "your_group_id"
  }'
```

## Webhook Event Types

The webhook endpoint handles these event types:

- `text`: Plain text messages and commands
- `image`: Image uploads
- `video`: Video uploads
- `document`: Document attachments

## Best Practices

1. Always include proper error handling
2. Implement exponential backoff for retries
3. Validate media before uploading
4. Keep track of rate limits
5. Check the debug endpoints for troubleshooting

## Integration Guidelines

When integrating with the API:

1. Start with test endpoints
2. Monitor the logs for issues
3. Implement proper error handling
4. Use the validation endpoints
5. Follow the rate limiting guidelines

See the [Integration Guide](../guides/integration.md) for detailed examples.
