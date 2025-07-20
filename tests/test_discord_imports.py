#!/usr/bin/env python3
"""
Discord imports test script
Tests all Discord-related imports in the .venv environment
"""

import sys
import traceback
from pathlib import Path

def write_log(message):
    """Write message to both console and log file"""
    print(message)
    with open('discord_test.log', 'a', encoding='utf-8') as f:
        f.write(message + '\n')

def test_discord_imports():
    """Test all Discord imports systematically"""
    
    # Clear the log file
    with open('discord_test.log', 'w', encoding='utf-8') as f:
        f.write('DISCORD IMPORTS TEST - USING .VENV ENVIRONMENT\n')
        f.write('=' * 60 + '\n\n')
    
    write_log("Testing Discord imports in .venv environment...")
    write_log(f"Python version: {sys.version}")
    write_log(f"Python executable: {sys.executable}")
    write_log("")
    
    # Test 1: Basic discord import
    write_log("1. Testing basic discord import...")
    try:
        import discord
        write_log(f"   SUCCESS: discord version {discord.__version__}")
    except Exception as e:
        write_log(f"   ERROR: {e}")
        return False
    
    # Test 2: Check discord.enums
    write_log("2. Testing discord.enums...")
    try:
        from discord import enums
        available_enums = [attr for attr in dir(enums) if not attr.startswith('_')]
        write_log(f"   SUCCESS: discord.enums imported")
        write_log(f"   Available enums count: {len(available_enums)}")
        
        # Check specifically for AppCommandOptionType
        if 'AppCommandOptionType' in available_enums:
            write_log("   SUCCESS: AppCommandOptionType found in discord.enums")
        else:
            write_log("   ERROR: AppCommandOptionType NOT found in discord.enums")
            write_log(f"   Available enums: {available_enums[:10]}...")
            
    except Exception as e:
        write_log(f"   ERROR: discord.enums failed: {e}")
        return False
    
    # Test 3: Test app_commands import
    write_log("3. Testing discord.app_commands import...")
    try:
        from discord import app_commands
        write_log("   SUCCESS: discord.app_commands imported")
    except Exception as e:
        write_log(f"   ERROR: discord.app_commands failed: {e}")
        write_log(f"   Full traceback: {traceback.format_exc()}")
        return False
    
    # Test 4: Test individual components
    write_log("4. Testing individual app_commands components...")
    try:
        # Test CommandTree
        tree = app_commands.CommandTree(discord.Client(intents=discord.Intents.default()))
        write_log("   SUCCESS: app_commands.CommandTree works")
        
        # Test Command
        async def dummy_callback(interaction):
            pass
        cmd = app_commands.Command(name="test", description="test", callback=dummy_callback)
        write_log("   SUCCESS: app_commands.Command works")
        
    except Exception as e:
        write_log(f"   ERROR: app_commands components failed: {e}")
        return False
    
    # Test 5: Test our bot imports
    write_log("5. Testing our bot imports...")
    try:
        # Add src to path
        sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
        
        # Set minimal environment variables
        import os
        os.environ.setdefault('DISCORD_TOKEN', 'test_token')
        os.environ.setdefault('GROQ_API_KEY', 'test_key')
        os.environ.setdefault('COSMOS_CONNECTION_STRING', 'test_connection')
        os.environ.setdefault('AZURE_SUBSCRIPTION_ID', 'test_sub')
        os.environ.setdefault('AZURE_TENANT_ID', 'test_tenant')
        os.environ.setdefault('AZURE_CLIENT_ID', 'test_client')
        os.environ.setdefault('AZURE_CLIENT_SECRET', 'test_secret')
        os.environ.setdefault('BLOB_CONNECTION_STRING', 'test_blob')
        os.environ.setdefault('SERVICE_BUS_CONNECTION_STRING', 'test_bus')
        os.environ.setdefault('KEY_VAULT_URL', 'test_vault')
        os.environ.setdefault('SECRET_KEY', 'test_secret_key')
        os.environ.setdefault('ENCRYPTION_KEY', 'test_encryption_key')
        
        from src.discord_bot.bot import run_bot
        write_log("   SUCCESS: src.discord_bot.bot imported")
        
    except Exception as e:
        write_log(f"   ERROR: Bot imports failed: {e}")
        write_log(f"   Full traceback: {traceback.format_exc()}")
        return False
    
    write_log("")
    write_log("=" * 60)
    write_log("ALL TESTS PASSED!")
    write_log("Discord imports are working correctly in .venv")
    return True

if __name__ == "__main__":
    success = test_discord_imports()
    if not success:
        write_log("\nTESTS FAILED! Check errors above.")
        sys.exit(1)
    else:
        write_log("\nAll Discord imports working correctly!")
        sys.exit(0)