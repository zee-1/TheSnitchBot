"""
Development setup script for The Snitch Discord Bot.
Creates necessary configuration files and checks dependencies.
"""

import os
import sys
from pathlib import Path
import logging

def setup_logging():
    """Setup basic logging for setup script."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

def check_python_version():
    """Check if Python version is compatible."""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        return False
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    return True

def create_env_file():
    """Create .env file with placeholders if it doesn't exist."""
    env_file = Path(".env")
    
    if env_file.exists():
        print("✅ .env file already exists")
        return True
    
    env_template = """# Discord Configuration
DISCORD_TOKEN=your_discord_bot_token_here
DISCORD_CLIENT_ID=your_discord_client_id_here
DISCORD_CLIENT_SECRET=your_discord_client_secret_here

# Azure Configuration  
AZURE_SUBSCRIPTION_ID=your_azure_subscription_id_here
AZURE_TENANT_ID=your_azure_tenant_id_here
AZURE_CLIENT_ID=your_azure_client_id_here
AZURE_CLIENT_SECRET=your_azure_client_secret_here

# Azure Cosmos DB
COSMOS_CONNECTION_STRING=your_cosmos_connection_string_here
COSMOS_DATABASE_NAME=snitch_bot_db
COSMOS_CONTAINER_SERVERS=servers
COSMOS_CONTAINER_TIPS=tips
COSMOS_CONTAINER_NEWSLETTERS=newsletters
COSMOS_CONTAINER_MESSAGES=messages

# Azure Blob Storage
BLOB_CONNECTION_STRING=your_blob_connection_string_here
BLOB_CONTAINER_NAME=snitch-files

# Azure Service Bus
SERVICE_BUS_CONNECTION_STRING=your_service_bus_connection_string_here
SERVICE_BUS_QUEUE_MESSAGES=message-processing
SERVICE_BUS_TOPIC_EVENTS=bot-events

# Azure Key Vault
KEY_VAULT_URL=your_key_vault_url_here

# AI Services
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL_NAME=mixtral-8x7b-32768

# ChromaDB Configuration
CHROMA_HOST=localhost
CHROMA_PORT=8000
CHROMA_PERSIST_DIRECTORY=./chroma_data

# Application Settings
ENVIRONMENT=development
LOG_LEVEL=INFO
DEBUG=true

# Newsletter Configuration
DEFAULT_NEWSLETTER_TIME=09:00
DEFAULT_TIMEZONE=UTC
MAX_MESSAGES_PER_ANALYSIS=1000

# Rate Limiting
RATE_LIMIT_COMMANDS_PER_MINUTE=10
RATE_LIMIT_NEWSLETTER_PER_DAY=1

# Security
SECRET_KEY=your_secret_key_here_generate_a_random_string
ENCRYPTION_KEY=your_encryption_key_here_generate_a_random_string

# Monitoring (Optional)
AZURE_MONITOR_CONNECTION_STRING=
APPLICATION_INSIGHTS_INSTRUMENTATION_KEY=

# External Services (Optional)
CLOUDFLARE_API_TOKEN=
CLOUDFLARE_ZONE_ID=

# Development Settings
ENABLE_MOCK_SERVICES=false
MOCK_AI_RESPONSES=true
SKIP_DISCORD_VERIFICATION=false
"""
    
    try:
        with open(env_file, 'w') as f:
            f.write(env_template)
        print("✅ Created .env file with placeholders")
        print("⚠️  Please edit .env and add your actual credentials")
        return True
    except Exception as e:
        print(f"❌ Failed to create .env file: {e}")
        return False

def check_directories():
    """Create necessary directories."""
    directories = [
        "logs",
        "chroma_data", 
        "temp"
    ]
    
    for directory in directories:
        dir_path = Path(directory)
        if not dir_path.exists():
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
                print(f"✅ Created directory: {directory}")
            except Exception as e:
                print(f"❌ Failed to create directory {directory}: {e}")
                return False
        else:
            print(f"✅ Directory exists: {directory}")
    
    return True

def check_required_packages():
    """Check if required packages are installed."""
    required_packages = [
        "discord",  # discord.py
        "pydantic",
        "azure.cosmos",  # azure-cosmos
        "azure.storage.blob",  # azure-storage-blob  
        "azure.servicebus",  # azure-servicebus
        "groq",
        "chromadb", 
        "sentence_transformers",  # sentence-transformers
        "numpy",
        "langchain",
        "httpx",
        "structlog"
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} - NOT INSTALLED")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n📦 Install missing packages with:")
        print(f"pip install -r requirements-minimal.txt")
        print(f"Or for development: pip install -r requirements-dev.txt")
        return False
    
    return True

def main():
    """Main setup function."""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    print("🔧 Setting up The Snitch Discord Bot development environment...\n")
    
    # Check Python version
    if not check_python_version():
        return 1
    print()
    
    # Create directories
    print("📁 Creating directories...")
    if not check_directories():
        return 1
    print()
    
    # Create .env file
    print("⚙️  Setting up configuration...")
    if not create_env_file():
        return 1
    print()
    
    # Check packages (optional for setup)
    print("📦 Checking Python packages...")
    packages_ok = check_required_packages()
    print()
    
    # Summary
    print("📋 Setup Summary:")
    print("✅ Python version check passed")
    print("✅ Directories created")
    print("✅ Configuration file created")
    
    if packages_ok:
        print("✅ All required packages installed")
        print("\n🎉 Setup complete! You can now run the bot with:")
        print("python main.py")
    else:
        print("⚠️  Some packages missing - install them first")
        print("\n🎯 Next steps:")
        print("1. Install missing packages (see above)")
        print("2. Edit .env file with your credentials")
        print("3. Run: python main.py")
    
    print("\n📖 Documentation: https://docs.anthropic.com/en/docs/claude-code")
    return 0

if __name__ == "__main__":
    sys.exit(main())