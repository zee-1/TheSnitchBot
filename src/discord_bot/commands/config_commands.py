"""
Configuration commands for The Snitch Discord Bot.
Handles server settings like persona, newsletter channel, and time.
"""

import discord
from typing import Dict, Any, Optional
from datetime import time
import re

from src.discord_bot.commands.base import AdminCommand, CommandContext, EmbedBuilder
from src.core.exceptions import InvalidCommandArgumentError
from src.core.logging import get_logger
from src.models.server import PersonaType
from src.utils.validation import validate_discord_id

logger = get_logger(__name__)


class SetPersonaCommand(AdminCommand):
    """Command to set the bot's persona for the server."""
    
    def __init__(self):
        super().__init__(
            name="set-persona",
            description="Set the bot's personality for this server",
            cooldown_seconds=10
        )
    
    async def validate_arguments(self, ctx: CommandContext, **kwargs) -> Dict[str, Any]:
        """Validate command arguments."""
        validated = {}
        
        persona = kwargs.get('persona')
        if not persona:
            raise InvalidCommandArgumentError(
                self.name,
                'persona',
                'Persona is required'
            )
        
        # Validate persona type
        try:
            validated['persona'] = PersonaType(persona.lower())
        except ValueError:
            valid_personas = [p.value for p in PersonaType]
            raise InvalidCommandArgumentError(
                self.name,
                'persona',
                f'Invalid persona. Valid options: {", ".join(valid_personas)}'
            )
        
        return validated
    
    async def execute(self, ctx: CommandContext, **kwargs) -> None:
        """Execute the set persona command."""
        persona = kwargs['persona']
        
        logger.info(
            "Set persona command executed",
            user_id=ctx.user_id,
            guild_id=ctx.guild_id,
            new_persona=persona.value
        )
        
        try:
            # Update server configuration
            server_repo = ctx.container.get_server_repository()
            success = await server_repo.update_persona(ctx.guild_id, persona)
            
            if success:
                embed = EmbedBuilder.success(
                    "Persona Updated",
                    f"Bot persona changed to **{persona.value.replace('_', ' ').title()}**! 🎭\n\n"
                    f"The newsletter and commands will now use this personality."
                )
                
                # Add persona description
                persona_descriptions = {
                    PersonaType.SASSY_REPORTER: "💅 Ready to spill the tea with attitude!",
                    PersonaType.INVESTIGATIVE_JOURNALIST: "🔍 Professional and thorough reporting.",
                    PersonaType.GOSSIP_COLUMNIST: "🍵 All about the drama and social dynamics.",
                    PersonaType.SPORTS_COMMENTATOR: "🏟️ High-energy play-by-play style!",
                    PersonaType.WEATHER_ANCHOR: "🌤️ Calm and informative delivery.",
                    PersonaType.CONSPIRACY_THEORIST: "🛸 Everything is connected... somehow."
                }
                
                description = persona_descriptions.get(persona, "A unique personality!")
                embed.add_field(
                    name="Personality Style",
                    value=description,
                    inline=False
                )
                
            else:
                embed = EmbedBuilder.error(
                    "Update Failed",
                    "Failed to update persona. Please try again."
                )
            
            await ctx.respond(embed=embed)
            
        except Exception as e:
            embed = EmbedBuilder.error(
                "Command Failed",
                "An error occurred while updating the persona."
            )
            await ctx.respond(embed=embed)
            logger.error(f"Error in set-persona command: {e}", exc_info=True)


