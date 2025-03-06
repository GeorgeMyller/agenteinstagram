# Quick Start Guide

Get up and running with Agent Social Media quickly.

## Prerequisites

Before you begin, ensure you have:

- Python 3.12 or newer
- FFmpeg installed for video processing
- Git for version control
- Instagram Business or Creator accoun
- Required API keys and tokens

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/acessoia/agentcrewai.gi
   cd agentcrewai
   ```

2. Run the setup script:
   ```bash
   chmod +x scripts/setup.sh
   ./scripts/setup.sh
   ```

   This will:
   - Create necessary directories
   - Install dependencies
   - Set up pre-commit hooks
   - Create a .env template

3. Configure your environment:
   - Copy `.env.example` to `.env`
   - Fill in your API keys and tokens
   - Configure paths and settings

4. Validate your setup:
   ```bash
   python scripts/validate_setup.py
   ```

## Quick Tes

Test your installation by:

1. Starting the server:
   ```bash
   python src/app.py
   ```

2. Running the test endpoint:
   ```bash
   curl http://localhost:5001/debug/send-tes
   ```

## Using the Web Interface

1. Start the Streamlit interface:
   ```bash
   streamlit run streamlit_app.py
   ```

2. Open your browser to `http://localhost:8501`

3. Try uploading an image and posting it to Instagram

## Next Steps

- Read the [Configuration Guide](configuration.md) for detailed setup
- Check the [User Guide](../guides/overview.md) for usage instructions
- Review [Common Issues](../troubleshooting/common.md) if you encounter problems

## Development Setup

For development, install additional tools:

```bash
pip install -r requirements-dev.tx
```

This includes:
- Testing tools (pytest)
- Code formatting (black)
- Type checking (mypy)
- Documentation tools (mkdocs)

Run tests to verify everything works:
```bash
python -m pytes
```
