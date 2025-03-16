# Guia de Início Rápido

Comece a usar o Instagram Agent rapidamente seguindo este guia.

## Pré-requisitos

Antes de começar, certifique-se de que você tem:

- Python 3.10 ou mais recente
- FFmpeg instalado para processamento de vídeos
- Git para controle de versão
- Conta Instagram Business ou Creator
- Chaves de API e tokens necessários

## Instalação

1. Clone o repositório:
   ```bash
   git clone https://github.com/GeorgeMyller/agenteinstagram.git
   cd agenteinstagram
   ```

2. Crie um ambiente virtual e ative-o:
   ```bash
   python -m venv venv
   # No Windows
   venv\Scripts\activate
   # No macOS/Linux
   source venv/bin/activate
   ```

3. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure seu ambiente:
   - Copie `.env.example` para `.env` (se disponível)
   - Preencha suas chaves de API e tokens
   - Configure caminhos e configurações

5. Valide sua configuração:
   ```bash
   python tests/check_job_status.py
   ```

## Teste Rápido

Teste sua instalação:

1. Inicie o servidor:
   ```bash
   python app.py
   ```

2. Em outro terminal, teste o endpoint:
   ```bash
   curl http://localhost:5001/status
   ```

## Usando a Interface Web

1. Inicie a interface Streamlit:
   ```bash
   streamlit run streamlit_app.py
   ```

2. Abra seu navegador em `http://localhost:8501`

3. Experimente fazer upload de uma imagem e publicá-la no Instagram

## Configuração de Bordas

Para configurar as bordas personalizadas:

```bash
python setup_border.py
```

Este script permite definir as configurações de borda padrão para suas imagens.

## Monitoramento

Para iniciar o serviço de monitoramento:

```bash
python monitor.py
```

Este serviço acompanha o status das publicações e fornece atualizações em tempo real.

## Próximos Passos

- Leia o [Guia de Configuração](../guides/configuration.md) para configuração detalhada
- Consulte o [Guia do Usuário](../guides/setup.md) para instruções de uso
- Revise [Problemas Comuns](../troubleshooting/common.md) se encontrar dificuldades

## Configuração de Desenvolvimento

Para desenvolvimento, instale ferramentas adicionais:

```bash
pip install -r requirements-dev.txt
```

Isso inclui:
- Ferramentas de teste (pytest)
- Formatação de código (black)
- Verificação de tipos (mypy)
- Ferramentas de documentação (mkdocs)

Execute os testes para verificar se tudo funciona:
```bash
python -m pytest
```
