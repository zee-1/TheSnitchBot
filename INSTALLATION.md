# The Snitch Discord Bot - Installation Guide

## 📋 Requirements

- **Python 3.8+** (Python 3.11+ recommended)
- **Discord Bot Token** (from Discord Developer Portal)
- **Groq API Key** (for AI functionality)
- **Azure Account** (for cloud services)

## 🚀 Quick Start

### 1. Clone and Setup Environment

```bash
# Clone the repository
git clone <repository-url>
cd JJJ

# Run setup script
python setup_dev.py
```

### 2. Install Dependencies

Choose one of the following based on your needs:

#### Minimal Installation (Core Functionality)
```bash
pip install -r requirements-minimal.txt
```

#### Development Installation (includes testing tools)
```bash
pip install -r requirements-dev.txt
```

#### Full Installation (all features)
```bash
pip install -r requirements.txt
```

### 3. Configure Environment

Edit the `.env` file created by the setup script:

```bash
# Required for basic functionality
DISCORD_TOKEN=your_discord_bot_token_here
GROQ_API_KEY=your_groq_api_key_here

# For testing without real AI
MOCK_AI_RESPONSES=true

# Azure services (required for production)
COSMOS_CONNECTION_STRING=your_cosmos_connection_string_here
```

### 4. Test Installation

```bash
# Verify all imports work
python test_imports.py

# Start the bot
python main.py
```

## 📦 Dependency Categories

### Core Dependencies (Always Required)
- `discord.py==2.3.2` - Discord API integration
- `pydantic==2.5.2` - Data validation
- `groq==0.4.1` - AI API client
- `chromadb==0.4.22` - Vector database
- `langchain==0.1.0` - AI pipeline framework

### Azure Cloud Services
- `azure-cosmos==4.5.1` - Database
- `azure-storage-blob==12.19.0` - File storage
- `azure-servicebus==7.11.4` - Message queues
- `azure-identity==1.15.0` - Authentication

### AI & Machine Learning
- `sentence-transformers==2.2.2` - Text embeddings
- `numpy==1.24.4` - Scientific computing
- `langchain-community==0.0.13` - Additional LangChain tools

### Development Tools (Optional)
- `pytest==7.4.4` - Testing framework
- `black==23.12.1` - Code formatting
- `mypy==1.8.0` - Type checking
- `pre-commit==3.6.0` - Git hooks

## 🔧 Platform-Specific Notes

### Windows
- `pywin32==306` is automatically installed
- No additional configuration needed

### Linux/macOS  
- `uvloop==0.19.0` provides better async performance
- May need to install system packages for some dependencies

### Docker (Optional)
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

## 🔍 Troubleshooting

### Common Issues

1. **Import Errors**: Run `python test_imports.py` to diagnose
2. **Discord Token Issues**: Verify token in Discord Developer Portal
3. **Azure Connection**: Check connection strings and permissions
4. **ChromaDB Issues**: Ensure `chroma_data` directory is writable

### Minimal Test Setup
If you want to test without cloud services:

```bash
# In .env file
MOCK_AI_RESPONSES=true
ENABLE_MOCK_SERVICES=true
SKIP_DISCORD_VERIFICATION=true
```

### Version Conflicts
If you encounter dependency conflicts:

```bash
# Create a fresh virtual environment
python -m venv venv_fresh
source venv_fresh/bin/activate  # Linux/macOS
# OR
venv_fresh\Scripts\activate  # Windows

# Install with exact versions
pip install -r requirements-minimal.txt
```

## 📊 Resource Requirements

### Minimal Setup
- **RAM**: 512MB minimum, 1GB recommended
- **Storage**: 500MB for dependencies + data
- **Network**: Stable internet for Discord/API calls

### Production Setup
- **RAM**: 2GB+ recommended
- **Storage**: 5GB+ for logs and data
- **Database**: Azure Cosmos DB or equivalent
- **Monitoring**: Application Insights (optional)

## 🔐 Security Notes

All packages are pinned to specific versions for security and stability. Regular updates should be tested in a development environment first.

The requirements include security scanning tools (`bandit`, `safety`) for production deployments.

## 📞 Support

If you encounter issues with dependencies:

1. Check the exact Python version: `python --version`
2. Verify virtual environment is activated
3. Try installing one requirement at a time to isolate issues
4. Check system-specific package requirements

For more help, refer to the main documentation or create an issue with your specific error message and environment details.