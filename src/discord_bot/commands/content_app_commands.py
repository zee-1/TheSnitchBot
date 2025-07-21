"""
Content generation app commands for The Snitch Discord Bot.
Properly configured Discord.py app_commands with parameters for content commands.
"""

import discord
from discord import app_commands
from typing import Optional

from src.core.dependencies import DependencyContainer
from src.core.logging import get_logger
from src.discord_bot.commands.base import CommandContext, EmbedBuilder
from src.discord_bot.commands.breaking_news import BreakingNewsCommand
from src.discord_bot.commands.fact_check import FactCheckCommand
from src.discord_bot.commands.tip_command import SubmitTipCommand
from src.discord_bot.commands.controversy_check import ControversyCheckCommand
from src.discord_bot.commands.community_pulse import CommunityPulseCommand

logger = get_logger(__name__)


class ContentCommands(app_commands.Group):
    """Content generation command group."""
    
    def __init__(self, container: DependencyContainer):
        super().__init__(name="content", description="Generate content and analyze messages")
        self.container = container
        self.breaking_news_cmd = BreakingNewsCommand()
        self.fact_check_cmd = FactCheckCommand()
        self.tip_cmd = SubmitTipCommand()
        self.controversy_cmd = ControversyCheckCommand()
        self.pulse_cmd = CommunityPulseCommand()
    
    async def _create_context(self, interaction: discord.Interaction) -> CommandContext:
        """Create command context from interaction."""
        # Get server config
        server_repo = self.container.get_server_repository()
        server_config = await server_repo.get_by_server_id_partition(str(interaction.guild_id))
        
        if not server_config:
            raise ValueError("Server not configured")
        
        return CommandContext(
            interaction=interaction,
            container=self.container,
            server_config=server_config
        )
    
    @app_commands.command(name="breaking-news", description="Generate breaking news from recent channel activity")
    @app_commands.describe(
        message_count="Number of recent messages to analyze (10-1000, default: 50)",
        time_window="Hours of message history to analyze (1-49, default: 2)"
    )
    async def breaking_news(
        self,
        interaction: discord.Interaction,
        message_count: Optional[app_commands.Range[int, 10, 1000]] = 50,
        time_window: Optional[app_commands.Range[int, 1, 48]] = 2
    ):
        """Generate breaking news bulletin from recent channel activity."""
        try:
            # Defer response since AI processing takes time
            await interaction.response.defer()
            
            # Create context
            ctx = await self._create_context(interaction)
            
            # Execute the command
            await self.breaking_news_cmd.execute(ctx, message_count=message_count, time_window=time_window)
            
        except Exception as e:
            logger.error(f"Error in breaking-news app command: {e}", exc_info=True)
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(
                        "❌ An error occurred while generating breaking news. Please try again later.",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        "❌ An error occurred while generating breaking news. Please try again later.",
                        ephemeral=True
                    )
            except:
                pass  # Ignore if we can't send error message
    
    @app_commands.command(name="fact-check", description="Fact-check a message with a humorous verdict")
    @app_commands.describe(message_id="Message ID (or right-click message and use Apps > fact-check)")
    async def fact_check(
        self,
        interaction: discord.Interaction,
        message_id: Optional[str] = None
    ):
        """Fact-check a message with a humorous verdict."""
        try:
            # Create context
            ctx = await self._create_context(interaction)
            
            # Execute the command
            await self.fact_check_cmd.execute(ctx, message_id=message_id)
            
        except Exception as e:
            logger.error(f"Error in fact-check app command: {e}", exc_info=True)
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(
                        "❌ An error occurred while fact-checking. Please try again later.",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        "❌ An error occurred while fact-checking. Please try again later.",
                        ephemeral=True
                    )
            except:
                pass  # Ignore if we can't send error message
    
    @app_commands.command(name="submit-tip", description="Submit an anonymous tip for investigation")
    @app_commands.describe(
        content="The tip content (what you want to report)",
        category="Category of tip",
        anonymous="Submit anonymously (default: True)"
    )
    @app_commands.choices(category=[
        app_commands.Choice(name="General", value="general"),
        app_commands.Choice(name="Drama", value="drama"),
        app_commands.Choice(name="Controversy", value="controversy"),
        app_commands.Choice(name="Breaking News", value="breaking_news"),
        app_commands.Choice(name="Rumor", value="rumor"),
        app_commands.Choice(name="Investigation", value="investigation")
    ])
    async def submit_tip(
        self,
        interaction: discord.Interaction,
        content: str,
        category: Optional[str] = "general",
        anonymous: Optional[bool] = True
    ):
        """Submit an anonymous tip for investigation."""
        try:
            # Create context
            ctx = await self._create_context(interaction)
            
            # Execute the command
            await self.tip_cmd.execute(ctx, content=content, category=category, anonymous=anonymous)
            
        except Exception as e:
            logger.error(f"Error in submit-tip app command: {e}", exc_info=True)
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(
                        "❌ An error occurred while submitting your tip. Please try again later.",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        "❌ An error occurred while submitting your tip. Please try again later.",
                        ephemeral=True
                    )
            except:
                pass  # Ignore if we can't send error message
    
    @app_commands.command(name="controversy-check", description="Check how controversial a message is using AI")
    @app_commands.describe(message_id="Message ID (or right-click message and use Apps > controversy-check)")
    async def controversy_check(
        self,
        interaction: discord.Interaction,
        message_id: Optional[str] = None
    ):
        """Check how controversial a message is using AI analysis."""
        try:
            # Create context
            ctx = await self._create_context(interaction)
            
            # Execute the command
            await self.controversy_cmd.execute(ctx, message_id=message_id)
            
        except Exception as e:
            logger.error(f"Error in controversy-check app command: {e}", exc_info=True)
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(
                        "❌ An error occurred while analyzing controversy. Please try again later.",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        "❌ An error occurred while analyzing controversy. Please try again later.",
                        ephemeral=True
                    )
            except:
                pass  # Ignore if we can't send error message
    
    @app_commands.command(name="community-pulse", description="Get real-time community insights and social dynamics")
    @app_commands.describe(
        timeframe="Time period to analyze",
        style="Presentation style for the pulse report", 
        focus="Specific aspect to focus on"
    )
    @app_commands.choices(timeframe=[
        app_commands.Choice(name="Last Hour", value="1h"),
        app_commands.Choice(name="Last 6 Hours", value="6h"),
        app_commands.Choice(name="Last 24 Hours", value="24h"),
        app_commands.Choice(name="Last Week", value="7d"),
        app_commands.Choice(name="Last Month", value="30d")
    ])
    @app_commands.choices(style=[
        app_commands.Choice(name="Dashboard", value="dashboard"),
        app_commands.Choice(name="Story Mode", value="story"),
        app_commands.Choice(name="Weather Report", value="weather"),
        app_commands.Choice(name="Gaming Stats", value="gaming"),
        app_commands.Choice(name="Social Network", value="network")
    ])
    @app_commands.choices(focus=[
        app_commands.Choice(name="Overall Pulse", value="overall"),
        app_commands.Choice(name="Social Connections", value="social"),
        app_commands.Choice(name="Trending Topics", value="topics"),
        app_commands.Choice(name="Mood Analysis", value="mood"),
        app_commands.Choice(name="Activity Patterns", value="activity"),
        app_commands.Choice(name="Hidden Patterns", value="patterns")
    ])
    async def community_pulse(
        self,
        interaction: discord.Interaction,
        timeframe: Optional[str] = "24h",
        style: Optional[str] = "dashboard",
        focus: Optional[str] = "overall"
    ):
        """Generate community pulse analysis with social insights."""
        try:
            # Defer response since analysis takes time
            await interaction.response.defer()
            
            # Create context
            ctx = await self._create_context(interaction)
            
            # Execute the command
            await self.pulse_cmd.execute(ctx, timeframe=timeframe, style=style, focus=focus)
            
        except Exception as e:
            logger.error(f"Error in community-pulse app command: {e}", exc_info=True)
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(
                        "❌ An error occurred while generating community pulse. Please try again later.",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        "❌ An error occurred while generating community pulse. Please try again later.",
                        ephemeral=True
                    )
            except:
                pass  # Ignore if we can't send error message


async def setup_content_commands(tree: app_commands.CommandTree, container: DependencyContainer):
    """Setup content generation app commands."""
    content_commands = ContentCommands(container)
    tree.add_command(content_commands)
    logger.info("Content app commands registered")