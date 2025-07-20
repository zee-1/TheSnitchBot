"""
Discord client wrapper for The Snitch Discord Bot.
Provides high-level interface for Discord API operations.
"""

import asyncio
from typing import List, Optional, Dict, Any, Union
import discord
from discord import app_commands

from discord.ext import commands
from datetime import datetime, timedelta
import logging

# Assuming these are your custom modules. 
# In a real scenario, make sure these paths are correct.
# from src.core.config import Settings
# from src.core.exceptions import (
#     DiscordError, DiscordAPIError, DiscordPermissionError,
#     DiscordServerNotFoundError, DiscordChannelNotFoundError,
#     DiscordUserNotFoundError
# )
# from src.core.logging import get_logger
# from src.utils.retry import api_retry
# from src.models.message import Message
# from src.models.server import ServerConfig

# --- Mock/Placeholder classes for standalone execution ---
# These classes are placeholders to make the script runnable for review
# without having the full project structure.

class Settings:
    def __init__(self):
        self.discord_token = "YOUR_DISCORD_TOKEN_HERE"

class DiscordError(Exception): pass
class DiscordAPIError(DiscordError): pass
class DiscordPermissionError(DiscordError):
    def __init__(self, permission, channel_id):
        super().__init__(f"Missing permission '{permission}' in channel '{channel_id}'.")
class DiscordServerNotFoundError(DiscordError): pass
class DiscordChannelNotFoundError(DiscordError): pass
class DiscordUserNotFoundError(DiscordError): pass

def get_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    if not logger.handlers:
        logger.addHandler(handler)
    return logger

def api_retry(func):
    """A simple decorator placeholder for the actual retry logic."""
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"API call for {func.__name__} failed. Error: {e}")
            raise
    return wrapper

class Message:
    @staticmethod
    def from_discord_message(discord_message, guild_id):
        # This would convert a discord.Message to your custom Message model
        return {"id": discord_message.id, "content": discord_message.content, "guild_id": guild_id}

class ServerConfig:
    def __init__(self, server_id, newsletter_channel_id=None, whitelisted_channels=None):
        self.server_id = server_id
        self.newsletter_channel_id = newsletter_channel_id
        self.whitelisted_channels = whitelisted_channels or []

# --- End of Mock/Placeholder classes ---


logger = get_logger(__name__)


