# Documentação da API

Esta seção contém a documentação completa da API REST do Instagram Agent.

## Visão Geral

A API do Instagram Agent permite o controle programático de todas as funcionalidades de publicação e gerenciamento de conteúdo para o Instagram. Ela fornece endpoints para upload de mídia, geração de legendas, programação de publicações e monitoramento de status.

## Autenticação

Todas as requisições à API devem incluir um token de autenticação no cabeçalho:

```
Authorization: Bearer SEU_TOKEN_AQUI
```

Para obter um token de acesso, entre em contato com o administrador do sistema ou configure suas próprias credenciais no arquivo `.env`.

## Formato de Resposta

Todas as respostas da API são retornadas no formato JSON. Um exemplo de resposta bem-sucedida:

```json
{
  "success": true,
  "data": {
    "id": "12345678",
    "status": "completed",
    "media_url": "https://instagram.com/p/AbCdEfGhIjK/"
  },
  "message": "Publicação realizada com sucesso"
}
```

Em caso de erro, o formato será:

```json
{
  "success": false,
  "error": {
    "code": "invalid_media",
    "message": "O formato de mídia não é suportado"
  }
}
```

## Endpoints Principais

### Publicação de Imagem

**Endpoint**: `POST /api/post/image`

**Descrição**: Publica uma única imagem no Instagram.

**Parâmetros**:
- `image`: Arquivo de imagem (JPG, PNG)
- `caption`: Legenda para a publicação (opcional)
- `generate_caption`: Boolean para gerar legenda automaticamente (opcional, padrão: false)
- `apply_border`: Boolean para aplicar borda na imagem (opcional, padrão: true)

**Exemplo de Resposta**:
```json
{
  "success": true,
  "data": {
    "post_id": "12345678",
    "status": "processing",
    "task_id": "task-123456"
  }
}
```

### Publicação de Carrossel

**Endpoint**: `POST /api/post/carousel`

**Descrição**: Publica um carrossel de imagens no Instagram.

**Parâmetros**:
- `images[]`: Array de arquivos de imagem (2-10 imagens)
- `caption`: Legenda para a publicação (opcional)
- `generate_caption`: Boolean para gerar legenda automaticamente (opcional, padrão: false)
- `apply_border`: Boolean para aplicar borda nas imagens (opcional, padrão: true)

**Exemplo de Resposta**:
```json
{
  "success": true,
  "data": {
    "post_id": "12345678",
    "image_count": 5,
    "status": "processing",
    "task_id": "task-123456"
  }
}
```

### Publicação de Vídeo

**Endpoint**: `POST /api/post/video`

**Descrição**: Publica um vídeo ou reel no Instagram.

**Parâmetros**:
- `video`: Arquivo de vídeo (MP4, MOV)
- `caption`: Legenda para a publicação (opcional)
- `generate_caption`: Boolean para gerar legenda automaticamente (opcional, padrão: false)
- `is_reel`: Boolean para publicar como reel (opcional, padrão: false)

**Exemplo de Resposta**:
```json
{
  "success": true,
  "data": {
    "post_id": "12345678",
    "status": "processing",
    "task_id": "task-123456",
    "estimated_time": 120
  }
}
```

### Status da Publicação

**Endpoint**: `GET /api/status/{task_id}`

**Descrição**: Verifica o status de uma publicação em andamento.

**Parâmetros**:
- `task_id`: ID da tarefa retornado na criação da publicação

**Exemplo de Resposta**:
```json
{
  "success": true,
  "data": {
    "task_id": "task-123456",
    "status": "completed",
    "post_id": "12345678",
    "media_url": "https://instagram.com/p/AbCdEfGhIjK/",
    "completed_at": "2023-06-15T14:32:10Z"
  }
}
```

### Geração de Legenda

**Endpoint**: `POST /api/generate/caption`

**Descrição**: Gera uma legenda para uma mídia usando IA.

**Parâmetros**:
- `image`: Arquivo de imagem (opcional)
- `video`: Arquivo de vídeo (opcional)
- `prompt`: Instrução adicional para geração (opcional)

**Exemplo de Resposta**:
```json
{
  "success": true,
  "data": {
    "caption": "Aproveitando este momento mágico no pôr do sol! #natureza #paz #momentos",
    "hashtags": ["natureza", "paz", "momentos"]
  }
}
```

## Códigos de Status

- `200 OK`: Requisição bem-sucedida
- `201 Created`: Recurso criado com sucesso
- `400 Bad Request`: Parâmetros incorretos ou inválidos
- `401 Unauthorized`: Token de autenticação inválido ou ausente
- `404 Not Found`: Recurso não encontrado
- `429 Too Many Requests`: Limite de taxa excedido
- `500 Internal Server Error`: Erro interno do servidor

## Webhooks

Para configurar webhooks e receber atualizações em tempo real sobre o status das publicações, consulte a [documentação de webhooks](./webhooks.md).

## Exemplos de Código

### Python
```python
import requests

api_url = "http://localhost:5001/api"
headers = {"Authorization": "Bearer YOUR_TOKEN"}

# Publicar uma imagem
files = {"image": open("imagem.jpg", "rb")}
data = {"caption": "Minha primeira publicação via API", "apply_border": True}
response = requests.post(f"{api_url}/post/image", headers=headers, files=files, data=data)
print(response.json())
```

### JavaScript
```javascript
const axios = require('axios');
const FormData = require('form-data');
const fs = require('fs');

const apiUrl = 'http://localhost:5001/api';
const token = 'YOUR_TOKEN';

async function postImage() {
  const form = new FormData();
  form.append('image', fs.createReadStream('imagem.jpg'));
  form.append('caption', 'Minha primeira publicação via API');
  form.append('apply_border', 'true');
  
  try {
    const response = await axios.post(`${apiUrl}/post/image`, form, {
      headers: {
        ...form.getHeaders(),
        'Authorization': `Bearer ${token}`
      }
    });
    console.log(response.data);
  } catch (error) {
    console.error(error.response.data);
  }
}

postImage();
```

## Próximos Passos

- [Detalhes dos Endpoints](./overview.md)
- [Guia de Implementação](../guides/implementation.md)
- [Solução de Problemas](../troubleshooting/api-errors.md)

