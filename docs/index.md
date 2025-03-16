# Instagram Agent Documentation

## Visão Geral
Instagram Agent é um sistema avançado de automação para redes sociais que ajuda a gerenciar e automatizar a publicação de conteúdo no Instagram através de uma interface API robusta. Suporta diversos tipos de conteúdo, incluindo imagens individuais, carrosséis, e vídeos/reels.

## Funcionalidades
- **Publicação de imagens** com geração automática de legendas
- **Suporte a carrosséis** com múltiplas imagens (2-10 imagens)
- **Upload de vídeos e reels** com otimização automática
- **Geração de legendas com IA** usando CrewAI
- **Descrição inteligente de conteúdo** usando API Gemini
- **Integração com webhooks** para publicação automatizada
- **Interface web** para gerenciamento manual de conteúdo
- **Sistema de filas** para processar grandes volumes de publicações
- **Monitoramento em tempo real** do status das publicações
- **Personalização de bordas e filtros** para identidade visual consistente
- **Processamento em lote** para publicações programadas

## Links Rápidos
- [Guia de Instalação](installation/quickstart.md)
- [Documentação da API](api/README.md)
- [Guia de Configuração](guides/configuration.md)
- [Solução de Problemas](troubleshooting/common.md)

## Tipos de Conteúdo Suportados

### Imagens Individuais
- Formatos: JPG, PNG, WebP
- Aplicação automática de filtros e bordas personalizáveis
- Geração de legendas com IA
- Otimização automática de resolução e proporção
- Suporte a hashtags inteligentes

### Carrosséis
- 2 a 10 imagens por carrossel
- Mesmos formatos e processamento de imagens individuais
- Narrativa coesa entre imagens com IA
- Ideal para contar histórias ou mostrar produtos
- Controle de transições e ordem das imagens

### Vídeos e Reels
- Formatos: MP4, MOV, AVI (com conversão automática)
- Otimização automática para requisitos do Instagram
- Opção de compartilhar no feed ou apenas como Reels
- Processamento de áudio e legendas automáticas
- Suporte a templates de vídeo

## Modos de Uso

### Interface Web (Streamlit)
Acesse todas as funcionalidades através de uma interface amigável:
- Upload e pré-visualização de mídia
- Personalização de legendas e hashtags
- Programação de publicações
- Controle de publicação
- Dashboard de métricas e desempenho

### API REST
Integre com outros sistemas usando a API REST completa:
- Endpoints para todos os tipos de mídia
- Sistema de webhooks para automação
- Monitoramento de status
- Autenticação segura
- Documentação interativa com Swagger/OpenAPI

### Webhooks
Receba e processe mensagens para publicação automática:
- Comandos via texto para iniciar carrosséis
- Upload de imagens e vídeos
- Controle de status via mensagens
- Notificações em tempo real
- Integrações com plataformas de terceiros

## Recursos Técnicos
- Processamento robusto de imagens e vídeos
- Sistema de filas para gerenciar publicações
- Tratamento avançado de erros e limites de taxa
- Monitoramento de status em tempo real
- Cache inteligente para otimização de recursos
- Sistema de logs detalhados para depuração
- Arquitetura modular e extensível
- Suporte a múltiplas contas do Instagram

## Requisitos do Sistema
- Python 3.10+
- Dependências listadas em requirements.txt
- Acesso à API do Instagram
- Armazenamento suficiente para processamento de mídia
- Conexão estável com a internet

## Contribuindo
Contribuições são bem-vindas! Por favor, consulte nosso guia de contribuição antes de enviar pull requests.

Para começar, veja o [Guia de Instalação](installation/quickstart.md) ou a [Documentação da API](api/README.md).
