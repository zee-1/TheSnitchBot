"""
Main entry point for The Snitch Discord Bot.
Initializes and runs the bot with all necessary components.
"""

import asyncio
import sys
import signal
import logging
import os
from pathlib import Path

# Disable ChromaDB telemetry to prevent posthog errors
os.environ['ANONYMIZED_TELEMETRY'] = 'False'
os.environ['CHROMA_TELEMETRY'] = 'False'

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.core.config import get_settings
from src.core.logging import setup_logging
from src.core.exceptions import BotInitializationError
from src.discord_bot.bot import run_bot


async def main():
    """Main entry point for the bot."""
    try:
        # Get settings first
        settings = get_settings()
        
        # Setup logging with settings
        setup_logging(settings)
        logger = logging.getLogger(__name__)
        
        logger.info("Starting The Snitch Discord Bot...")
        
        # Validate configuration
        
        # Check required environment variables
        required_vars = [
            'DISCORD_TOKEN',
            'GROQ_API_KEY',
            'COSMOS_CONNECTION_STRING'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not getattr(settings, var.lower(), None):
                missing_vars.append(var)
        
        if missing_vars:
            logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
            logger.error("Please check your .env file and ensure all required variables are set.")
            return 1
        
        # Setup graceful shutdown
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            asyncio.create_task(shutdown())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Run the bot
        await run_bot()
        
    except BotInitializationError as e:
        logger.error(f"Bot initialization failed: {e}")
        return 1
    except KeyboardInterrupt:
        logger.info("Bot shutdown requested by user")
        return 0
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1


async def shutdown():
    """Gracefully shutdown the bot."""
    logger = logging.getLogger(__name__)
    logger.info("Shutting down The Snitch Discord Bot...")
    
    # Cancel running tasks
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    
    # Wait for tasks to complete
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    
    logger.info("Shutdown complete")


if __name__ == "__main__":
    if sys.version_info < (3, 8):
        print("Python 3.8 or higher is required")
        sys.exit(1)
    
    try:
        # Run the bot
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nBot stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"Failed to start bot: {e}")
        sys.exit(1)