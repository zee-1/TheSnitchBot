#!/usr/bin/env python3
"""
Test script to verify main.py is ready to run
"""

import sys
import os
from pathlib import Path

def main():
    # Set test environment variables
    env_vars = {
        'DISCORD_TOKEN': 'test_token_123',
        'DISCORD_CLIENT_ID': 'test_client_id_123',
        'DISCORD_CLIENT_SECRET': 'test_client_secret_123',
        'AZURE_SUBSCRIPTION_ID': 'test_azure_sub_123',
        'AZURE_TENANT_ID': 'test_azure_tenant_123',
        'AZURE_CLIENT_ID': 'test_azure_client_123',
        'AZURE_CLIENT_SECRET': 'test_azure_secret_123',
        'COSMOS_CONNECTION_STRING': 'AccountEndpoint=https://test.documents.azure.com:443/;AccountKey=test_key==',
        'BLOB_CONNECTION_STRING': 'DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test;EndpointSuffix=core.windows.net',
        'SERVICE_BUS_CONNECTION_STRING': 'Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=test;SharedAccessKey=test=',
        'KEY_VAULT_URL': 'https://test-vault.vault.azure.net/',
        'GROQ_API_KEY': 'gsk_test_api_key_123',
        'SECRET_KEY': 'test_secret_key_very_long_string_for_security',
        'ENCRYPTION_KEY': 'test_encryption_key_very_long_string_for_security'
    }
    
    for key, value in env_vars.items():
        os.environ[key] = value
    
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    
    with open('discord_test.log', 'w', encoding='utf-8') as f:
        f.write('TESTING MAIN.PY READINESS\\n')
        f.write('=' * 35 + '\\n\\n')
        
        try:
            f.write('1. Testing main.py imports...\\n')
            
            # Import everything main.py imports
            from src.core.config import get_settings
            from src.core.logging import setup_logging
            from src.core.exceptions import BotInitializationError
            from src.discord_bot.bot import run_bot
            
            f.write('   SUCCESS: All imports work\\n')
            
            f.write('2. Testing settings and logging setup...\\n')
            
            # Test the exact sequence main.py uses
            settings = get_settings()
            setup_logging(settings)
            
            f.write('   SUCCESS: Settings loaded and logging configured\\n')
            
            f.write('3. Testing bot components...\\n')
            
            # Test bot creation
            from src.discord_bot.bot import SnitchBot
            bot = SnitchBot()
            
            f.write(f'   SUCCESS: Bot created ({type(bot).__name__})\\n')
            
            f.write('4. Testing command registry...\\n')
            
            from src.discord_bot.commands.base import command_registry
            commands = command_registry.get_all_commands()
            
            f.write(f'   SUCCESS: {len(commands)} commands available\\n')
            
            f.write('\\n' + '=' * 35 + '\\n')
            f.write('MAIN.PY READINESS: CONFIRMED!\\n')
            f.write('\\n')
            f.write('✓ All imports working\\n')
            f.write('✓ Settings loading correctly\\n')
            f.write('✓ Logging setup working\\n')
            f.write('✓ Bot creation successful\\n')
            f.write('✓ Commands registered\\n')
            f.write('\\n')
            f.write('READY TO RUN: python main.py\\n')
            f.write('(Make sure to set real environment variables first)\\n')
            
            print("SUCCESS: main.py is ready to run!")
            print("All setup_logging issues fixed!")
            return True
            
        except Exception as e:
            f.write(f'ERROR: {e}\\n')
            import traceback
            f.write(f'Traceback: {traceback.format_exc()}\\n')
            print(f"ERROR: {e}")
            return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)