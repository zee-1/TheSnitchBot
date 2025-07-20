"""
Help command for The Snitch Discord Bot.
Shows available commands and usage information.
"""

import discord
from typing import Dict, Any

from src.discord_bot.commands.base import PublicCommand, CommandContext, EmbedBuilder
from src.core.logging import get_logger

logger = get_logger(__name__)


class HelpCommand(PublicCommand):
    """Command to show help and available commands."""
    
    def __init__(self):
        super().__init__(
            name="help",
            description="Show available commands and bot information",
            cooldown_seconds=5
        )
    
    async def execute(self, ctx: CommandContext, **kwargs) -> None:
        """Execute the help command."""
        
        logger.info(
            "Help command executed",
            user_id=ctx.user_id,
            guild_id=ctx.guild_id
        )
        
        try:
            # Create help embed
            embed = discord.Embed(
                title="🤖 The Snitch Bot - Command Help",
                description="I'm here to keep your community entertained with daily newsletters and breaking news!",
                color=discord.Color.blue()
            )
            
            # Admin Commands
            admin_commands = [
                "`/config set-persona` - Set bot personality",
                "`/config set-news-channel` - Set newsletter channel", 
                "`/config set-news-time` - Set newsletter time",
                "`/config bot-status` - View bot configuration"
            ]
            
            embed.add_field(
                name="👑 Admin Commands",
                value="\n".join(admin_commands),
                inline=False
            )
            
            # Public Commands
            public_commands = [
                "`/breaking-news` - Generate breaking news report",
                "`/fact-check` - Get fact-checking on recent topics",
                "`/leak` - Get exclusive server insights",
                "`/help` - Show this help message"
            ]
            
            embed.add_field(
                name="📢 Public Commands", 
                value="\n".join(public_commands),
                inline=False
            )
            
            # Bot Features
            features = [
                "🗞️ Daily automated newsletters",
                "📊 Message analysis and trending topics", 
                "🤖 Multiple personality modes",
                "⚡ Real-time breaking news alerts",
                "🔍 Smart fact-checking capabilities"
            ]
            
            embed.add_field(
                name="✨ Bot Features",
                value="\n".join(features),
                inline=False
            )
            
            # Permission Info
            if ctx.is_admin:
                embed.add_field(
                    name="🛡️ Your Permissions",
                    value="✅ **Admin** - You can use all commands",
                    inline=True
                )
            elif ctx.is_moderator:
                embed.add_field(
                    name="🛡️ Your Permissions", 
                    value="✅ **Moderator** - You can use most commands",
                    inline=True
                )
            else:
                embed.add_field(
                    name="🛡️ Your Permissions",
                    value="👤 **Member** - You can use public commands",
                    inline=True
                )
            
            # Setup Info
            setup_info = []
            if not ctx.server_config.newsletter_channel_id:
                setup_info.append("⚠️ Newsletter channel not set")
            if not ctx.server_config.newsletter_enabled:
                setup_info.append("⚠️ Newsletter disabled")
            
            if setup_info:
                embed.add_field(
                    name="⚙️ Setup Required",
                    value="\n".join(setup_info) + "\n\nContact an admin to configure the bot.",
                    inline=False
                )
            else:
                embed.add_field(
                    name="✅ Bot Status",
                    value="Fully configured and ready!",
                    inline=False
                )
            
            embed.set_footer(text="Use /config bot-status for detailed configuration info")
            
            await ctx.respond(embed=embed)
            
        except Exception as e:
            embed = EmbedBuilder.error(
                "Help Command Failed",
                "An error occurred while showing help information."
            )
            await ctx.respond(embed=embed)
            logger.error(f"Error in help command: {e}", exc_info=True)


# Register the command
from src.discord_bot.commands.base import command_registry
command_registry.register(HelpCommand())