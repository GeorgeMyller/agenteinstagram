# API Reference

## Base URL
Por padrão: `http://localhost:5001`

## Endpoints

### Publicação de Imagem
`POST /api/post/image`
```json
{
  "image": "file_content_in_bytes",
  "caption": "Your caption here",
  "apply_border": true,
  "generate_caption": false
}
```

### Publicação de Carrossel
`POST /api/post/carousel`
```json
{
  "images": ["file_content_1_bytes", "file_content_2_bytes", ...],
  "caption": "Your carousel caption",
  "apply_border": true,
  "generate_caption": false
}
```

### Publicação de Vídeo
`POST /api/post/video`
```json
{
  "video": "file_content_bytes",
  "caption": "Your video caption",
  "is_reel": true,
  "generate_caption": false
}
```

### Status da Publicação
`GET /api/status/{task_id}`

### Geração de Legenda
`POST /api/generate/caption`
```json
{
  "image": "optional_image_content_bytes",
  "video": "optional_video_content_bytes",
  "prompt": "Optional prompt for caption generation"
}
```

## Tipos de Eventos
- `text`: Mensagens de texto e comandos
- `image`: Upload de imagens
- `video`: Upload de vídeos
- `document`: Anexos de documentos

## Boas Práticas
1. Implemente tratamento de erros
2. Use backoff exponencial
3. Valide mídia antes do upload
4. Monitore limites de taxa
5. Use endpoints de debug para troubleshooting
6. Implement token refresh
7. Validate input parameters
