# Command Architecture Documentation - The Snitch Discord Bot

## ⚠️ CRITICAL: DO NOT MODIFY COMMAND STRUCTURE

**WARNING**: This command architecture is FINAL and MUST NOT be changed. Any modifications to the command structure will result in system failure.

## Command Architecture Overview

The Snitch Discord Bot uses a dual-layer command system:
1. **Base Command System**: Python class-based commands with validation and cooldowns
2. **Discord App Commands**: Proper Discord.py integration with parameter exposure

## Command Structure Hierarchy

### Base Command Classes

```python
BaseCommand (Abstract)
├── AdminCommand      # Administrator-only commands
├── ModeratorCommand  # Moderator and admin commands  
├── PublicCommand     # All users can execute
```

### Command Registration Flow

1. **Command Definition**: Commands inherit from base classes
2. **Parameter Definition**: `define_parameters()` method defines Discord-visible parameters
3. **Registration**: Commands auto-register via imports in `bot.py`
4. **App Command Creation**: Parametered commands get Discord app command wrappers

## Current Command Inventory

### Admin Commands (4)
- **set-persona**: Configure bot personality
- **set-news-channel**: Set newsletter delivery channel
- **set-news-time**: Set newsletter delivery time
- **bot-status**: View server configuration

### Public Commands (5)
- **breaking-news**: Generate AI breaking news from channel activity
- **fact-check**: Humorous fact-checking of messages
- **leak**: Generate harmless fake leaks about users
- **help**: Display available commands and information
- **submit-tip**: Anonymous tip submission system

## Command Implementation Patterns

### 1. Base Command Pattern

```python
class ExampleCommand(PublicCommand):
    def __init__(self):
        super().__init__(
            name="command-name",
            description="Command description",
            cooldown_seconds=30
        )
    
    def define_parameters(self) -> Dict[str, Dict[str, Any]]:
        """Define Discord-visible parameters"""
        return {
            "param_name": {
                "type": int,
                "description": "Parameter description",
                "required": False,
                "default": 50,
                "min_value": 10,
                "max_value": 100
            }
        }
    
    async def execute(self, ctx: CommandContext, param_name: int = 50):
        """Command execution logic"""
        pass
```

### 2. App Command Wrapper Pattern

```python
@app_commands.command(name="command-name", description="Description")
@app_commands.describe(param_name="Parameter description")
async def command_wrapper(
    self,
    interaction: discord.Interaction,
    param_name: Optional[app_commands.Range[int, 10, 100]] = 50
):
    """Discord app command wrapper"""
    ctx = await self._create_context(interaction)
    await self.base_command.execute(ctx, param_name=param_name)
```

## Command Registration System

### File Structure
```
src/discord_bot/commands/
├── __init__.py
├── base.py                    # Base command classes and registry
├── config_commands.py         # Admin configuration commands
├── config_app_commands.py     # Discord app command wrappers for config
├── breaking_news.py          # Breaking news command
├── fact_check.py             # Fact-check command
├── leak.py                   # Leak command
├── help_command.py           # Help command
├── tip_command.py            # Tip submission command
└── content_app_commands.py   # Discord app command wrappers for content
```

### Registration Flow

1. **Import Registration**: Commands register automatically when imported in `bot.py`
```python
# Import command modules to trigger registration
import src.discord_bot.commands.config_commands
import src.discord_bot.commands.breaking_news
import src.discord_bot.commands.fact_check
import src.discord_bot.commands.leak
import src.discord_bot.commands.help_command
import src.discord_bot.commands.tip_command
```

2. **App Command Setup**: Parametered commands get app command wrappers
```python
# Register proper config commands with parameters
from src.discord_bot.commands.config_app_commands import setup_config_commands
config_group = setup_config_commands(self, self.container)

# Register content commands with parameters
from src.discord_bot.commands.content_app_commands import setup_content_commands
await setup_content_commands(self.tree, self.container)
```

3. **Command Filtering**: Prevents duplicate registration
```python
# Skip commands that are handled by app command groups
if (command_instance.name.startswith("set-") or 
    command_instance.name == "bot-status" or
    command_instance.name == "breaking-news" or
    command_instance.name == "fact-check"):
    continue  # Handled by app command groups
```

## Command Categories and Access

### Discord Command Groups

