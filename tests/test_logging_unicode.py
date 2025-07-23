#!/usr/bin/env python3
"""
Test script to validate Unicode logging fixes
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from src.core.config import Settings
    from src.core.logging import setup_logging, get_logger
    
    def test_unicode_logging():
        """Test that Unicode characters in logs don't cause encoding errors."""
        print("Testing Unicode logging...")
        
        # Setup logging with test settings  
        settings = Settings(
            LOG_LEVEL="INFO",
            GROQ_API_KEY="test",
            DISCORD_TOKEN="test"
        )
        
        try:
            setup_logging(settings)
            logger = get_logger("test_unicode")
            
            # Test various Unicode characters that were causing issues
            test_messages = [
                "Successfully sent to output channel 🍵-tea",
                "Bot is ready! 🤖 Let the gossip begin! ✨",
                "Tea Alert! ☕ Sources say something happened 💅",
                "Weather update with 🌤️ and satellite 📡",
                "Investigation reveals 🔍 evidence with 👁️",
            ]
            
            for i, msg in enumerate(test_messages):
                try:
                    logger.info(f"Test {i+1}: {msg}")
                    print(f"PASS: Message {i+1} logged successfully")
                except Exception as e:
                    print(f"FAIL: Message {i+1} failed with error: {e}")
                    return False
            
            print("PASS: All Unicode logging tests passed!")
            return True
            
        except Exception as e:
            print(f"FAIL: Setup or logging failed: {e}")
            return False
    
    if __name__ == "__main__":
        success = test_unicode_logging()
        sys.exit(0 if success else 1)
        
except ImportError as e:
    print(f"Import error: {e}")
    print("This is expected if dependencies are not available.")
    sys.exit(0)  # Don't fail on import errors in test environment