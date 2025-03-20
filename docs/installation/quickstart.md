# Guia de Início Rápido

## Pré-requisitos
- Python 3.10+
- FFmpeg instalado
- Git para controle de versão
- Conta Instagram Business/Creator
- Chaves de API necessárias (Gemini)

## Instalação

1. Clone o repositório:
   ```bash
   git clone https://github.com/GeorgeMyller/agenteinstagram.git
   cd agenteinstagram
   ```

2. Crie e ative o ambiente virtual:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

3. Instale dependências:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure o ambiente:
   - Copie `.env.example` para `.env`
   - Configure suas chaves e tokens

## Teste Rápido
1. Inicie o servidor:
   ```bash
   python app.py
   ```

2. Teste o status:
   ```bash
   curl http://localhost:5001/status
   ```

## Interface Web
1. Inicie o Streamlit:
   ```bash
   streamlit run streamlit_app.py
   ```

2. Acesse `http://localhost:8501`

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
