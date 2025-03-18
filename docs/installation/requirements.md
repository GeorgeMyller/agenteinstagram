# Installation Requirements

## System Requirements

- Python 3.9 or higher
- At least 2GB of available RAM
- Storage space for temporary files and media processing

## Python Dependencies

All Python dependencies are listed in requirements.txt and will be installed automatically during setup.

Key dependencies include:
- moviepy: For video processing and validation
- opencv-python: For image processing
- Pillow: For image handling
- numpy: For numerical operations
- streamlit: For web interface

## Installation Steps

1. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
.\venv\Scripts\activate  # Windows
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

1. Copy `.env.example` to `.env`
2. Fill in required API keys and settings
3. Configure storage paths in `config.json`

## Optional Components

- Redis: For job queues and caching (optional)
- ImageMagick: For advanced image processing (optional)

## Troubleshooting

If you encounter issues with video processing:
1. Make sure you have enough disk space for temporary files
2. Check that moviepy is properly installed
3. Verify your Python environment has access to write temporary files

For more details on resolving issues, see the [troubleshooting guide](../troubleshooting/common.md).

