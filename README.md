# Agent Social Media - CrewAI2 📱🤖

## Português 🇧🇷

### Descrição do Projeto
Este projeto é uma ferramenta de automação social media que integra CrewAI e Gemini para gerenciar postagens no Instagram. Oferece geração inteligente de legendas, processamento de imagens e suporte a múltiplos formatos de mídia.

> **Origem do Projeto**: Este projeto foi inspirado pelo livro [CrewAI 2 - Intermediário](https://physia.com.br) do Professor Sandeco, que apresenta conceitos avançados de automação e IA colaborativa para desenvolvimento de agentes inteligentes.

### Funcionalidades Principais 🚀
- Geração de legendas usando CrewAI
- Descrição de imagens com API Gemini
- Processamento de imagens e vídeos
- Suporte a carrosséis do Instagram
- Interface web via Streamlit
- API REST para integrações

### Pré-requisitos 📋
- Python 3.10+
- FFmpeg para processamento de vídeos
- Conta Instagram Business/Creator
- Chave API Gemini
- UV (gerenciador de pacotes Python)

### Como Usar 🚀

#### Interface Gráfica (Recomendado)
1. Instale as dependências:
   ```bash
   uv sync
   ```
2. Execute a interface Streamlit:
   ```bash
   streamlit run streamlit_app.py
   ```
3. Acesse em `http://localhost:8501`

#### API (Webhooks)
1. Instale o UV e crie ambiente virtual:
   ```bash
   pip install uv
   uv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   uv sync
   ```
2. Configure o `.env` com suas credenciais
3. Inicie o servidor Flask

### Estrutura do Projeto 📂
- `app.py`: Endpoints Flask
- `instagram/`: Módulos de integração Instagram
- `crew_post_instagram.py`: Configuração CrewAI
- `message.py`: Processamento de mensagens
- `streamlit_app.py`: Interface gráfica

### Licença
MIT License - Veja LICENSE para detalhes.

---

## English 🇺🇸

### Project Description
This project is a comprehensive tool for automating and managing social media posts, with a special focus on Instagram. It integrates the CrewAI library to generate creative captions, along with robust image processing features – including filters, border addition, image upload via Imgur, and Instagram posting. It also features intelligent image description using Google's Gemini API, message processing (text, audio, image, and document) and integration with the Evolution API.

> **Project Origin**: This project was inspired by Professor Sandeco's book [CrewAI 2 - Intermediate](https://physia.com.br), which presents advanced concepts of automation and collaborative AI for developing intelligent agents.

### Main Features 🚀
- Caption generation with CrewAI
- Image processing: filters, corrections, and border additions
- Image upload using Imgur
- Instagram post publishing
- Intelligent image description with Gemini API
- Message processing and sending via Evolution API
- Flask endpoints for webhooks and service integration

### How to Use 🚀

#### Graphical Interface (Recommended)
1. Install dependencies:
   ```bash
   uv sync
   ```
2. Run the Streamlit interface:
   ```bash
   streamlit run streamlit_app.py
   ```
3. Access the web interface at `http://localhost:8501`
4. Use the sidebar to configure:
   - Writing style
   - Narrative person
   - Sentiment
   - Emoji and informal language usage
5. Upload an image and add an optional caption
6. Click "Post to Instagram" to publish

#### API (Webhooks)
1. Install UV:
   ```bash
   pip install uv
   ```
2. Create the virtual environment:
   ```bash
   uv venv
   ```
3. Activate the virtual environment (use `venv\Scripts\activate` on Windows):
   ```bash
   source venv/bin/activate
   ```
4. Synchronize dependencies and launch the application:
   ```bash
   uv sync
   ```

### Project Structure 📂
- `app.py`: Flask endpoints for message processing.
- `instagram/` folder: Modules for creating posts, image uploading, filters, border additions and image description.
- `crew_post_instagram.py`: CrewAI configuration and caption generation tasks.
- `message.py` and `send_message.py`: Message processing and sending.
- `paths.py`: File path configurations.
- `streamlit_app.py`: Graphical interface for post management
- Other auxiliary files and scripts.

### Contribution
Contributions are welcome! Feel free to open issues and pull requests for improvements and fixes.

### License
This project is licensed under the MIT License. See the LICENSE file for more details.

Happy coding! 😄