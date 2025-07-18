"""
Discord client wrapper for The Snitch Discord Bot.
Provides high-level interface for Discord API operations.
"""

import asyncio
from typing import List, Optional, Dict, Any, Union
import discord
from discord.ext import commands
from datetime import datetime, timedelta
import logging

from src.core.config import Settings
from src.core.exceptions import (
    DiscordError, DiscordAPIError, DiscordPermissionError,
    DiscordServerNotFoundError, DiscordChannelNotFoundError,
    DiscordUserNotFoundError
)
from src.core.logging import get_logger
from src.utils.retry import api_retry
from src.models.message import Message
from src.models.server import ServerConfig

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
        self.tree = discord.app_commands.CommandTree(self.client)
        
        # Bot state
        self._ready = False
        self._guilds_cache: Dict[int, discord.Guild] = {}
        
        # Setup event handlers
        self._setup_event_handlers()
    
    def _setup_event_handlers(self) -> None:
        """Set up Discord event handlers."""
        
        @self.client.event
        async def on_ready():
            """Handle bot ready event."""
            self._ready = True
            logger.info(
                "Discord client ready",
                bot_user=str(self.client.user),
                guild_count=len(self.client.guilds),
                user_count=sum(guild.member_count for guild in self.client.guilds)
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
        
        @self.client.event
        async def on_guild_join(guild: discord.Guild):
            """Handle guild join event."""
            self._guilds_cache[guild.id] = guild
            logger.info(
                "Joined new guild",
                guild_id=guild.id,
                guild_name=guild.name,
                member_count=guild.member_count
            )
        
        @self.client.event
        async def on_guild_remove(guild: discord.Guild):
            """Handle guild remove event."""
            self._guilds_cache.pop(guild.id, None)
            logger.info(
                "Removed from guild",
                guild_id=guild.id,
                guild_name=guild.name
            )
        
        @self.client.event
        async def on_error(event: str, *args, **kwargs):
            """Handle Discord client errors."""
            logger.error(f"Discord client error in event {event}", exc_info=True)
    
    async def start(self) -> None:
        """Start the Discord client."""
        try:
            await self.client.start(self.settings.discord_token)
        except Exception as e:
            logger.error(f"Failed to start Discord client: {e}")
            raise DiscordError(f"Failed to start Discord client: {e}")
    
    async def close(self) -> None:
        """Close the Discord client."""
        try:
            await self.client.close()
            self._ready = False
            logger.info("Discord client closed")
        except Exception as e:
            logger.error(f"Error closing Discord client: {e}")
    
    @property
    def is_ready(self) -> bool:
        """Check if the client is ready."""
        return self._ready and self.client.is_ready()
    
    @api_retry
    async def get_guild(self, guild_id: Union[int, str]) -> Optional[discord.Guild]:
        """Get guild by ID."""
        try:
            guild_id = int(guild_id)
            
            # Check cache first
            if guild_id in self._guilds_cache:
                return self._guilds_cache[guild_id]
            
            # Fetch from Discord
            guild = self.client.get_guild(guild_id)
            if guild:
                self._guilds_cache[guild_id] = guild
                return guild
            
            # Try fetching if not in cache
            try:
                guild = await self.client.fetch_guild(guild_id)
                self._guilds_cache[guild_id] = guild
                return guild
            except discord.NotFound:
                return None
            
        except Exception as e:
            logger.error(f"Error getting guild {guild_id}: {e}")
            raise DiscordAPIError(f"Failed to get guild: {e}")
    
    @api_retry
    async def get_channel(self, channel_id: Union[int, str]) -> Optional[discord.TextChannel]:
        """Get text channel by ID."""
        try:
            channel_id = int(channel_id)
            channel = self.client.get_channel(channel_id)
            
            if channel and isinstance(channel, discord.TextChannel):
                return channel
            
            # Try fetching if not in cache
            try:
                channel = await self.client.fetch_channel(channel_id)
                if isinstance(channel, discord.TextChannel):
                    return channel
            except discord.NotFound:
                return None
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting channel {channel_id}: {e}")
            raise DiscordAPIError(f"Failed to get channel: {e}")
    
    @api_retry
    async def get_user(self, user_id: Union[int, str]) -> Optional[discord.User]:
        """Get user by ID."""
        try:
            user_id = int(user_id)
            user = self.client.get_user(user_id)
            
            if user:
                return user
            
            # Try fetching if not in cache
            try:
                user = await self.client.fetch_user(user_id)
                return user
            except discord.NotFound:
                return None
            
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {e}")
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
        try:
            channel = await self.get_channel(channel_id)
            if not channel:
                raise DiscordChannelNotFoundError(str(channel_id))
            
            # Check permissions
            if not channel.permissions_for(channel.guild.me).send_messages:
                raise DiscordPermissionError("send_messages", str(channel.guild.id))
            
            message = await channel.send(
                content=content,
                embed=embed,
                file=file,
                view=view
            )
            
            logger.info(
                "Message sent successfully",
                channel_id=channel_id,
                message_id=message.id,
                has_embed=embed is not None,
                has_file=file is not None
            )
            
            return message
            
        except discord.Forbidden:
            raise DiscordPermissionError("send_messages", str(channel_id))
        except discord.HTTPException as e:
            raise DiscordAPIError(f"HTTP error sending message: {e}")
        except Exception as e:
            logger.error(f"Error sending message to {channel_id}: {e}")
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
        try:
            channel = await self.get_channel(channel_id)
            if not channel:
                raise DiscordChannelNotFoundError(str(channel_id))
            
            # Check permissions
            if not channel.permissions_for(channel.guild.me).read_message_history:
                raise DiscordPermissionError("read_message_history", str(channel.guild.id))
            
            messages = []
            async for discord_message in channel.history(
                limit=limit,
                before=before,
                after=after
            ):
                # Convert to our Message model
                message = Message.from_discord_message(discord_message, str(channel.guild.id))
                messages.append(message)
            
            logger.info(
                "Retrieved messages",
                channel_id=channel_id,
                message_count=len(messages),
                limit=limit
            )
            
            return messages
            
        except discord.Forbidden:
            raise DiscordPermissionError("read_message_history", str(channel_id))
        except Exception as e:
            logger.error(f"Error getting messages from {channel_id}: {e}")
            raise DiscordAPIError(f"Failed to get messages: {e}")
    
    @api_retry
    async def get_message(
        self, 
        channel_id: Union[int, str], 
        message_id: Union[int, str]
    ) -> Optional[Message]:
        """Get a specific message by ID."""
        try:
            channel = await self.get_channel(channel_id)
            if not channel:
                raise DiscordChannelNotFoundError(str(channel_id))
            
            discord_message = await channel.fetch_message(int(message_id))
            message = Message.from_discord_message(discord_message, str(channel.guild.id))
            
            return message
            
        except discord.NotFound:
            return None
        except discord.Forbidden:
            raise DiscordPermissionError("read_message_history", str(channel_id))
        except Exception as e:
            logger.error(f"Error getting message {message_id} from {channel_id}: {e}")
            raise DiscordAPIError(f"Failed to get message: {e}")
    
    @api_retry
    async def add_reaction(
        self, 
        channel_id: Union[int, str], 
        message_id: Union[int, str], 
        emoji: str
    ) -> bool:
        """Add reaction to a message."""
        try:
            channel = await self.get_channel(channel_id)
            if not channel:
                raise DiscordChannelNotFoundError(str(channel_id))
            
            message = await channel.fetch_message(int(message_id))
            await message.add_reaction(emoji)
            
            logger.debug(
                "Reaction added",
                channel_id=channel_id,
                message_id=message_id,
                emoji=emoji
            )
            
            return True
            
        except discord.Forbidden:
            raise DiscordPermissionError("add_reactions", str(channel_id))
        except discord.HTTPException as e:
            logger.warning(f"Failed to add reaction: {e}")
            return False
        except Exception as e:
            logger.error(f"Error adding reaction: {e}")
            return False
    
    async def check_permissions(
        self, 
        guild_id: Union[int, str], 
        channel_id: Union[int, str], 
        permissions: List[str]
    ) -> Dict[str, bool]:
        """Check bot permissions in a channel."""
        try:
            guild = await self.get_guild(guild_id)
            if not guild:
                raise DiscordServerNotFoundError(str(guild_id))
            
            channel = await self.get_channel(channel_id)
            if not channel:
                raise DiscordChannelNotFoundError(str(channel_id))
            
            bot_permissions = channel.permissions_for(guild.me)
            
            permission_status = {}
            for permission in permissions:
                permission_status[permission] = getattr(bot_permissions, permission, False)
            
            return permission_status
            
        except Exception as e:
            logger.error(f"Error checking permissions: {e}")
            return {perm: False for perm in permissions}
    
    async def get_guild_info(self, guild_id: Union[int, str]) -> Optional[Dict[str, Any]]:
        """Get guild information."""
        try:
            guild = await self.get_guild(guild_id)
            if not guild:
                return None
            
            return {
                "id": str(guild.id),
                "name": guild.name,
                "description": guild.description,
                "member_count": guild.member_count,
                "owner_id": str(guild.owner_id),
                "created_at": guild.created_at.isoformat(),
                "icon_url": guild.icon.url if guild.icon else None,
                "banner_url": guild.banner.url if guild.banner else None,
                "features": guild.features,
                "verification_level": str(guild.verification_level),
                "explicit_content_filter": str(guild.explicit_content_filter),
                "default_notifications": str(guild.default_notifications),
                "premium_tier": guild.premium_tier,
                "premium_subscription_count": guild.premium_subscription_count,
                "preferred_locale": str(guild.preferred_locale)
            }
            
        except Exception as e:
            logger.error(f"Error getting guild info for {guild_id}: {e}")
            return None
    
    async def get_channel_info(self, channel_id: Union[int, str]) -> Optional[Dict[str, Any]]:
        """Get channel information."""
        try:
            channel = await self.get_channel(channel_id)
            if not channel:
                return None
            
            return {
                "id": str(channel.id),
                "name": channel.name,
                "type": str(channel.type),
                "position": channel.position,
                "topic": channel.topic,
                "nsfw": channel.nsfw,
                "created_at": channel.created_at.isoformat(),
                "guild_id": str(channel.guild.id),
                "category_id": str(channel.category_id) if channel.category_id else None,
                "slowmode_delay": channel.slowmode_delay,
                "permissions_synced": channel.permissions_synced
            }
            
        except Exception as e:
            logger.error(f"Error getting channel info for {channel_id}: {e}")
            return None
    
    async def validate_server_setup(self, server_config: ServerConfig) -> Dict[str, Any]:
        """Validate server setup and permissions."""
        validation_results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "permissions": {}
        }
        
        try:
            # Check if guild exists
            guild = await self.get_guild(server_config.server_id)
            if not guild:
                validation_results["valid"] = False
                validation_results["errors"].append("Guild not found or bot not in guild")
                return validation_results
            
            # Check newsletter channel if configured
            if server_config.newsletter_channel_id:
                channel = await self.get_channel(server_config.newsletter_channel_id)
                if not channel:
                    validation_results["errors"].append("Newsletter channel not found")
                else:
                    # Check permissions
                    required_permissions = [
                        "send_messages", "embed_links", "attach_files", 
                        "add_reactions", "read_message_history"
                    ]
                    
                    permissions = await self.check_permissions(
                        server_config.server_id,
                        server_config.newsletter_channel_id,
                        required_permissions
                    )
                    
                    validation_results["permissions"]["newsletter_channel"] = permissions
                    
                    missing_permissions = [
                        perm for perm, has_perm in permissions.items() 
                        if not has_perm
                    ]
                    
                    if missing_permissions:
                        validation_results["warnings"].append(
                            f"Missing permissions in newsletter channel: {', '.join(missing_permissions)}"
                        )
            
            # Check if bot can read messages in whitelisted channels
            if server_config.whitelisted_channels:
                for channel_id in server_config.whitelisted_channels:
                    channel = await self.get_channel(channel_id)
                    if not channel:
                        validation_results["warnings"].append(
                            f"Whitelisted channel {channel_id} not found"
                        )
                    else:
                        permissions = await self.check_permissions(
                            server_config.server_id,
                            channel_id,
                            ["read_message_history", "view_channel"]
                        )
                        
                        if not all(permissions.values()):
                            validation_results["warnings"].append(
                                f"Cannot read messages in channel {channel_id}"
                            )
            
        except Exception as e:
            validation_results["valid"] = False
            validation_results["errors"].append(f"Validation error: {e}")
        
        return validation_results
    
    async def get_bot_stats(self) -> Dict[str, Any]:
        """Get bot statistics."""
        try:
            guild_count = len(self.client.guilds)
            total_members = sum(guild.member_count for guild in self.client.guilds)
            
            return {
                "guild_count": guild_count,
                "total_members": total_members,
                "uptime_seconds": (datetime.now() - self.client.user.created_at).total_seconds(),
                "latency_ms": round(self.client.latency * 1000, 2),
                "is_ready": self.is_ready,
                "user_id": str(self.client.user.id),
                "username": str(self.client.user)
            }
            
        except Exception as e:
            logger.error(f"Error getting bot stats: {e}")
            return {}


# Global Discord client instance
_discord_client: Optional[SnitchDiscordClient] = None


async def get_discord_client(settings: Optional[Settings] = None) -> SnitchDiscordClient:
    """Get or create the global Discord client."""
    global _discord_client
    
    if _discord_client is None:
        if settings is None:
            from src.core.config import get_settings
            settings = get_settings()
        
        _discord_client = SnitchDiscordClient(settings)
    
    return _discord_client


async def close_discord_client() -> None:
    """Close the global Discord client."""
    global _discord_client
    
    if _discord_client is not None:
        await _discord_client.close()
        _discord_client = None