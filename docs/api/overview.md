# API Reference

## Base URL
Por padrão: `http://localhost:5001`

## Endpoints

### Publicação de Imagem
`POST /messages-upser`
```json
{
  "type": "image",
  "data": {
    "base64": "..."
  }
}
```

### Iniciar Carrossel
`POST /messages-upser`
```json
{
  "text": "iniciar carrossel",
  "group_id": "your_group_id"
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
