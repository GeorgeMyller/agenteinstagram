# Instagram Agent Documentation

## Overview

Instagram Agent é um sistema avançado de automação para redes sociais que ajuda a gerenciar e automatizar a publicação de conteúdo no Instagram através de uma interface API robusta. Suporta diversos tipos de conteúdo, incluindo imagens individuais, carrosséis, e vídeos/reels.

## Features

- **Publicação de imagens** com geração automática de legendas
- **Suporte a carrosséis** com múltiplas imagens (2-10 imagens)
- **Upload de vídeos e reels** com otimização automática
- **Geração de legendas com IA** usando CrewAI
- **Descrição inteligente de conteúdo** usando API Gemini
- **Integração com webhooks** para publicação automatizada
- **Interface web** para gerenciamento manual de conteúdo
- **Sistema de filas** para processar grandes volumes de publicações
- **Monitoramento em tempo real** do status das publicações

## Quick Links

- [Guia de Instalação](installation/quickstart.md)
- [Documentação da API](api/README.md)
- [Guia de Configuração](guides/configuration.md)
- [Solução de Problemas](troubleshooting/common.md)

## Tipos de Conteúdo Suportados

### Imagens Individuais
- Formatos: JPG, PNG
- Aplicação automática de filtros e bordas
- Geração de legendas com IA

### Carrosséis
- 2 a 10 imagens por carrossel
- Mesmos formatos e processamento de imagens individuais
- Ideal para contar histórias ou mostrar produtos

### Vídeos e Reels
- Formatos: MP4, MOV
- Otimização automática para requisitos do Instagram
- Opção de compartilhar no feed

## Modos de Uso

### Interface Web (Streamlit)
Acesse todas as funcionalidades através de uma interface amigável:
- Upload e pré-visualização de mídia
- Personalização de legendas
- Controle de publicação

### API REST
Integre com outros sistemas usando a API REST completa:
- Endpoints para todos os tipos de mídia
- Sistema de webhooks para automação
- Monitoramento de status

### Webhooks
Receba e processe mensagens para publicação automática:
- Comandos via texto para iniciar carrosséis
- Upload de imagens e vídeos
- Controle de status via mensagens

## Recursos Técnicos

- Processamento robusto de imagens e vídeos
- Sistema de filas para gerenciar publicações
- Tratamento avançado de erros e limites de taxa
- Monitoramento de status em tempo real

Para começar, veja o [Guia de Instalação](installation/quickstart.md) ou a [Documentação da API](api/README.md).
