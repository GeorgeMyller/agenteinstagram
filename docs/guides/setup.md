# Guia de Configuração

Este guia fornece instruções detalhadas para configurar corretamente o Instagram Agent.

## Configuração do Ambiente

### Variáveis de Ambiente

As seguintes variáveis de ambiente devem ser configuradas no arquivo `.env`:

```
# Credenciais do Instagram
INSTAGRAM_USERNAME=sua_conta_instagram
INSTAGRAM_PASSWORD=sua_senha

# Credenciais da API Gemini (para geração de legendas)
GEMINI_API_KEY=sua_chave_api_gemini

# Configurações de Servidor
SERVER_PORT=5001
DEBUG_MODE=False

# Caminhos para Armazenamento
TEMP_DIR=./temp
UPLOAD_DIR=./uploads
LOG_DIR=./logs

# Configurações de Processamento
MAX_IMAGE_SIZE=10000000  # 10MB em bytes
MAX_VIDEO_SIZE=50000000  # 50MB em bytes
```

### Configuração do Serviço

O sistema pode ser executado como um serviço para garantir que ele continue funcionando mesmo após reinicializações do servidor.

#### Linux (systemd)

1. Crie um arquivo de serviço:

```bash
sudo nano /etc/systemd/system/instagram-agent.service
```

2. Adicione o seguinte conteúdo:

```
[Unit]
Description=Instagram Agent Service
After=network.target

[Service]
User=seu_usuario
WorkingDirectory=/caminho/para/agenteinstagram
ExecStart=/caminho/para/python /caminho/para/agenteinstagram/app.py
Restart=always
RestartSec=10
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=instagram-agent

[Install]
WantedBy=multi-user.target
```

3. Habilite e inicie o serviço:

```bash
sudo systemctl enable instagram-agent
sudo systemctl start instagram-agent
```

#### macOS (launchd)

1. Crie um arquivo plist:

```bash
nano ~/Library/LaunchAgents/com.user.instagram-agent.plist
```

2. Adicione o seguinte conteúdo:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.instagram-agent</string>
    <key>ProgramArguments</key>
    <array>
        <string>/caminho/para/python</string>
        <string>/caminho/para/agenteinstagram/app.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>WorkingDirectory</key>
    <string>/caminho/para/agenteinstagram</string>
    <key>StandardOutPath</key>
    <string>/caminho/para/agenteinstagram/logs/stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/caminho/para/agenteinstagram/logs/stderr.log</string>
</dict>
</plist>
```

3. Carregue o serviço:

```bash
launchctl load ~/Library/LaunchAgents/com.user.instagram-agent.plist
```

## Configuração de Bordas e Filtros

O arquivo `setup_border.py` permite personalizar as configurações de borda e filtros aplicados às suas imagens.

Execute o script e siga as instruções interativas:

```bash
python setup_border.py
```

Você pode configurar:

- Largura da borda
- Cor da borda
- Filtros padrão para aplicar às imagens
- Relação de aspecto para redimensionamento

Estas configurações serão salvas e aplicadas automaticamente a todas as imagens carregadas.

## Configuração do Monitoramento

O sistema inclui um painel de monitoramento para acompanhar o status das publicações e o desempenho do sistema.

### Configuração do Painel

1. Execute o script de monitoramento:

```bash
python monitor.py
```

2. Acesse o painel em seu navegador:

```
http://localhost:5002/dashboard
```

O painel de monitoramento mostrará:

- Status de publicações recentes
- Taxas de sucesso/falha
- Tempo médio de processamento
- Erros comuns e soluções

## Configuração do Streamlit

Para personalizar a interface Streamlit:

1. Crie um arquivo de configuração:

```bash
mkdir -p ~/.streamlit
nano ~/.streamlit/config.toml
```

2. Adicione as configurações personalizadas:

```toml
[theme]
primaryColor = "#4ed2ff"
backgroundColor = "#ffffff"
secondaryBackgroundColor = "#f0f0f0"
textColor = "#262730"
font = "sans serif"

[server]
port = 8501
enableCORS = false
```

3. Reinicie a aplicação Streamlit para aplicar as alterações.

## Integração com Webhooks

Para configurar webhooks para notificações em tempo real:

1. Configure a URL do webhook no arquivo `.env`:

```
WEBHOOK_URL=https://seu-sistema.com/webhooks/instagram
WEBHOOK_SECRET=seu_segredo
```

2. O sistema enviará atualizações de status para esta URL a cada mudança no status de uma publicação.

3. Os payloads de webhook incluirão:
   - ID da tarefa
   - Status atual
   - Timestamp
   - Detalhes da mídia
   - Links para a publicação (quando concluída)

## Próximos Passos

Após concluir a configuração:

1. Realize um [teste inicial](../installation/quickstart.md#teste-rápido) para verificar se tudo está funcionando corretamente.

2. Configure a [validação de mídia](./media_validation.md) para garantir que todas as publicações atendam aos requisitos do Instagram.

3. Consulte a [solução de problemas](../troubleshooting/common.md) se encontrar dificuldades.

