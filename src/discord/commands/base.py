"""
Base command classes for The Snitch Discord Bot.
Provides foundation for slash command implementations.
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
import discord
from discord.ext import commands
from datetime import datetime, timedelta
import logging

from src.core.config import Settings
from src.core.exceptions import (
    CommandError, CommandPermissionError, CommandCooldownError,
    InvalidCommandArgumentError, DiscordError
)
from src.core.logging import get_logger, log_command_usage
from src.core.dependencies import DependencyContainer
from src.models.server import ServerConfig
from src.utils.validation import validate_discord_id

logger = get_logger(__name__)


class CommandContext:
    """Context information for command execution."""
    
    def __init__(
        self,
        interaction: discord.Interaction,
        server_config: ServerConfig,
        container: DependencyContainer
    ):
        self.interaction = interaction
        self.server_config = server_config
        self.container = container
        
        # Extract common properties
        self.guild_id = str(interaction.guild_id) if interaction.guild_id else None
        self.channel_id = str(interaction.channel_id) if interaction.channel_id else None
        self.user_id = str(interaction.user.id)
        self.user = interaction.user
        self.channel = interaction.channel
        self.guild = interaction.guild
    
    @property
    def is_admin(self) -> bool:
        """Check if user is an admin."""
        return self.server_config.is_admin(self.user_id)
    
    @property
    def is_moderator(self) -> bool:
        """Check if user is a moderator or admin."""
        return self.server_config.is_moderator(self.user_id)
    
    async def respond(
        self,
        content: str = None,
        embed: discord.Embed = None,
        ephemeral: bool = False,
        view: discord.ui.View = None
    ) -> None:
        """Respond to the interaction."""
        try:
            if self.interaction.response.is_done():
                await self.interaction.followup.send(
                    content=content,
                    embed=embed,
                    ephemeral=ephemeral,
                    view=view
                )
            else:
                await self.interaction.response.send_message(
                    content=content,
                    embed=embed,
                    ephemeral=ephemeral,
                    view=view
                )
        except Exception as e:
            logger.error(f"Failed to respond to interaction: {e}")
            raise DiscordError(f"Failed to respond: {e}")
    
    async def defer(self, ephemeral: bool = False) -> None:
        """Defer the interaction response."""
        try:
            await self.interaction.response.defer(ephemeral=ephemeral)
        except Exception as e:
            logger.error(f"Failed to defer interaction: {e}")
            raise DiscordError(f"Failed to defer: {e}")


class CooldownManager:
    """Manages command cooldowns per user/guild."""
    
    def __init__(self):
        self._cooldowns: Dict[str, datetime] = {}
    
    def is_on_cooldown(
        self,
        command_name: str,
        user_id: str,
        guild_id: str,
        cooldown_seconds: int
    ) -> bool:
        """Check if command is on cooldown for user."""
        key = f"{command_name}:{user_id}:{guild_id}"
        
        if key not in self._cooldowns:
            return False
        
        last_used = self._cooldowns[key]
        cooldown_expires = last_used + timedelta(seconds=cooldown_seconds)
        
        return datetime.now() < cooldown_expires
    
    def get_remaining_cooldown(
        self,
        command_name: str,
        user_id: str,
        guild_id: str,
        cooldown_seconds: int
    ) -> int:
        """Get remaining cooldown time in seconds."""
        key = f"{command_name}:{user_id}:{guild_id}"
        
        if key not in self._cooldowns:
            return 0
        
        last_used = self._cooldowns[key]
        cooldown_expires = last_used + timedelta(seconds=cooldown_seconds)
        now = datetime.now()
        
        if now >= cooldown_expires:
            return 0
        
        return int((cooldown_expires - now).total_seconds())
    
    def set_cooldown(
        self,
        command_name: str,
        user_id: str,
        guild_id: str
    ) -> None:
        """Set cooldown for command."""
        key = f"{command_name}:{user_id}:{guild_id}"
        self._cooldowns[key] = datetime.now()
    
    def clear_cooldown(
        self,
        command_name: str,
        user_id: str,
        guild_id: str
    ) -> None:
        """Clear cooldown for command."""
        key = f"{command_name}:{user_id}:{guild_id}"
        self._cooldowns.pop(key, None)


class BaseCommand(ABC):
    """Base class for all Discord slash commands."""
    
    def __init__(self, name: str, description: str, cooldown_seconds: int = 5):
        self.name = name
        self.description = description
        self.cooldown_seconds = cooldown_seconds
        self.cooldown_manager = CooldownManager()
    
    @abstractmethod
    async def execute(self, ctx: CommandContext, **kwargs) -> None:
        """Execute the command logic."""
        pass
    
    async def check_permissions(self, ctx: CommandContext) -> bool:
        """Check if user has permission to execute this command."""
        # Default: all users can execute
        return True
    
    async def validate_arguments(self, ctx: CommandContext, **kwargs) -> Dict[str, Any]:
        """Validate command arguments."""
        # Default: no validation
        return kwargs
    
    async def handle_command(
        self,
        interaction: discord.Interaction,
        container: DependencyContainer,
        **kwargs
    ) -> None:
        """Handle command execution with error handling and logging."""
        start_time = datetime.now()
        success = False
        error_message = None
        
        try:
            # Validate guild context
            if not interaction.guild_id:
                await interaction.response.send_message(
                    "This command can only be used in a server.",
                    ephemeral=True
                )
                return
            
            # Get server configuration
            server_repo = container.get_server_repository()
            server_config = await server_repo.get_by_server_id(str(interaction.guild_id))
            
            if not server_config:
                await interaction.response.send_message(
                    "Server not configured. Please contact an administrator.",
                    ephemeral=True
                )
                return
            
            # Create command context
            ctx = CommandContext(interaction, server_config, container)
            
            # Check if command is enabled
            if not server_config.can_use_command(self.name):
                await interaction.response.send_message(
                    f"The `{self.name}` command is disabled on this server.",
                    ephemeral=True
                )
                return
            
            # Check permissions
            if not await self.check_permissions(ctx):
                await interaction.response.send_message(
                    "You don't have permission to use this command.",
                    ephemeral=True
                )
                raise CommandPermissionError(
                    self.name, ctx.user_id, ctx.guild_id
                )
            
            # Check cooldown
            if self.cooldown_manager.is_on_cooldown(
                self.name, ctx.user_id, ctx.guild_id, self.cooldown_seconds
            ):
                remaining = self.cooldown_manager.get_remaining_cooldown(
                    self.name, ctx.user_id, ctx.guild_id, self.cooldown_seconds
                )
                await interaction.response.send_message(
                    f"Command on cooldown. Try again in {remaining} seconds.",
                    ephemeral=True
                )
                raise CommandCooldownError(self.name, remaining)
            
            # Validate arguments
            validated_args = await self.validate_arguments(ctx, **kwargs)
            
            # Execute command
            await self.execute(ctx, **validated_args)
            
            # Set cooldown
            self.cooldown_manager.set_cooldown(self.name, ctx.user_id, ctx.guild_id)
            
            success = True
            
        except CommandError as e:
            error_message = str(e)
            logger.warning(
                f"Command error in {self.name}",
                user_id=interaction.user.id,
                guild_id=interaction.guild_id,
                error=error_message
            )
            
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"Command failed: {error_message}",
                    ephemeral=True
                )
        
        except Exception as e:
            error_message = str(e)
            logger.error(
                f"Unexpected error in {self.name}",
                user_id=interaction.user.id,
                guild_id=interaction.guild_id,
                error=error_message,
                exc_info=True
            )
            
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An unexpected error occurred. Please try again later.",
                    ephemeral=True
                )
        
        finally:
            # Log command usage
            duration = (datetime.now() - start_time).total_seconds()
            
            log_command_usage(
                command=self.name,
                user_id=str(interaction.user.id),
                server_id=str(interaction.guild_id) if interaction.guild_id else "dm",
                success=success,
                duration_seconds=duration,
                error_message=error_message
            )


class AdminCommand(BaseCommand):
    """Base class for admin-only commands."""
    
    async def check_permissions(self, ctx: CommandContext) -> bool:
        """Check if user is an admin."""
        return ctx.is_admin


class ModeratorCommand(BaseCommand):
    """Base class for moderator+ commands."""
    
    async def check_permissions(self, ctx: CommandContext) -> bool:
        """Check if user is a moderator or admin."""
        return ctx.is_moderator


class PublicCommand(BaseCommand):
    """Base class for public commands with rate limiting."""
    
    def __init__(self, name: str, description: str, cooldown_seconds: int = 10):
        super().__init__(name, description, cooldown_seconds)
    
    async def check_permissions(self, ctx: CommandContext) -> bool:
        """Check rate limiting for public commands."""
        # Additional rate limiting logic can be added here
        return True


class EmbedBuilder:
    """Helper class for building Discord embeds."""
    
    @staticmethod
    def success(title: str, description: str = None) -> discord.Embed:
        """Create success embed."""
        embed = discord.Embed(
            title=f"✅ {title}",
            description=description,
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        return embed
    
    @staticmethod
    def error(title: str, description: str = None) -> discord.Embed:
        """Create error embed."""
        embed = discord.Embed(
            title=f"❌ {title}",
            description=description,
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        return embed
    
    @staticmethod
    def warning(title: str, description: str = None) -> discord.Embed:
        """Create warning embed."""
        embed = discord.Embed(
            title=f"⚠️ {title}",
            description=description,
            color=discord.Color.orange(),
            timestamp=datetime.now()
        )
        return embed
    
    @staticmethod
    def info(title: str, description: str = None) -> discord.Embed:
        """Create info embed."""
        embed = discord.Embed(
            title=f"ℹ️ {title}",
            description=description,
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        return embed
    
    @staticmethod
    def newsletter(
        title: str,
        content: str,
        author_name: str = "The Snitch",
        thumbnail_url: str = None
    ) -> discord.Embed:
        """Create newsletter embed."""
        embed = discord.Embed(
            title=title,
            description=content,
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        
        embed.set_author(name=author_name)
        
        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)
        
        embed.set_footer(text="Generated by The Snitch 🤖")
        
        return embed


class CommandRegistry:
    """Registry for managing Discord commands."""
    
    def __init__(self):
        self.commands: Dict[str, BaseCommand] = {}
    
    def register(self, command: BaseCommand) -> None:
        """Register a command."""
        self.commands[command.name] = command
        logger.info(f"Registered command: {command.name}")
    
    def get_command(self, name: str) -> Optional[BaseCommand]:
        """Get command by name."""
        return self.commands.get(name)
    
    def get_all_commands(self) -> List[BaseCommand]:
        """Get all registered commands."""
        return list(self.commands.values())
    
    def setup_app_commands(
        self,
        tree: discord.app_commands.CommandTree,
        container: DependencyContainer
    ) -> None:
        """Set up app commands on the command tree."""
        for command in self.commands.values():
            self._create_app_command(tree, command, container)
    
    def _create_app_command(
        self,
        tree: discord.app_commands.CommandTree,
        command: BaseCommand,
        container: DependencyContainer
    ) -> None:
        """Create Discord app command from BaseCommand."""
        
        async def command_callback(interaction: discord.Interaction, **kwargs):
            await command.handle_command(interaction, container, **kwargs)
        
        # Create the app command
        app_command = discord.app_commands.Command(
            name=command.name,
            description=command.description,
            callback=command_callback
        )
        
        # Add to tree
        tree.add_command(app_command)


# Global command registry
command_registry = CommandRegistry()