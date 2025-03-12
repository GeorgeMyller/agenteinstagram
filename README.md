# Agent Social Media - CrewAI2 📱🤖

## Português 🇧🇷

### Descrição do Projeto
Este projeto é uma ferramenta completa para automação e gerenciamento de postagens no Instagram, integrando CrewAI para gerar legendas criativas e oferecendo uma interface web intuitiva para gerenciamento de conteúdo.

### Funcionalidades Principais 🚀
- Interface web amigável com Streamlit
- Geração de legendas personalizadas com CrewAI
- Suporte a fotos individuais, carrosséis e reels
- Configuração de estilo de escrita e narrativa
- Monitoramento de status da API em tempo real

### Como Usar 🚀

#### Interface Web (Recomendado)
1. Instale as dependências:
   ```bash
   uv sync
   ```
2. Execute a interface Streamlit:
   ```bash
   streamlit run streamlit_app.py
   ```
3. Acesse a interface web em `http://localhost:8501`
4. Use as abas disponíveis:
   - **Postar Foto**: Para imagens individuais
   - **Postar Reels**: Para vídeos e reels
   - **Postar Carrossel**: Para múltiplas imagens
   - **Status da Fila**: Monitoramento da API

### Estrutura do Projeto 📂
- `streamlit_app.py`: Interface web principal com Streamlit
- `src/instagram/`: Módulos para integração com Instagram
- `src/utils/`: Utilitários e configurações
- `docs/`: Documentação detalhada
- `assets/`: Recursos estáticos
- `requirements.txt`: Dependências do projeto

### Contribuição
Contribuições são bem-vindas! Abra issues e pull requests para melhorias.

### Licença
MIT License

---

## English 🇺🇸

### Project Description
This project is a comprehensive tool for Instagram post automation and management, integrating CrewAI for creative caption generation and providing an intuitive web interface for content management.

### Main Features 🚀
- User-friendly Streamlit web interface
- Custom caption generation with CrewAI
- Support for single photos, carousels, and reels
- Writing style and narrative customization
- Real-time API status monitoring

### How to Use 🚀

#### Web Interface (Recommended)
1. Install dependencies:
   ```bash
   uv sync
   ```
2. Run the Streamlit interface:
   ```bash
   streamlit run streamlit_app.py
   ```
3. Access the web interface at `http://localhost:8501`
4. Use the available tabs:
   - **Post Photo**: For single images
   - **Post Reels**: For videos and reels
   - **Post Carousel**: For multiple images
   - **Queue Status**: API monitoring

### Project Structure 📂
- `streamlit_app.py`: Main Streamlit web interface
- `src/instagram/`: Instagram integration modules
- `src/utils/`: Utilities and configurations
- `docs/`: Detailed documentation
- `assets/`: Static resources
- `requirements.txt`: Project dependencies

### Contribution
Contributions are welcome! Open issues and pull requests for improvements.

### License
MIT License