#### `/config` Group (Admin Only)
- **set-persona**: Bot personality configuration
- **set-newsletter-channel**: Newsletter delivery channel
- **set-newsletter-time**: Newsletter delivery time
- **status**: Server configuration display

#### `/content` Group (Public)
- **breaking-news**: AI news generation with parameters
- **fact-check**: Message fact-checking with message ID

#### Root Commands (Public)
- **leak**: Automatic random user selection
- **help**: No parameters needed
- **submit-tip**: Anonymous tip with content/category/anonymous options

## Parameter Validation System

### Parameter Definition Schema
```python
{
    "parameter_name": {
        "type": int | str | bool,           # Python type
        "description": "User-friendly description",
        "required": True | False,           # Is parameter required
        "default": value,                   # Default value if optional
        "min_value": int,                   # For integer parameters
        "max_value": int,                   # For integer parameters
        "choices": ["option1", "option2"]   # For enum parameters
    }
}
```

### Validation Flow
1. **Discord Validation**: Type checking and range validation
2. **Command Validation**: Custom validation in `validate_arguments()`
3. **Execution**: Validated parameters passed to `execute()` method

## Error Handling System

### Exception Hierarchy
```
SnitchBotError (Base)
├── CommandError
│   ├── CommandPermissionError
│   ├── CommandCooldownError
│   └── InvalidCommandArgumentError
├── ValidationError
├── DatabaseError
└── DiscordError
```

### Error Response Pattern
```python
try:
    # Command execution
except ValidationError as e:
    embed = EmbedBuilder.error("Validation Error", str(e))
    await ctx.respond(embed=embed, ephemeral=True)
except Exception as e:
    embed = EmbedBuilder.error("Command Failed", "Unexpected error occurred")
    await ctx.respond(embed=embed, ephemeral=True)
    logger.error(f"Command error: {e}", exc_info=True)
```

## Cooldown Management

### Cooldown System
- **Per-user/guild tracking**: `{command}:{user_id}:{guild_id}`
- **Configurable timeouts**: Set per command in constructor
- **Automatic enforcement**: Handled by base command system

### Cooldown Values
- **Admin commands**: 5-10 seconds
- **Content generation**: 15-30 seconds  
- **Tip submission**: 300 seconds (5 minutes)
- **Simple commands**: 5-20 seconds

## Logging and Monitoring

### Structured Logging
```python
logger.info(
    "Command executed",
    extra={
        "command": command_name,
        "user_id": ctx.user_id,
        "guild_id": ctx.guild_id,
        "parameters": parameters
    }
)
```

### Performance Tracking
- Command execution time
- Parameter validation time
- Error rates and types
- Usage statistics per command

## Security Considerations

### Permission Validation
- **Admin check**: Server owner, explicit admin list, or Discord admin permissions
- **Moderator check**: Admin permissions + explicit moderator list
- **Public access**: Rate limiting and content validation

### Input Validation
- **Discord ID format**: Snowflake validation
- **Content filtering**: XSS prevention, length limits
- **Rate limiting**: Per-user cooldowns and command limits

## CRITICAL RULES

### ⚠️ NEVER MODIFY
1. **Command class hierarchy**: BaseCommand → AdminCommand/ModeratorCommand/PublicCommand
2. **Registration flow**: Import-based auto-registration
3. **Parameter definition schema**: `define_parameters()` method structure  
4. **App command wrapper pattern**: Dual-layer system
5. **Command filtering logic**: Prevents duplicate registration

### ✅ SAFE TO MODIFY
1. **Command descriptions**: User-facing text
2. **Parameter descriptions**: Help text only
3. **Error messages**: User feedback text
4. **Logging messages**: Internal logging only
5. **Cooldown values**: Timing adjustments only

### 🚫 FORBIDDEN CHANGES
1. **Changing command names**: Breaks Discord registration
2. **Modifying parameter types**: Breaks validation
3. **Altering class inheritance**: Breaks permission system
4. **Changing registration imports**: Breaks command loading
5. **Removing app command wrappers**: Breaks parameter visibility

## Conclusion

This command architecture provides a robust, scalable system for Discord bot commands with proper parameter handling, validation, and user experience. The dual-layer approach ensures both Python flexibility and Discord integration compatibility.

**FINAL WARNING**: Any modifications to this architecture will result in system failure and must be avoided at all costs.