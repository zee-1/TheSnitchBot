"""
Test script to verify all imports work correctly.
Run this before trying to start the bot.
"""

import sys
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def test_imports():
    """Test all critical imports."""
    print("🧪 Testing imports...")
    
    try:
        # Core imports
        print("📦 Testing core modules...")
        from src.core.config import get_settings
        from src.core.logging import setup_logging
        from src.core.dependencies import DependencyContainer
        print("✅ Core modules imported successfully")
        
        # Model imports  
        print("📦 Testing model modules...")
        from src.models.server import ServerConfig, PersonaType
        from src.models.message import Message
        from src.models.newsletter import Newsletter
        print("✅ Model modules imported successfully")
        
        # Repository imports
        print("📦 Testing repository modules...")
        from src.data.repositories import (
            ServerRepository, 
            MessageRepository, 
            NewsletterRepository,
            TipRepository
        )
        print("✅ Repository modules imported successfully")
        
        # AI imports
        print("📦 Testing AI modules...")
        from src.ai import (
            GroqClient,
            NewsletterPipeline, 
            EmbeddingService,
            AIService
        )
        print("✅ AI modules imported successfully")
        
        # Discord imports
        print("📦 Testing Discord modules...")
        from src.discord_bot.bot import SnitchBot
        from src.discord_bot.commands.base import PublicCommand
        print("✅ Discord modules imported successfully")
        
        # Test configuration loading
        print("📦 Testing configuration...")
        try:
            settings = get_settings()
            print("✅ Configuration loaded (some values may be missing)")
        except Exception as e:
            print(f"⚠️  Configuration warning: {e}")
        
        print("\n🎉 All imports successful! The bot should be able to start.")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print(f"💡 Missing dependency or syntax error in module")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def main():
    """Main test function."""
    print("🔍 The Snitch Discord Bot - Import Test\n")
    
    if test_imports():
        print("\n✅ Import test passed! Ready to run the bot.")
        return 0
    else:
        print("\n❌ Import test failed. Fix the errors above before running the bot.")
        return 1

if __name__ == "__main__":
    sys.exit(main())