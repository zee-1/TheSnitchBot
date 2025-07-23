#!/usr/bin/env python3
"""
Simple test for Unicode logging fix
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_safe_stream_handler():
    """Test the SafeStreamHandler directly."""
    try:
        from src.core.logging import SafeStreamHandler
        import logging
        
        print("Testing SafeStreamHandler...")
        
        # Create a test logger with the SafeStreamHandler
        logger = logging.getLogger("test")
        logger.setLevel(logging.INFO)
        
        # Remove any existing handlers
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # Add our SafeStreamHandler
        handler = SafeStreamHandler(sys.stdout)
        formatter = logging.Formatter('%(levelname)s: %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        # Test messages with Unicode that were causing issues
        test_messages = [
            "Successfully sent to output channel 🍵-tea",
            "Bot ready 🤖 with sparkles ✨",
            "Weather 🌤️ satellite 📡 forecast"
        ]
        
        for i, msg in enumerate(test_messages):
            try:
                logger.info(msg)
                print(f"PASS: Test message {i+1} logged without error")
            except Exception as e:
                print(f"FAIL: Test message {i+1} failed: {e}")
                return False
        
        print("PASS: All SafeStreamHandler tests passed!")
        return True
        
    except Exception as e:
        print(f"FAIL: Test setup failed: {e}")
        return False

if __name__ == "__main__":
    success = test_safe_stream_handler()
    sys.exit(0 if success else 1)