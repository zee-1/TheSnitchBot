#!/usr/bin/env python3
"""
Discord Bot Permissions Calculator and Guide
"""

def main():
    with open('discord_test.log', 'w', encoding='utf-8') as f:
        f.write('DISCORD BOT PERMISSIONS GUIDE\\n')
        f.write('=' * 40 + '\\n\\n')
        
        f.write('REQUIRED BOT PERMISSIONS:\\n')
        f.write('=' * 25 + '\\n\\n')
        
        f.write('📝 TEXT PERMISSIONS:\\n')
        f.write('- Send Messages (REQUIRED)\\n')
        f.write('- Send Messages in Threads (REQUIRED)\\n')
        f.write('- Embed Links (REQUIRED)\\n')
        f.write('- Attach Files (REQUIRED)\\n')
        f.write('- Read Message History (REQUIRED)\\n')
        f.write('- Use Slash Commands (REQUIRED)\\n')
        f.write('- Add Reactions (REQUIRED)\\n')
        f.write('\\n')
        
        f.write('👥 GENERAL PERMISSIONS:\\n')
        f.write('- View Channels (REQUIRED)\\n')
        f.write('\\n')
        
        f.write('🔧 PRIVILEGED GATEWAY INTENTS:\\n')
        f.write('- Message Content Intent (REQUIRED)\\n')
        f.write('- Server Members Intent (recommended)\\n')
        f.write('\\n')
        
        f.write('PERMISSION BITS BREAKDOWN:\\n')
        f.write('=' * 26 + '\\n')
        
        permissions = {
            'View Channels': 1024,           # 1 << 10
            'Send Messages': 2048,           # 1 << 11
            'Embed Links': 16384,            # 1 << 14
            'Attach Files': 32768,           # 1 << 15
            'Read Message History': 65536,   # 1 << 16
            'Add Reactions': 64,             # 1 << 6
            'Use Slash Commands': 2147483648 # 1 << 31
        }
        
        total_permissions = sum(permissions.values())
        
        for perm, value in permissions.items():
            f.write(f'{perm}: {value}\\n')
        
        f.write(f'\\nTOTAL PERMISSION VALUE: {total_permissions}\\n')
        f.write('\\n')
        
        f.write('DISCORD DEVELOPER PORTAL SETUP:\\n')
        f.write('=' * 35 + '\\n')
        f.write('1. Go to https://discord.com/developers/applications\\n')
        f.write('2. Select your bot application\\n')
        f.write('3. Go to Bot section\\n')
        f.write('4. Enable Privileged Gateway Intents:\\n')
        f.write('   ✓ MESSAGE CONTENT INTENT (REQUIRED!)\\n')
        f.write('   ✓ SERVER MEMBERS INTENT (recommended)\\n')
        f.write('\\n')
        f.write('5. Go to OAuth2 > URL Generator\\n')
        f.write('6. Select Scopes:\\n')
        f.write('   ✓ bot\\n')
        f.write('   ✓ applications.commands\\n')
        f.write('\\n')
        f.write('7. Select Bot Permissions:\\n')
        f.write('   ✓ View Channels\\n')
        f.write('   ✓ Send Messages\\n')
        f.write('   ✓ Send Messages in Threads\\n')
        f.write('   ✓ Embed Links\\n')
        f.write('   ✓ Attach Files\\n')
        f.write('   ✓ Read Message History\\n')
        f.write('   ✓ Add Reactions\\n')
        f.write('   ✓ Use Slash Commands\\n')
        f.write('\\n')
        f.write('8. Copy the generated invite URL\\n')
        f.write('\\n')
        
        f.write('BOT INVITE URL FORMAT:\\n')
        f.write('=' * 22 + '\\n')
        f.write('https://discord.com/api/oauth2/authorize?\\n')
        f.write('client_id=YOUR_BOT_CLIENT_ID&\\n')
        f.write(f'permissions={total_permissions}&\\n')
        f.write('scope=bot%20applications.commands\\n')
        f.write('\\n')
        
        f.write('CRITICAL NOTES:\\n')
        f.write('=' * 15 + '\\n')
        f.write('⚠️  MESSAGE CONTENT INTENT is REQUIRED\\n')
        f.write('⚠️  Without it, bot cannot read message content\\n')
        f.write('⚠️  Enable in Developer Portal > Bot > Privileged Gateway Intents\\n')
        f.write('\\n')
        f.write('✅ SETUP COMPLETE!\\n')
        f.write('Your bot will be able to:\\n')
        f.write('- Read and send messages\\n')
        f.write('- Use slash commands\\n')
        f.write('- Send newsletters with embeds\\n')
        f.write('- React to messages\\n')
        f.write('- Process server activity\\n')

    print('Discord Bot Permissions Guide Created!')
    print('')
    print('🔑 REQUIRED PERMISSIONS:')
    print('✓ View Channels')
    print('✓ Send Messages') 
    print('✓ Send Messages in Threads')
    print('✓ Embed Links')
    print('✓ Attach Files')
    print('✓ Read Message History')
    print('✓ Add Reactions')
    print('✓ Use Slash Commands')
    print('')
    print('🚪 CRITICAL: Enable in Developer Portal > Bot:')
    print('✓ MESSAGE CONTENT INTENT (REQUIRED!)')
    print('✓ SERVER MEMBERS INTENT (recommended)')
    print('')
    print(f'📋 Permission Value: {sum([1024, 2048, 16384, 32768, 65536, 64, 2147483648])}')
    print('📋 Full setup guide saved to discord_test.log')

if __name__ == "__main__":
    main()