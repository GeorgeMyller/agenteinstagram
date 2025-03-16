# Validação de Mídia

Este guia explica como a validação de mídia funciona no Instagram Agent e como configurá-la para garantir que todas as publicações atendam aos requisitos do Instagram.

## Requisitos do Instagram

O Instagram tem requisitos específicos para diferentes tipos de mídia. O sistema de validação do Instagram Agent garante que todo o conteúdo enviado atenda a esses requisitos.

### Requisitos para Imagens

- **Formatos suportados**: JPG, PNG
- **Resolução mínima**: 320 x 320 pixels
- **Resolução máxima recomendada**: 1080 x 1080 pixels (quadrado)
- **Proporções suportadas**: 
  - 1:1 (quadrado)
  - 4:5 (retrato)
  - 1.91:1 (paisagem)
- **Tamanho máximo do arquivo**: 8MB

### Requisitos para Carrosséis

- **Número de imagens**: 2-10 imagens
- **Consistência**: Todas as imagens devem ter a mesma proporção
- **Formatos e limites**: Mesmos das imagens individuais

### Requisitos para Vídeos

- **Formatos suportados**: MP4, MOV
- **Codec de vídeo**: H.264
- **Codec de áudio**: AAC
- **Resolução mínima**: 600 x 600 pixels
- **Relação de aspecto**: 1:1 a 1.91:1 (horizontal) ou 4:5 (vertical)
- **Duração**:
  - Feed: 3-60 segundos
  - Reels: 3-90 segundos
- **Tamanho máximo**: 100MB

## Sistema de Validação

O Instagram Agent possui um sistema de validação automática que verifica:

1. Formato do arquivo
2. Dimensões e proporção
3. Tamanho do arquivo
4. Duração (para vídeos)
5. Qualidade da mídia

## Configuração da Validação

### Modificando Limites

Você pode ajustar os limites de validação editando o arquivo `.env`:

```
# Limites de Validação
MAX_IMAGE_SIZE=8000000  # 8MB em bytes
MAX_VIDEO_SIZE=100000000  # 100MB em bytes
MIN_IMAGE_DIMENSION=320
MAX_IMAGE_DIMENSION=1080
MIN_VIDEO_DURATION=3
MAX_VIDEO_DURATION_FEED=60
MAX_VIDEO_DURATION_REEL=90
```

### Desativando Validações Específicas

Para cenários de teste ou casos especiais, você pode desativar certas validações:

```
SKIP_DIMENSION_CHECK=False
SKIP_SIZE_CHECK=False
SKIP_FORMAT_CHECK=False
SKIP_DURATION_CHECK=False
```

## Pré-processamento de Mídia

### Redimensionamento Automático

O sistema pode redimensionar automaticamente imagens para os requisitos do Instagram:

```python
# Exemplo de configuração de redimensionamento
RESIZE_OVERSIZED_IMAGES=True
TARGET_RESOLUTION=1080  # Lado mais longo em pixels
PRESERVE_ASPECT_RATIO=True
```

### Otimização de Vídeo

Para vídeos que não atendem aos requisitos, o sistema pode realizar otimização automática:

1. Conversão para formato compatível (H.264/AAC)
2. Redimensionamento para resolução adequada
3. Ajuste de bitrate e qualidade
4. Correção de duração (corte ou loop)

Esta otimização ocorre automaticamente quando necessário.

## Detecção de Problemas Comuns

O sistema identifica automaticamente os seguintes problemas:

### Problemas de Imagem

- Resolução muito baixa
- Proporção não suportada
- Formato de arquivo incompatível
- Imagem corrompida
- Metadados excessivos

### Problemas de Vídeo

- Codec incompatível
- Áudio ausente ou com problema
- Duração inadequada
- Taxa de quadros muito baixa
- Bitrate insuficiente

## Solução de Problemas de Validação

Se suas mídias falharem na validação:

### Para Imagens

1. Redimensione usando ferramentas como Photoshop, GIMP ou online
2. Verifique a proporção (1:1, 4:5, 1.91:1)
3. Converta para JPG ou PNG se estiver usando outros formatos
4. Compacte para reduzir o tamanho do arquivo

### Para Vídeos

1. Use o FFmpeg para converter para formato compatível:
   ```bash
   ffmpeg -i input.mov -c:v libx264 -preset slow -crf 22 -c:a aac -b:a 128k output.mp4
   ```

2. Redimensione vídeos:
   ```bash
   ffmpeg -i input.mp4 -vf scale=1080:1080 output.mp4
   ```

3. Ajuste a duração:
   ```bash
   # Para cortar para 60 segundos
   ffmpeg -i input.mp4 -t 60 -c copy output.mp4
   ```

## Testes de Validação

Para testar se sua mídia passa na validação:

```bash
python tests/test_media.py --image path/to/image.jpg
python tests/test_media.py --video path/to/video.mp4
```

## Próximos Passos

- Consulte a [Configuração de Bordas](setup.md#configuração-de-bordas-e-filtros) para personalizar o estilo visual
- Veja a [Solução de Problemas](../troubleshooting/common.md) para lidar com erros específicos de validação