class SetNewsChannelCommand(AdminCommand):
    """Command to set the newsletter delivery channel."""
    
    def __init__(self):
        super().__init__(
            name="set-news-channel",
            description="Set the channel where newsletters will be delivered",
            cooldown_seconds=10
        )
    
    async def validate_arguments(self, ctx: CommandContext, **kwargs) -> Dict[str, Any]:
        """Validate command arguments."""
        validated = {}
        
        channel = kwargs.get('channel')
        if not channel:
            # Use current channel if none specified
            validated['channel_id'] = ctx.channel_id
        else:
            # Handle channel mention or ID
            if isinstance(channel, discord.TextChannel):
                validated['channel_id'] = str(channel.id)
            else:
                # Try to parse as channel mention or ID
                channel_str = str(channel)
                # Remove <# and > if it's a mention
                channel_match = re.match(r'<#(\d+)>', channel_str)
                if channel_match:
                    validated['channel_id'] = channel_match.group(1)
                else:
                    # Assume it's a channel ID
                    try:
                        validated['channel_id'] = validate_discord_id(channel_str, 'channel')
                    except Exception as e:
                        raise InvalidCommandArgumentError(
                            self.name,
                            'channel',
                            f'Invalid channel format: {e}'
                        )
        
        return validated
    
    async def execute(self, ctx: CommandContext, **kwargs) -> None:
        """Execute the set news channel command."""
        channel_id = kwargs['channel_id']
        
        logger.info(
            "Set news channel command executed",
            user_id=ctx.user_id,
            guild_id=ctx.guild_id,
            new_channel_id=channel_id
        )
        
        try:
            # Verify channel exists and bot has permissions
            settings = ctx.container.get_settings()
            from src.discord_bot.client import get_discord_client
            discord_client = await get_discord_client(settings)
            
            channel = await discord_client.get_channel(channel_id)
            if not channel:
                embed = EmbedBuilder.error(
                    "Channel Not Found",
                    f"Could not find channel with ID `{channel_id}`."
                )
                await ctx.respond(embed=embed)
                return
            
            # Check permissions
            required_permissions = [
                "send_messages", "embed_links", "attach_files", "add_reactions"
            ]
            
            permissions = await discord_client.check_permissions(
                ctx.guild_id, channel_id, required_permissions
            )
            
            missing_permissions = [
                perm for perm, has_perm in permissions.items() if not has_perm
            ]
            
            if missing_permissions:
                embed = EmbedBuilder.warning(
                    "Missing Permissions",
                    f"I don't have the following permissions in {channel.mention}:\n"
                    f"```{', '.join(missing_permissions)}```\n"
                    f"Please grant these permissions and try again."
                )
                await ctx.respond(embed=embed)
                return
            
            # Update server configuration
            server_repo = ctx.container.get_server_repository()
            logger.info(f"Guild ID:{ctx.guild_id},Channel:{channel_id}")
            
            success = await server_repo.update_newsletter_channel(ctx.guild_id, channel_id)
            
            if success:
                embed = EmbedBuilder.success(
                    "Newsletter Channel Updated",
                    f"Newsletters will now be delivered to {channel.mention}! 📰\n\n"
                    f"Make sure I have the necessary permissions to post there."
                )
                
                embed.add_field(
                    name="📋 Required Permissions",
                    value="✅ Send Messages\n✅ Embed Links\n✅ Attach Files\n✅ Add Reactions",
                    inline=True
                )
                
                embed.add_field(
                    name="📅 Next Newsletter",
                    value=f"Will be delivered at the configured time in {channel.mention}",
                    inline=False
                )
                
            else:
                embed = EmbedBuilder.error(
                    "Update Failed",
                    "Failed to update newsletter channel. Please try again."
                )
            
            await ctx.respond(embed=embed)
            
        except Exception as e:
            embed = EmbedBuilder.error(
                "Command Failed",
                "An error occurred while updating the newsletter channel."
            )
            await ctx.respond(embed=embed)
            logger.error(f"Error in set-news-channel command: {e}", exc_info=True)


class SetNewsTimeCommand(AdminCommand):
    """Command to set the newsletter delivery time."""
    
    def __init__(self):
        super().__init__(
            name="set-news-time",
            description="Set the time when newsletters will be delivered (24-hour format: HH:MM)",
            cooldown_seconds=10
        )
    
    async def validate_arguments(self, ctx: CommandContext, **kwargs) -> Dict[str, Any]:
        """Validate command arguments."""
        validated = {}
        
        time_str = kwargs.get('time')
        if not time_str:
            raise InvalidCommandArgumentError(
                self.name,
                'time',
                'Time is required (format: HH:MM)'
            )
        
        # Validate time format
        time_pattern = re.compile(r'^([01]?[0-9]|2[0-3]):([0-5][0-9])$')
        match = time_pattern.match(time_str)
        
        if not match:
            raise InvalidCommandArgumentError(
                self.name,
                'time',
                'Invalid time format. Use HH:MM (24-hour format)'
            )
        
        hour, minute = int(match.group(1)), int(match.group(2))
        validated['newsletter_time'] = time(hour, minute)
        
        return validated
    
    async def execute(self, ctx: CommandContext, **kwargs) -> None:
        """Execute the set news time command."""
        newsletter_time = kwargs['newsletter_time']
        
        logger.info(
            "Set news time command executed",
            user_id=ctx.user_id,
            guild_id=ctx.guild_id,
            new_time=newsletter_time.strftime("%H:%M")
        )
        
        try:
            # Update server configuration
            server_repo = ctx.container.get_server_repository()
            success = await server_repo.update_newsletter_time(ctx.guild_id, newsletter_time)
            
            if success:
                embed = EmbedBuilder.success(
                    "Newsletter Time Updated",
                    f"Newsletters will now be delivered at **{newsletter_time.strftime('%H:%M')} UTC**! ⏰\n\n"
                    f"*Note: Time is in UTC. Convert to your local timezone as needed.*"
                )
                
                # Add timezone conversion help
                embed.add_field(
                    name="🌍 Timezone Info",
                    value="All times are in UTC. Use an online converter to find your local time.",
                    inline=False
                )
                
                embed.add_field(
                    name="📅 Next Newsletter",
                    value=f"Will be delivered tomorrow at {newsletter_time.strftime('%H:%M')} UTC",
                    inline=False
                )
                
            else:
                embed = EmbedBuilder.error(
                    "Update Failed",
                    "Failed to update newsletter time. Please try again."
                )
            
            await ctx.respond(embed=embed)
            
        except Exception as e:
            embed = EmbedBuilder.error(
                "Command Failed",
                "An error occurred while updating the newsletter time."
            )
            await ctx.respond(embed=embed)
            logger.error(f"Error in set-news-time command: {e}", exc_info=True)


