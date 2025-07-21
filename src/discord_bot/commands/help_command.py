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
                title="🤖 The Snitch Bot - Complete Command Reference",
                description=(
                    "**Welcome to The Snitch!** 🕵️\n\n"
                    "I'm your AI-powered community reporter, ready to transform server activity into "
                    "entertaining content! From daily newsletters to real-time breaking news, "
                    "I'll keep your community engaged with intelligent analysis and personality.\n\n"
                    "**Quick Start:** `/config set-persona` → `/config set-newsletter-channel` → You're ready!"
                ),
                color=discord.Color.blue()
            )
            
            # Admin Commands - Configuration & Management
            admin_config_commands = [
                "`/config set-persona <persona>` - Set bot personality (sassy_reporter, investigative_journalist, gossip_columnist, sports_commentator, weather_anchor, conspiracy_theorist)",
                "`/config set-newsletter-channel [channel]` - Set newsletter delivery channel (uses current channel if none specified)", 
                "`/config set-newsletter-time <time>` - Set newsletter delivery time in HH:MM UTC format (e.g., 09:00, 14:30)",
                "`/config set-output-channel [channel]` - Set channel for command outputs (breaking news, leaks, etc.)",
                "`/config set-bot-updates-channel [channel]` - Set channel for bot status updates and notifications (startup, features, errors)",
                "`/config status` - View complete bot configuration and feature status"
            ]
            
            admin_tip_commands = [
                "`/approve-tip <tip_id> <action> [notes]` - Approve, process, or dismiss submitted tips",
                "`/list-tips [status] [priority]` - List submitted tips with filtering options",
                "`/tip-stats [days]` - View tip submission statistics and analytics"
            ]
            
            admin_utility_commands = [
                "`/sync-commands` - Manually sync Discord slash commands (maintenance tool)"
            ]
            
            embed.add_field(
                name="👑 Admin - Configuration",
                value="\n".join(admin_config_commands),
                inline=False
            )
            
            embed.add_field(
                name="👑 Admin - Tip Management", 
                value="\n".join(admin_tip_commands),
                inline=False
            )
            
            embed.add_field(
                name="👑 Admin - Utilities", 
                value="\n".join(admin_utility_commands),
                inline=False
            )
            
            # Content Generation Commands
            content_commands = [
                "`/content breaking-news [count] [hours]` - Generate breaking news from recent activity (10-100 messages, 1-24 hours)",
                "`/content fact-check [message_id]` - Fact-check a message with humorous verdict (or use right-click context menu)",
                "`/content controversy-check [message_id]` - Analyze controversy level of a message (or use right-click context menu)",
                "`/content submit-tip <content> [category] [anonymous]` - Submit anonymous tips for investigation with categories"
            ]
            
            # Public Commands  
            public_commands = [
                "`/leak` - Get exclusive server insights, rumors, and behind-the-scenes information",
                "`/help` - Show this comprehensive help message with all commands"
            ]
            
            embed.add_field(
                name="📰 Content Generation", 
                value="\n".join(content_commands),
                inline=False
            )
            
            embed.add_field(
                name="📢 Public Commands", 
                value="\n".join(public_commands),
                inline=False
            )
            
            # Bot Features
            features = [
                "🗞️ **Daily Newsletters** - AI-generated summaries of server activity with personality",
                "📊 **Smart Analysis** - Message controversy detection and community insights", 
                "🤖 **Multiple Personas** - 6 unique personalities (sassy reporter, investigative journalist, etc.)",
                "⚡ **Breaking News** - Real-time news generation from channel activity patterns",
                "🔍 **Fact-Checking** - Humorous fact-checking with context menu support",
                "🕵️ **Tip System** - Anonymous submission, categorization, and management workflow",
                "📈 **Content Analytics** - Smart categorization, trending topics, and engagement metrics",
                "🎯 **Context Menus** - Right-click messages for quick fact-check and controversy analysis"
            ]
            
            embed.add_field(
                name="✨ Bot Features",
                value="\n".join(features),
                inline=False
            )
            
            # Usage Tips
            usage_tips = [
                "💡 **Context Menus**: Right-click any message → Apps → 'Fact Check' or 'Controversy Check' for quick analysis",
                "📝 **Tip Categories**: Use `/content submit-tip` with categories: general, drama, controversy, breaking_news, rumor, investigation",
                "⏰ **Newsletter Setup**: Set channel with `/config set-newsletter-channel`, time with `/config set-newsletter-time`",
                "🎭 **Persona Examples**: Try 'sassy_reporter' for attitude, 'conspiracy_theorist' for fun theories",
                "📊 **Parameter Ranges**: Breaking news supports 10-100 messages and 1-24 hour time windows",
                "🔧 **Admin Tools**: Use `/config status` to see complete configuration and `/list-tips` to manage submissions"
            ]
            
            embed.add_field(
                name="💡 Usage Tips",
                value="\n".join(usage_tips),
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
            
            # Command Syntax Guide
            syntax_guide = [
                "📝 **Parameter Types:**",
                "• `<required>` - Must provide this parameter",
                "• `[optional]` - Optional parameter with default value",
                "• `<choice1|choice2>` - Choose one of the listed options",
                "",
                "📱 **Context Menus:** Right-click any message → Apps → Select analysis tool",
                "⚡ **Quick Access:** Most commands work without parameters using smart defaults"
            ]
            
            embed.add_field(
                name="📖 Command Syntax Guide",
                value="\n".join(syntax_guide),
                inline=False
            )
            
            # Setup Info
            setup_info = []
            recommendations = []
            
            if not ctx.server_config.newsletter_channel_id:
                setup_info.append("⚠️ Newsletter channel not set")
                recommendations.append("• Run `/config set-newsletter-channel` to enable daily newsletters")
            if not ctx.server_config.newsletter_enabled:
                setup_info.append("⚠️ Newsletter disabled")
            if not ctx.server_config.tip_submission_enabled:
                setup_info.append("⚠️ Tip submission disabled")
                recommendations.append("• Enable tips for community engagement and content ideas")
            
            if ctx.server_config.persona == "sassy_reporter":
                recommendations.append("• Try different personas with `/config set-persona` for variety")
            
            if setup_info:
                embed.add_field(
                    name="⚙️ Configuration Status",
                    value="\n".join(setup_info) + "\n\n**Recommendations:**\n" + "\n".join(recommendations) + "\n\n*Contact an admin to complete setup.*",
                    inline=False
                )
            else:
                embed.add_field(
                    name="✅ Bot Status",
                    value=f"**Fully configured and ready!**\n\n🎭 Current Persona: **{ctx.server_config.persona.replace('_', ' ').title()}**\n📰 Newsletter: **{'Enabled' if ctx.server_config.newsletter_enabled else 'Disabled'}**\n🕵️ Tips: **{'Enabled' if ctx.server_config.tip_submission_enabled else 'Disabled'}**",
                    inline=False
                )
            
            embed.set_footer(text="Use /config status for detailed configuration • Parameters: <required> [optional]")
            
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