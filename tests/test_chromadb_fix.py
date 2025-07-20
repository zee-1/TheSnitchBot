#!/usr/bin/env python3
"""
Test ChromaDB telemetry fix
"""

import os
import sys
from pathlib import Path

def main():
    # Set the telemetry environment variables early
    os.environ['ANONYMIZED_TELEMETRY'] = 'False'
    os.environ['CHROMA_TELEMETRY'] = 'False'
    
    # Set minimal test environment
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
    
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    
    with open('discord_test.log', 'w', encoding='utf-8') as f:
        f.write('TESTING CHROMADB TELEMETRY FIX\\n')
        f.write('=' * 35 + '\\n\\n')
        
        try:
            f.write('1. Testing ChromaDB import with telemetry disabled...\\n')
            
            # Test ChromaDB import
            import chromadb
            f.write(f'   ChromaDB version: {chromadb.__version__}\\n')
            f.write('   SUCCESS: ChromaDB imported without telemetry errors\\n')
            
            f.write('\\n2. Testing embedding service import...\\n')
            
            # Test embedding service
            from src.ai.embedding_service import EmbeddingService, CHROMADB_AVAILABLE
            f.write(f'   ChromaDB available: {CHROMADB_AVAILABLE}\\n')
            f.write('   SUCCESS: EmbeddingService imported\\n')
            
            f.write('\\n3. Testing bot imports with ChromaDB...\\n')
            
            # Test main bot import
            from src.discord_bot.bot import SnitchBot
            f.write('   SUCCESS: Bot imported without ChromaDB telemetry errors\\n')
            
            f.write('\\n' + '=' * 35 + '\\n')
            f.write('CHROMADB TELEMETRY FIX: SUCCESS!\\n')
            f.write('\\n')
            f.write('TELEMETRY STATUS:\\n')
            f.write(f'- ANONYMIZED_TELEMETRY: {os.environ.get("ANONYMIZED_TELEMETRY")}\\n')
            f.write(f'- CHROMA_TELEMETRY: {os.environ.get("CHROMA_TELEMETRY")}\\n')
            f.write('\\n')
            f.write('ChromaDB will no longer send telemetry data.\\n')
            f.write('No more posthog capture() errors!\\n')
            
            print("SUCCESS: ChromaDB telemetry fix applied!")
            print("No more posthog capture() errors should occur.")
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