class ServerStatusCommand(AdminCommand):
    """Command to view server configuration status."""
    
    def __init__(self):
        super().__init__(
            name="bot-status",
            description="View current bot configuration and status for this server",
            cooldown_seconds=5
        )
    
    async def execute(self, ctx: CommandContext, **kwargs) -> None:
        """Execute the server status command."""
        
        logger.info(
            "Bot status command executed",
            user_id=ctx.user_id,
            guild_id=ctx.guild_id
        )
        
        try:
            server_config = ctx.server_config
            
            # Create status embed
            embed = discord.Embed(
                title="🤖 The Snitch Bot Status",
                description=f"Configuration for **{server_config.server_name}**",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            # Basic info
            embed.add_field(
                name="🎭 Current Persona",
                value=server_config.persona.value.replace('_', ' ').title(),
                inline=True
            )
            
            embed.add_field(
                name="📰 Newsletter",
                value="✅ Enabled" if server_config.newsletter_enabled else "❌ Disabled",
                inline=True
            )
            
            embed.add_field(
                name="⏰ Newsletter Time",
                value=f"{server_config.newsletter_time.strftime('%H:%M')} UTC",
                inline=True
            )
            
            # Newsletter channel
            if server_config.newsletter_channel_id:
                embed.add_field(
                    name="📍 Newsletter Channel",
                    value=f"<#{server_config.newsletter_channel_id}>",
                    inline=True
                )
            else:
                embed.add_field(
                    name="📍 Newsletter Channel",
                    value="⚠️ Not configured",
                    inline=True
                )
            
            # Last newsletter
            if server_config.last_newsletter_sent:
                last_newsletter = server_config.last_newsletter_sent.strftime('%Y-%m-%d %H:%M UTC')
                embed.add_field(
                    name="📅 Last Newsletter",
                    value=last_newsletter,
                    inline=True
                )
            else:
                embed.add_field(
                    name="📅 Last Newsletter",
                    value="Never sent",
                    inline=True
                )
            
            # Feature status
            features = []
            if server_config.breaking_news_enabled:
                features.append("🚨 Breaking News")
            if server_config.fact_check_enabled:
                features.append("✅ Fact Check")
            if server_config.leak_command_enabled:
                features.append("🕵️ Leak")
            if server_config.tip_submission_enabled:
                features.append("💡 Tips")
            
            embed.add_field(
                name="🛠️ Enabled Features",
                value="\n".join(features) if features else "No features enabled",
                inline=False
            )
            
            # Admin info
            admin_count = len(server_config.admin_users)
            moderator_count = len(server_config.moderator_users)
            
            embed.add_field(
                name="👑 Admins",
                value=f"{admin_count} user(s)",
                inline=True
            )
            
            embed.add_field(
                name="🛡️ Moderators",
                value=f"{moderator_count} user(s)",
                inline=True
            )
            
            embed.add_field(
                name="📊 Server Status",
                value=server_config.status.value.title(),
                inline=True
            )
            
            embed.set_footer(text=f"Server ID: {server_config.server_id}")
            
            await ctx.respond(embed=embed)
            
        except Exception as e:
            embed = EmbedBuilder.error(
                "Command Failed",
                "An error occurred while retrieving server status."
            )
            await ctx.respond(embed=embed)
            logger.error(f"Error in bot-status command: {e}", exc_info=True)


# Register commands
from src.discord_bot.commands.base import command_registry
command_registry.register(SetPersonaCommand())
command_registry.register(SetNewsChannelCommand())
command_registry.register(SetNewsTimeCommand())
command_registry.register(ServerStatusCommand())


from datetime import datetime