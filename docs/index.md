# Instagram Agent Documentation

## Overview

Instagram Agent is a powerful social media automation system that helps manage and automate Instagram content posting through an API interface. It supports various content types including single images, carousels, and videos/reels.

## Features

- Image posting with automatic caption generation
- Carousel post support with multiple images
- Video and reels upload capability
- AI-powered content description
- Webhook integration for automated posting
- Web interface for manual content managemen

## Quick Links

- [Installation Guide](installation/quickstart.md)
- [API Documentation](api/README.md)
- [Configuration Guide](guides/configuration.md)
- [Troubleshooting](troubleshooting/common.md)

## Project Structure

```
├── src/                    # Source code
│   ├── instagram/         # Instagram integration
│   ├── handlers/          # Request handlers
│   ├── services/          # Core services
│   └── utils/            # Utilities
├── tests/                 # Test suite
├── docs/                  # Documentation
└── scripts/              # Helper scripts
```

## Getting Started

1. Install the package:
   ```bash
   pip install -e .
   ```

2. Configure your environment:
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

3. Run the validation:
   ```bash
   python scripts/validate_setup.py
   ```

4. Start the server:
   ```bash
   python run.py
   ```

## Contributing

See our [contribution guidelines](guides/contributing.md) for information on how to contribute to this project.
