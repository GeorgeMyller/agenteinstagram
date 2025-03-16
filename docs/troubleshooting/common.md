# Problemas Comuns e Soluções

Este guia cobre os problemas mais comuns que você pode encontrar ao usar o Instagram Agent e suas soluções.

## Problemas de Instalação

### Incompatibilidade de Versão do Python

**Problema**: Erro sobre requisito de versão do Python não atendido

**Solução**:
1. Instale Python 3.10 ou mais recente
2. Crie um novo ambiente virtual:
   ```bash
   python3.10 -m venv venv
   source venv/bin/activate  # ou venv\Scripts\activate no Windows
   ```

### FFmpeg Ausente

**Problema**: O processamento de vídeo falha com erros relacionados ao FFmpeg

**Solução**:
- No macOS: `brew install ffmpeg`
- No Ubuntu/Debian: `sudo apt install ffmpeg`
- No Windows: Baixe do [site oficial do FFmpeg](https://ffmpeg.org/download.html)

### Dependências Não Instaladas

**Problema**: Módulo não encontrado ou erros de importação

**Solução**:
1. Verifique se todas as dependências foram instaladas:
   ```bash
   pip install -r requirements.txt
   ```
2. Considere usar o ambiente de desenvolvimento completo:
   ```bash
   pip install -e .
   ```

## Problemas de Configuração

### Variáveis de Ambiente Ausentes

**Problema**: Erros "Variável de ambiente X não encontrada"

**Solução**:
1. Copie `.env.example` para `.env` (se disponível)
2. Preencha todas as variáveis necessárias
3. Reinicie a aplicação para aplicar as alterações

### Chaves de API Inválidas

**Problema**: Erros de autenticação com Instagram/Gemini

**Solução**:
1. Verifique a validade das chaves de API
2. Regenere os tokens se estiverem expirados
3. Verifique os escopos de permissão

### Problemas de Diretório

**Problema**: Erros de permissão ou diretórios não encontrados

**Solução**:
1. Verifique se os diretórios necessários existem:
   ```bash
   mkdir -p temp logs uploads
   ```
2. Verifique as permissões de escrita:
   ```bash
   chmod -R 755 temp logs uploads
   ```

## Problemas com Instagram

### Falhas de Upload de Postagem

#### Erro 2207026 (Formato de Mídia Inválido)

**Problema**: Formato de vídeo não aceito pelo Instagram

**Solução**:
1. Certifique-se de que o vídeo atende aos requisitos:
   - Codec: H.264
   - Áudio: AAC
   - Resolução: ≥600x600
   - Duração: 3-90s (Reels)
2. Use a ferramenta de monitoramento para verificar erros detalhados:
   ```bash
   python monitor.py
   ```

#### Erro 190 (Token Inválido/Expirado)

**Problema**: Token da API do Instagram expirado

**Solução**:
1. Gere um novo token no Instagram
2. Atualize o arquivo `.env`
3. Reinicie a aplicação

### Problemas com Carrossel

#### Imagens Não Aparecem

**Problema**: Imagens do carrossel ausentes ou não carregam

**Solução**:
1. Verifique se as imagens estão no formato correto (JPG, PNG)
2. Verifique os caminhos das imagens
3. Limpe o diretório temp:
   ```bash
   rm -rf temp/*
   ```

#### Upload Travado

**Problema**: O upload do carrossel parece congelado

**Solução**:
1. Verifique os logs em `logs/app.log` (se disponível)
2. Reinicie o processo
3. Tente com menos imagens (máximo 10)

## Problemas de Desempenho

### Uso Elevado de Memória

**Problema**: Aplicativo consumindo muita memória

**Solução**:
1. Limpe diretórios temporários:
   ```bash
   rm -rf temp/*
   ```
2. Reduza o número máximo de imagens em carrosséis
3. Implemente limpeza automática

### Processamento de Vídeo Lento

**Problema**: O processamento de vídeo leva muito tempo

**Solução**:
1. Verifique a instalação do FFmpeg
2. Reduza as configurações de qualidade do vídeo
3. Use arquivos de vídeo menores
4. Ative a aceleração de hardware (se disponível)

## Problemas de Interface

### Interface Web Não Carrega

**Problema**: A interface Streamlit não carrega ou apresenta erros

**Solução**:
1. Verifique se o Streamlit está instalado:
   ```bash
   pip install streamlit
   ```
2. Verifique se o servidor está rodando:
   ```bash
   streamlit run streamlit_app.py
   ```
3. Limpe o cache do Streamlit:
   ```bash
   streamlit cache clear
   ```

### Visualizações de Imagem Quebradas

**Problema**: Imagens não são exibidas corretamente na interface

**Solução**:
1. Verifique os formatos de imagem suportados
2. Verifique permissões de leitura nos arquivos
3. Reinicie a aplicação Streamlit

## Problemas de Monitoramento

### Painel Não Mostra Dados

**Problema**: O painel de monitoramento está vazio ou incompleto

**Solução**:
1. Verifique se o serviço de monitoramento está em execução:
   ```bash
   python monitor.py
   ```
2. Verifique se há registros de monitoramento:
   ```bash
   cat logs/monitoring.log
   ```
3. Reinicie o serviço de monitoramento

## Problemas de Geração de Conteúdo

### Falha na Geração de Legendas

**Problema**: A geração automática de legendas falha ou produz resultados inadequados

**Solução**:
1. Verifique a chave de API Gemini no arquivo `.env`
2. Verifique a conexão com a API
3. Tente com um prompt mais específico ou detalhado
4. Verifique se a imagem tem conteúdo claro para descrição

### Falha na Aplicação de Bordas

**Problema**: As bordas não são aplicadas ou ficam distorcidas

**Solução**:
1. Verifique se o arquivo de borda existe em `assets/moldura.png`
2. Reconfigure as configurações da borda:
   ```bash
   python setup_border.py
   ```
3. Verifique se as imagens têm resolução adequada

## Problemas de Integração

### Webhook Não Recebe Eventos

**Problema**: O endpoint de webhook não recebe mensagens

**Solução**:
1. Verifique se a URL do webhook está correta
2. Verifique as configurações de rede/firewall
3. Teste com um endpoint de depuração

### Limite de Taxa

**Problema**: Erros de "muitas solicitações"

**Solução**:
1. Implemente recuo exponencial nos seus scripts
2. Reduza a frequência de solicitações
3. Use operações em lote quando possível

## Problemas de Desenvolvimento

### Erros de Verificação de Tipo

**Problema**: mypy reportando erros de tipo

**Solução**:
1. Instale stubs de tipo:
   ```bash
   pip install -r requirements-dev.txt
   ```
2. Adicione anotações de tipo
3. Use `# type: ignore` quando necessário

### Falhas em Testes

**Problema**: Testes unitários falhando

**Solução**:
1. Atualize as dependências de teste
2. Verifique os fixtures de dados de teste
3. Execute um teste específico para detalhes:
   ```bash
   pytest tests/test_carousel.py -v
   ```

## Obtendo Ajuda

Se você ainda estiver com problemas:

1. Verifique os logs:
   ```bash
   tail -f logs/app.log
   ```

2. Ative o modo de depuração no arquivo `.env`:
   ```
   DEBUG=True
   LOG_LEVEL=DEBUG
   ```

3. Use os endpoints de depuração (se disponíveis):
   - `/debug/status`
   - `/debug/test`
   
4. Abra uma issue no GitHub com:
   - Mensagem de erro
   - Logs relevantes
   - Passos para reproduzir
   - Detalhes do ambiente
