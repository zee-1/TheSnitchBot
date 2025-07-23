#!/usr/bin/env python3
"""
Debug script to test persona enum handling
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from src.models.server import PersonaType, ServerConfig
    
    def test_persona_enum():
        """Test persona enum behavior."""
        print("Testing persona enum...")
        
        # Test enum directly
        persona = PersonaType.SASSY_REPORTER
        print(f"Direct enum: {persona}")
        print(f"Direct enum type: {type(persona)}")
        print(f"Direct enum value: {persona.value}")
        print(f"Has value attr: {hasattr(persona, 'value')}")
        
        # Test ServerConfig with default persona
        try:
            server_config = ServerConfig(
                server_id="123456",
                server_name="Test Server", 
                owner_id="789012",
                partition_key="123456",
                entity_type="server_config"
            )
            print(f"ServerConfig persona: {server_config.persona}")
            print(f"ServerConfig persona type: {type(server_config.persona)}")
            print(f"ServerConfig persona has value: {hasattr(server_config.persona, 'value')}")
            if hasattr(server_config.persona, 'value'):
                print(f"ServerConfig persona value: {server_config.persona.value}")
            else:
                print(f"ServerConfig persona as string: {server_config.persona}")
        except Exception as e:
            print(f"Error creating ServerConfig: {e}")
        
        return True
    
    if __name__ == "__main__":
        success = test_persona_enum()
        sys.exit(0 if success else 1)
        
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)