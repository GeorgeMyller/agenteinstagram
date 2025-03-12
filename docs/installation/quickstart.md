# Quick Start Guide

## Prerequisites

- Python 3.11 or higher
- UV package manager
- Instagram Business Account
- Instagram Access Token
- Instagram User ID

## Installation

1. Install UV if not already installed:
```bash
pip install uv
```

2. Create and activate virtual environment:
```bash
uv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
```

3. Install dependencies:
```bash
uv sync
```

## Configuration

1. Create a `.env` file in the root directory
2. Add required environment variables:
```
INSTAGRAM_ACCESS_TOKEN=your_access_token
INSTAGRAM_USER_ID=your_user_id
```

## Using the Web Interface

1. Start the Streamlit interface:
```bash
streamlit run streamlit_app.py
```

2. Open your browser to `http://localhost:8501`

3. Navigate through the available tabs:
   - **Postar Foto**: Single image posts
   - **Postar Reels**: Video/reels posts
   - **Postar Carrossel**: Multiple image posts
   - **Status da Fila**: API status monitoring

4. For image posts:
   - Choose an image to upload
   - Select caption style and narrative person
   - Add optional custom caption
   - Preview and publish

5. For carrossel posts:
   - Upload 2-10 images
   - Add a single caption for all images
   - Preview selections before publishing

6. Monitor API limits and account status in the Status tab

## Troubleshooting

If you encounter issues:

1. Check the logs:
```bash
tail -f logs/app_debug.log
```

2. Verify your environment variables are set correctly
3. Ensure your Instagram tokens are valid
4. Check API rate limits in the Status tab

## Next Steps

- Review the [User Guide](../guides/overview.md) for detailed usage
- Check [API Documentation](../api/overview.md) for programmatic access
- See [Common Issues](../troubleshooting/common.md) for problem resolution
