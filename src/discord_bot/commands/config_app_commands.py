"""
Config app commands for The Snitch Discord Bot.
Properly configured Discord.py app_commands with parameters.
"""

import discord
from discord import app_commands
from typing import Literal, Optional

from src.core.dependencies import DependencyContainer
from src.core.logging import get_logger
from src.models.server import PersonaType
from src.discord_bot.commands.base import CommandContext, EmbedBuilder

logger = get_logger(__name__)


class ConfigCommands(app_commands.Group):
    """Config command group for admin settings."""
    
    def __init__(self, container: DependencyContainer):
        super().__init__(name="config", description="Configure bot settings")
        self.container = container
    
    async def _get_server_config(self, interaction: discord.Interaction):
        """Get server configuration and check admin permissions."""
        server_repo = self.container.get_server_repository()
        server_config = await server_repo.get_by_server_id_partition(str(interaction.guild_id))
        
        if not server_config:
            # Create default config
            from src.discord_bot.bot import SnitchBot
            bot_instance = interaction.client
            if hasattr(bot_instance, '_create_default_server_config'):
                server_config = await bot_instance._create_default_server_config(
                    interaction.guild_id, interaction.guild.name
                )
            else:
                # Check if interaction has been deferred
                if interaction.response.is_done():
                    await interaction.followup.send(
                        "❌ Server not configured. Please contact support.", ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        "❌ Server not configured. Please contact support.", ephemeral=True
                    )
                return None, False
        
        # Check admin permissions
        is_admin = (
            str(interaction.user.id) in server_config.admin_users or
            str(interaction.user.id) == server_config.owner_id or
            interaction.user.guild_permissions.administrator
        )
        
        if not is_admin:
            # Check if interaction has been deferred
            if interaction.response.is_done():
                await interaction.followup.send(
                    "❌ You need admin permissions to use config commands.", ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "❌ You need admin permissions to use config commands.", ephemeral=True
                )
            return None, False
            
        return server_config, True
    
    @app_commands.command(name="set-persona", description="Set the bot's personality")
    @app_commands.describe(persona="Choose the bot's personality type")
    async def set_persona(
        self, 
        interaction: discord.Interaction, 
        persona: Literal[
            "sassy_reporter", 
            "investigative_journalist", 
            "gossip_columnist", 
            "sports_commentator", 
            "weather_anchor", 
            "conspiracy_theorist"
        ]
    ):
        """Set the bot's persona for the server."""
        # Defer immediately to prevent timeout
        await interaction.response.defer(ephemeral=False)
        
        server_config, can_proceed = await self._get_server_config(interaction)
        if not can_proceed:
            return
            
        try:
            # Update persona
            server_repo = self.container.get_server_repository()
            success = await server_repo.update_persona(str(interaction.guild_id), PersonaType(persona))
            
            if success:
                embed = EmbedBuilder.success(
                    "Persona Updated",
                    f"Bot persona changed to **{persona.replace('_', ' ').title()}**! 🎭\n\n"
                    f"The newsletter and commands will now use this personality."
                )
                
                # Add persona description
                persona_descriptions = {
                    "sassy_reporter": "💅 Ready to spill the tea with attitude!",
                    "investigative_journalist": "🔍 Professional and thorough reporting.",
                    "gossip_columnist": "🍵 All about the drama and social dynamics.",
                    "sports_commentator": "🏟️ High-energy play-by-play style!",
                    "weather_anchor": "🌤️ Calm and informative delivery.",
                    "conspiracy_theorist": "🛸 Everything is connected... somehow."
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
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            embed = EmbedBuilder.error(
                "Command Failed",
                "An error occurred while updating the persona."
            )
            await interaction.followup.send(embed=embed)
            logger.error(f"Error in set-persona command: {e}", exc_info=True)
    
    @app_commands.command(name="set-newsletter-channel", description="Set the newsletter delivery channel")
    @app_commands.describe(channel="The channel where newsletters will be posted")
    async def set_newsletter_channel(
        self, 
        interaction: discord.Interaction, 
        channel: Optional[discord.TextChannel] = None
    ):
        """Set the newsletter delivery channel."""
        # Defer immediately to prevent timeout
        await interaction.response.defer(ephemeral=False)
        
        server_config, can_proceed = await self._get_server_config(interaction)
        if not can_proceed:
            return
            
        # Use current channel if none specified
        target_channel = channel or interaction.channel
        
        try:
            # Check bot permissions in target channel
            bot_member = interaction.guild.me
            channel_perms = target_channel.permissions_for(bot_member)
            
            missing_perms = []
            if not channel_perms.send_messages:
                missing_perms.append("Send Messages")
            if not channel_perms.embed_links:
                missing_perms.append("Embed Links")
            if not channel_perms.attach_files:
                missing_perms.append("Attach Files")
            
            if missing_perms:
                embed = EmbedBuilder.warning(
                    "Missing Permissions",
                    f"I don't have the following permissions in {target_channel.mention}:\n"
                    f"```{', '.join(missing_perms)}```\n"
                    f"Please grant these permissions and try again."
                )
                await interaction.followup.send(embed=embed)
                return
            
            # Update newsletter channel
            server_repo = self.container.get_server_repository()
            success = await server_repo.update_newsletter_channel(
                str(interaction.guild_id), str(target_channel.id)
            )
            
            if success:
                embed = EmbedBuilder.success(
                    "Newsletter Channel Updated",
                    f"Newsletters will now be delivered to {target_channel.mention}! 📰"
                )
                
                embed.add_field(
                    name="📋 Required Permissions",
                    value="✅ Send Messages\n✅ Embed Links\n✅ Attach Files",
                    inline=True
                )
                
                embed.add_field(
                    name="📅 Next Newsletter",
                    value=f"Will be delivered at the configured time in {target_channel.mention}",
                    inline=False
                )
            else:
                embed = EmbedBuilder.error(
                    "Update Failed",
                    "Failed to update newsletter channel. Please try again."
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            embed = EmbedBuilder.error(
                "Command Failed",
                "An error occurred while updating the newsletter channel."
            )
            await interaction.followup.send(embed=embed)
            logger.error(f"Error in set-newsletter-channel command: {e}", exc_info=True)
    
    @app_commands.command(name="set-newsletter-time", description="Set the newsletter delivery time")
    @app_commands.describe(time="Time in HH:MM format (24-hour, UTC)")
    async def set_newsletter_time(
        self, 
        interaction: discord.Interaction, 
        time: str
    ):
        """Set the newsletter delivery time."""
        # Defer immediately to prevent timeout
        await interaction.response.defer(ephemeral=False)
        
        server_config, can_proceed = await self._get_server_config(interaction)
        if not can_proceed:
            return
            
        # Validate time format
        import re
        time_pattern = re.compile(r'^([01]?[0-9]|2[0-3]):([0-5][0-9])$')
        if not time_pattern.match(time):
            embed = EmbedBuilder.error(
                "Invalid Time Format",
                "Please use HH:MM format (24-hour). Examples: 09:00, 14:30, 23:15"
            )
            await interaction.followup.send(embed=embed)
            return
            
        try:
            # Update newsletter time
            server_repo = self.container.get_server_repository()
            success = await server_repo.update_newsletter_time(str(interaction.guild_id), time)
            
            if success:
                embed = EmbedBuilder.success(
                    "Newsletter Time Updated",
                    f"Newsletters will now be delivered at **{time} UTC**! ⏰\n\n"
                    f"*Note: Time is in UTC. Convert to your local timezone as needed.*"
                )
                
                embed.add_field(
                    name="🌍 Timezone Info",
                    value="All times are in UTC. Use an online converter to find your local time.",
                    inline=False
                )
                
                embed.add_field(
                    name="📅 Next Newsletter",
                    value=f"Will be delivered tomorrow at {time} UTC",
                    inline=False
                )
            else:
                embed = EmbedBuilder.error(
                    "Update Failed",
                    "Failed to update newsletter time. Please try again."
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            embed = EmbedBuilder.error(
                "Command Failed",
                "An error occurred while updating the newsletter time."
            )
            await interaction.followup.send(embed=embed)
            logger.error(f"Error in set-newsletter-time command: {e}", exc_info=True)
    
    @app_commands.command(name="status", description="View current bot configuration and status")
    async def status(self, interaction: discord.Interaction):
        """View server configuration status."""
        # Defer immediately to prevent timeout
        await interaction.response.defer(ephemeral=False)
        
        server_config, can_proceed = await self._get_server_config(interaction)
        if not can_proceed:
            return
            
        try:
            from datetime import datetime
            
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
                value=server_config.persona.replace('_', ' ').title(),
                inline=True
            )
            
            embed.add_field(
                name="📰 Newsletter",
                value="✅ Enabled" if server_config.newsletter_enabled else "❌ Disabled",
                inline=True
            )
            
            embed.add_field(
                name="⏰ Newsletter Time",
                value=f"{server_config.newsletter_time} UTC",
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
                embed.add_field(
                    name="📅 Last Newsletter",
                    value=server_config.last_newsletter_sent[:10],  # Just the date part
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
            
            embed.set_footer(text=f"Server ID: {server_config.server_id}")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            embed = EmbedBuilder.error(
                "Command Failed",
                "An error occurred while retrieving server status."
            )
            await interaction.followup.send(embed=embed)
            logger.error(f"Error in status command: {e}", exc_info=True)


def setup_config_commands(bot, container: DependencyContainer):
    """Setup config commands on the bot."""
    config_commands = ConfigCommands(container)
    bot.tree.add_command(config_commands)
    return config_commands