class SnitchDiscordClient:
    """Discord client wrapper with enhanced functionality for The Snitch bot."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        
        # Configure intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.guild_messages = True
        intents.guild_reactions = True
        intents.members = True
        
        # Initialize Discord client
        self.client = discord.Client(intents=intents)
        self.tree = app_commands.CommandTree(self.client)
        
        # Bot state
        self._ready_event = asyncio.Event()
        self._guilds_cache: Dict[int, discord.Guild] = {}
        
        # Setup event handlers
        self._setup_event_handlers()
    
    def _setup_event_handlers(self) -> None:
        """Set up Discord event handlers."""
        
        @self.client.event
        async def on_ready():
            """Handle bot ready event."""
            # Corrected user_count logic
            user_count = sum(guild.member_count for guild in self.client.guilds if guild.member_count is not None)
            logger.info(
                "Discord client ready",
                extra={
                    "bot_user": str(self.client.user),
                    "guild_count": len(self.client.guilds),
                    "user_count": user_count
                }
            )
            
            # Cache guilds
            for guild in self.client.guilds:
                self._guilds_cache[guild.id] = guild
            
            # Sync command tree
            try:
                synced = await self.tree.sync()
                logger.info(f"Synced {len(synced)} commands")
            except Exception as e:
                logger.error(f"Failed to sync commands: {e}")

            # Signal that the client is now ready for operations.
            self._ready_event.set()
        
        @self.client.event
        async def on_guild_join(guild: discord.Guild):
            """Handle guild join event."""
            self._guilds_cache[guild.id] = guild
            logger.info(
                "Joined new guild",
                extra={
                    "guild_id": guild.id,
                    "guild_name": guild.name,
                    "member_count": guild.member_count
                }
            )
        
        @self.client.event
        async def on_guild_remove(guild: discord.Guild):
            """Handle guild remove event."""
            self._guilds_cache.pop(guild.id, None)
            logger.info(
                "Removed from guild",
                extra={
                    "guild_id": guild.id,
                    "guild_name": guild.name
                }
            )
        
        @self.client.event
        async def on_error(event: str, *args, **kwargs):
            """Handle Discord client errors."""
            logger.error(f"Discord client error in event {event}", exc_info=True)
    
    async def start(self) -> None:
        """Start the Discord client and wait for it to be ready."""
        try:
            # The start method will not return until the bot is disconnected.
            await self.client.start(self.settings.discord_token)
        except Exception as e:
            logger.error(f"Failed to start Discord client: {e}", exc_info=True)
            raise DiscordError(f"Failed to start Discord client: {e}")
    
    async def close(self) -> None:
        """Close the Discord client."""
        try:
            await self.client.close()
            self._ready_event.clear()
            logger.info("Discord client closed")
        except Exception as e:
            logger.error(f"Error closing Discord client: {e}", exc_info=True)
    
    async def _wait_for_ready(self):
        """Waits until the client is fully connected and ready."""
        try:
            # Wait for the on_ready event to be set, with a timeout.
            await asyncio.wait_for(self._ready_event.wait(), timeout=60.0)
        except asyncio.TimeoutError:
            logger.critical("Discord client failed to become ready in 60 seconds.")
            raise DiscordError("Client not ready: The connection to Discord timed out.")

    @property
    def is_ready(self) -> bool:
        """Check if the client is ready."""
        return self._ready_event.is_set() and self.client.is_ready()
    
    @api_retry
    async def get_guild(self, guild_id: Union[int, str]) -> Optional[discord.Guild]:
        """Get guild by ID, using cache first."""
        await self._wait_for_ready()
        try:
            guild_id = int(guild_id)
            
            # Check cache first
            if guild_id in self._guilds_cache:
                return self._guilds_cache[guild_id]
            
            # Fetch from Discord if not in cache
            guild = self.client.get_guild(guild_id)
            if guild:
                self._guilds_cache[guild_id] = guild
                return guild
            
            # Try fetching explicitly if not found
            guild = await self.client.fetch_guild(guild_id)
            self._guilds_cache[guild_id] = guild
            return guild
            
        except discord.NotFound:
            logger.warning(f"Guild {guild_id} not found.")
            return None
        except Exception as e:
            logger.error(f"Error getting guild {guild_id}: {e}", exc_info=True)
            raise DiscordAPIError(f"Failed to get guild: {e}")
    
    @api_retry
    async def get_channel(self, channel_id: Union[int, str]) -> Optional[discord.TextChannel]:
        """Get text channel by ID."""
        await self._wait_for_ready()
        try:
            channel_id = int(channel_id)
            channel = self.client.get_channel(channel_id)
            
            if channel and isinstance(channel, discord.TextChannel):
                return channel
            
            # Try fetching if not in cache
            channel = await self.client.fetch_channel(channel_id)
            if isinstance(channel, discord.TextChannel):
                return channel
            return None
            
        except discord.NotFound:
            logger.warning(f"Channel {channel_id} not found.")
            return None
        except Exception as e:
            logger.error(f"Error getting channel {channel_id}: {e}", exc_info=True)
            raise DiscordAPIError(f"Failed to get channel: {e}")
    
    @api_retry
    async def get_user(self, user_id: Union[int, str]) -> Optional[discord.User]:
        """Get user by ID."""
        await self._wait_for_ready()
        try:
            user_id = int(user_id)
            user = self.client.get_user(user_id)
            
            if user:
                return user
            
            # Try fetching if not in cache
            user = await self.client.fetch_user(user_id)
            return user

        except discord.NotFound:
            logger.warning(f"User {user_id} not found.")
            return None
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {e}", exc_info=True)
            raise DiscordAPIError(f"Failed to get user: {e}")
    
    @api_retry
    async def send_message(
        self, 
        channel_id: Union[int, str], 
        content: str = None,
        embed: discord.Embed = None,
        file: discord.File = None,
        view: discord.ui.View = None
    ) -> Optional[discord.Message]:
        """Send message to a channel."""
        await self._wait_for_ready()
        channel = await self.get_channel(channel_id)
        if not channel:
            raise DiscordChannelNotFoundError(str(channel_id))
        
        # Check permissions
        if not channel.permissions_for(channel.guild.me).send_messages:
            raise DiscordPermissionError("send_messages", str(channel.guild.id))
        
        try:
            message = await channel.send(
                content=content,
                embed=embed,
                file=file,
                view=view
            )
            
            logger.info(
                "Message sent successfully",
                extra={
                    "channel_id": channel_id, "message_id": message.id,
                    "has_embed": embed is not None, "has_file": file is not None
                }
            )
            return message
            
        except discord.Forbidden as e:
            raise DiscordPermissionError("send_messages", str(channel_id)) from e
        except discord.HTTPException as e:
            raise DiscordAPIError(f"HTTP error sending message: {e}") from e
        except Exception as e:
            logger.error(f"Error sending message to {channel_id}: {e}", exc_info=True)
            raise DiscordAPIError(f"Failed to send message: {e}")
    
    @api_retry
    async def get_recent_messages(
        self, 
        channel_id: Union[int, str], 
        limit: int = 100,
        before: Optional[datetime] = None,
        after: Optional[datetime] = None
    ) -> List[Message]:
        """Get recent messages from a channel."""
        await self._wait_for_ready()
        channel = await self.get_channel(channel_id)
        if not channel:
            raise DiscordChannelNotFoundError(str(channel_id))
        
        # Check permissions
        if not channel.permissions_for(channel.guild.me).read_message_history:
            raise DiscordPermissionError("read_message_history", str(channel.guild.id))
        
        try:
            messages = []
            async for discord_message in channel.history(limit=limit, before=before, after=after):
                # Convert to our Message model
                message = Message.from_discord_message(discord_message, str(channel.guild.id))
                messages.append(message)
            
            logger.info(
                "Retrieved messages",
                extra={"channel_id": channel_id, "message_count": len(messages), "limit": limit}
            )
            return messages
            
        except discord.Forbidden as e:
            raise DiscordPermissionError("read_message_history", str(channel_id)) from e
        except Exception as e:
            logger.error(f"Error getting messages from {channel_id}: {e}", exc_info=True)
            raise DiscordAPIError(f"Failed to get messages: {e}")
    
    @api_retry
    async def get_message(
        self, 
        channel_id: Union[int, str], 
        message_id: Union[int, str]
    ) -> Optional[Message]:
        """Get a specific message by ID."""
        await self._wait_for_ready()
        channel = await self.get_channel(channel_id)
        if not channel:
            raise DiscordChannelNotFoundError(str(channel_id))
        
        try:
            discord_message = await channel.fetch_message(int(message_id))
            return Message.from_discord_message(discord_message, str(channel.guild.id))
            
        except discord.NotFound:
            return None
        except discord.Forbidden as e:
            raise DiscordPermissionError("read_message_history", str(channel_id)) from e
        except Exception as e:
            logger.error(f"Error getting message {message_id} from {channel_id}: {e}", exc_info=True)
            raise DiscordAPIError(f"Failed to get message: {e}")
    
    @api_retry
    async def add_reaction(
        self, 
        channel_id: Union[int, str], 
        message_id: Union[int, str], 
        emoji: str
    ) -> bool:
        """Add reaction to a message."""
        await self._wait_for_ready()
        channel = await self.get_channel(channel_id)
        if not channel:
            raise DiscordChannelNotFoundError(str(channel_id))
        
        try:
            message = await channel.fetch_message(int(message_id))
            await message.add_reaction(emoji)
            
            logger.debug(
                "Reaction added",
                extra={"channel_id": channel_id, "message_id": message_id, "emoji": emoji}
            )
            return True
            
        except discord.Forbidden as e:
            raise DiscordPermissionError("add_reactions", str(channel_id)) from e
        except discord.HTTPException as e:
            logger.warning(f"Failed to add reaction: {e}")
            return False
        except Exception as e:
            logger.error(f"Error adding reaction: {e}", exc_info=True)
            return False
    
    async def check_permissions(
        self, 
        guild_id: Union[int, str], 
        channel_id: Union[int, str], 
        permissions: List[str]
    ) -> Dict[str, bool]:
        """Check bot permissions in a channel."""
        await self._wait_for_ready()
        try:
            guild = await self.get_guild(guild_id)
            if not guild:
                raise DiscordServerNotFoundError(str(guild_id))
            
            channel = await self.get_channel(channel_id)
            if not channel:
                raise DiscordChannelNotFoundError(str(channel_id))
            
            bot_permissions = channel.permissions_for(guild.me)
            
            return {perm: getattr(bot_permissions, perm, False) for perm in permissions}
            
        except Exception as e:
            logger.error(f"Error checking permissions: {e}", exc_info=True)
            return {perm: False for perm in permissions}
    
    async def get_guild_info(self, guild_id: Union[int, str]) -> Optional[Dict[str, Any]]:
        """Get detailed guild information."""
        await self._wait_for_ready()
        try:
            guild = await self.get_guild(guild_id)
            if not guild:
                return None
            
            return {
                "id": str(guild.id), "name": guild.name, "description": guild.description,
                "member_count": guild.member_count, "owner_id": str(guild.owner_id),
                "created_at": guild.created_at.isoformat(),
                "icon_url": str(guild.icon.url) if guild.icon else None,
                "banner_url": str(guild.banner.url) if guild.banner else None,
                "features": guild.features, "verification_level": str(guild.verification_level),
                "explicit_content_filter": str(guild.explicit_content_filter),
                "default_notifications": str(guild.default_notifications),
                "premium_tier": guild.premium_tier,
                "premium_subscription_count": guild.premium_subscription_count,
                "preferred_locale": str(guild.preferred_locale)
            }
            
        except Exception as e:
            logger.error(f"Error getting guild info for {guild_id}: {e}", exc_info=True)
            return None
    
    async def get_channel_info(self, channel_id: Union[int, str]) -> Optional[Dict[str, Any]]:
        """Get detailed channel information."""
        await self._wait_for_ready()
        try:
            channel = await self.get_channel(channel_id)
            if not channel:
                return None
            
            return {
                "id": str(channel.id), "name": channel.name, "type": str(channel.type),
                "position": channel.position, "topic": channel.topic, "nsfw": channel.nsfw,
                "created_at": channel.created_at.isoformat(), "guild_id": str(channel.guild.id),
                "category_id": str(channel.category_id) if channel.category_id else None,
                "slowmode_delay": channel.slowmode_delay,
                "permissions_synced": channel.permissions_synced
            }
            
        except Exception as e:
            logger.error(f"Error getting channel info for {channel_id}: {e}", exc_info=True)
            return None
    
    async def validate_server_setup(self, server_config: ServerConfig) -> Dict[str, Any]:
        """Validate server setup and permissions."""
        await self._wait_for_ready()
        results = {"valid": True, "errors": [], "warnings": [], "permissions": {}}
        
        try:
            guild = await self.get_guild(server_config.server_id)
            if not guild:
                results["valid"] = False
                results["errors"].append("Guild not found or bot not in guild")
                return results
            
            # Validate newsletter channel
            if server_config.newsletter_channel_id:
                required_perms = ["send_messages", "embed_links", "attach_files", "add_reactions", "read_message_history"]
                perms = await self.check_permissions(guild.id, server_config.newsletter_channel_id, required_perms)
                results["permissions"]["newsletter_channel"] = perms
                missing_perms = [p for p, has in perms.items() if not has]
                if missing_perms:
                    results["warnings"].append(f"Missing permissions in newsletter channel: {', '.join(missing_perms)}")

            # Validate whitelisted channels
            if server_config.whitelisted_channels:
                for cid in server_config.whitelisted_channels:
                    perms = await self.check_permissions(guild.id, cid, ["read_message_history", "view_channel"])
                    if not all(perms.values()):
                        results["warnings"].append(f"Cannot read messages in whitelisted channel {cid}")
            
        except DiscordChannelNotFoundError as e:
            results["errors"].append(f"Configuration error: Channel not found - {e}")
        except Exception as e:
            results["valid"] = False
            results["errors"].append(f"An unexpected validation error occurred: {e}")
        
        return results
    
    async def get_bot_stats(self) -> Dict[str, Any]:
        """Get bot statistics."""
        await self._wait_for_ready()
        if not self.is_ready:
            return {"is_ready": False}
            
        try:
            return {
                "guild_count": len(self.client.guilds),
                "total_members": sum(g.member_count for g in self.client.guilds if g.member_count),
                "uptime_seconds": (datetime.utcnow() - self.client.user.created_at).total_seconds(),
                "latency_ms": round(self.client.latency * 1000, 2),
                "is_ready": self.is_ready,
                "user_id": str(self.client.user.id),
                "username": str(self.client.user)
            }
            
        except Exception as e:
            logger.error(f"Error getting bot stats: {e}", exc_info=True)
            return {}

# --- Singleton Pattern for the Client ---
_discord_client: Optional[SnitchDiscordClient] = None

async def get_discord_client(settings: Optional[Settings] = None) -> SnitchDiscordClient:
    """Get or create the global Discord client instance."""
    global _discord_client
    
    if _discord_client is None:
        if settings is None:
            # In a real app, this would import and call get_settings()
            settings = Settings()
        
        _discord_client = SnitchDiscordClient(settings)
    
    return _discord_client

async def close_discord_client() -> None:
    """Close the global Discord client if it exists."""
    global _discord_client
    
    if _discord_client is not None:
        await _discord_client.close()
        _discord_client = None
