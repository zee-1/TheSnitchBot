"""
Breaking news command for The Snitch Discord Bot.
Generates immediate news bulletin from recent channel activity.
"""

import discord
from typing import Dict, Any
from datetime import datetime, timedelta

from src.discord_bot.commands.base import PublicCommand, CommandContext, EmbedBuilder
from src.core.exceptions import InsufficientContentError, AIServiceError
from src.core.logging import get_logger

logger = get_logger(__name__)


class BreakingNewsCommand(PublicCommand):
    """Command to generate breaking news from recent messages."""
    
    def __init__(self):
        super().__init__(
            name="breaking-news",
            description="Generate a breaking news bulletin from recent channel activity",
            cooldown_seconds=30  # Higher cooldown for AI operations
        )
    
    def define_parameters(self) -> Dict[str, Dict[str, Any]]:
        """Define command parameters for Discord slash command."""
        return {
            "message_count": {
                "type": int,
                "description": "Number of recent messages to analyze for breaking news (10-100)",
                "required": False,
                "default": 50,
                "min_value": 10,
                "max_value": 100
            },
            "time_window": {
                "type": int,
                "description": "Hours of message history to analyze (1-24)",
                "required": False,
                "default": 2,
                "min_value": 1,
                "max_value": 24
            }
        }
    
    async def validate_arguments(self, ctx: CommandContext, **kwargs) -> Dict[str, Any]:
        """Validate command arguments."""
        validated = {}
        
        # Message count (optional)
        message_count = kwargs.get('message_count', 50)
        if not isinstance(message_count, int) or message_count < 10 or message_count > 100:
            message_count = 50
        validated['message_count'] = message_count
        
        # Time window in hours (optional)
        time_window = kwargs.get('time_window', 2)
        if not isinstance(time_window, int) or time_window < 1 or time_window > 24:
            time_window = 2
        validated['time_window'] = time_window
        
        return validated
    
    async def execute(self, ctx: CommandContext, message_count: int = 50, time_window: int = 2) -> None:
        """Execute the breaking news command."""
        
        logger.info(
            "Breaking news command executed",
            user_id=ctx.user_id,
            guild_id=ctx.guild_id,
            channel_id=ctx.channel_id,
            message_count=message_count,
            time_window=time_window
        )
        
        # Defer response since AI processing takes time
        await ctx.defer()
        
        try:
            # Get recent messages directly from Discord channel
            cutoff_time = datetime.now() - timedelta(hours=time_window)
            channel = ctx.interaction.client.get_channel(int(ctx.channel_id))
            if not channel:
                embed = EmbedBuilder.error(
                    "Channel Error",
                    "Could not access the current channel."
                )
                await ctx.respond(embed=embed)
                return
            
            # Fetch recent messages from the channel
            messages = []
            async for message in channel.history(limit=message_count, after=cutoff_time):
                if not message.author.bot and message.content.strip():
                    messages.append(message)
            
            if len(messages) < 5:
                embed = EmbedBuilder.warning(
                    "Insufficient Activity",
                    f"Not enough recent messages ({len(messages)}) to generate breaking news. "
                    f"Try again when there's more activity or increase the time window."
                )
                await ctx.respond(embed=embed)
                return
            
            # Filter out very short messages (bot messages already filtered)
            filtered_messages = [
                msg for msg in messages 
                if len(msg.content.strip()) > 10
            ]
            
            if len(filtered_messages) < 3:
                embed = EmbedBuilder.warning(
                    "Insufficient Content",
                    "Not enough meaningful messages to generate breaking news. "
                    "Try again when there's more discussion."
                )
                await ctx.respond(embed=embed)
                return
            
            # Get AI service for processing
            try:
                from src.ai import get_ai_service
                ai_service = await get_ai_service()
                
                # Use mock responses if enabled in settings
                if ctx.settings.mock_ai_responses:
                    bulletin = await self._generate_mock_bulletin(filtered_messages, ctx)
                else:
                    # Generate smart breaking news using AI service
                    bulletin = await ai_service.generate_smart_breaking_news(
                        messages=filtered_messages,
                        persona=ctx.server_config.persona,
                        server_id=ctx.guild_id,
                        channel_context=f"#{ctx.channel.name} recent activity"
                    )
                    
            except Exception as ai_error:
                logger.warning(f"AI service failed, falling back to mock: {ai_error}")
                # Fallback to mock if AI service fails
                bulletin = await self._generate_mock_bulletin(filtered_messages, ctx)
            
            # Create breaking news embed
            embed = EmbedBuilder.newsletter(
                title="🚨 BREAKING NEWS",
                content=bulletin,
                author_name=f"The Snitch • {ctx.server_config.persona.value.replace('_', ' ').title()}"
            )
            
            # Add footer with analysis info
            embed.add_field(
                name="Analysis Details",
                value=f"📊 {len(filtered_messages)} messages analyzed from last {time_window}h",
                inline=False
            )
            
            # Add reaction to the command message for engagement
            try:
                await ctx.interaction.message.add_reaction("📰")
            except:
                pass  # Ignore if we can't add reaction
            
            await ctx.respond(embed=embed)
            
            logger.info(
                "Breaking news generated successfully",
                user_id=ctx.user_id,
                guild_id=ctx.guild_id,
                channel_id=ctx.channel_id,
                messages_analyzed=len(filtered_messages),
                bulletin_length=len(bulletin)
            )
            
        except InsufficientContentError as e:
            embed = EmbedBuilder.warning("Insufficient Content", str(e))
            await ctx.respond(embed=embed)
            
        except AIServiceError as e:
            embed = EmbedBuilder.error("AI Service Error", "Failed to generate breaking news. Please try again later.")
            await ctx.respond(embed=embed)
            logger.error(f"AI service error in breaking news: {e}")
            
        except Exception as e:
            embed = EmbedBuilder.error("Command Failed", "An unexpected error occurred while generating breaking news.")
            await ctx.respond(embed=embed)
            logger.error(f"Unexpected error in breaking news command: {e}", exc_info=True)
    
    async def _generate_mock_bulletin(self, messages, ctx: CommandContext) -> str:
        """Generate mock breaking news bulletin for testing."""
        
        # Simple mock implementation
        total_messages = len(messages)
        unique_users = len(set(str(msg.author.id) for msg in messages))
        
        # Find most active topic (simple keyword analysis)
        word_counts = {}
        for msg in messages:
            words = msg.content.lower().split()
            for word in words:
                if len(word) > 4 and word.isalpha():  # Filter out short words and non-alphabetic
                    word_counts[word] = word_counts.get(word, 0) + 1
        
        top_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        
        # Get most engaging message (by length as proxy for controversy)
        most_controversial = max(messages, key=lambda x: len(x.content)) if messages else None
        
        # Generate mock bulletin based on persona
        persona = ctx.server_config.persona
        
        if persona == "sassy_reporter":
            bulletin = f"**BREAKING:** Drama alert in #{ctx.channel.name}! 🍵\n\n"
            bulletin += f"Our sources report {unique_users} users have been going OFF about "
            if top_words:
                bulletin += f"'{top_words[0][0]}' "
            bulletin += f"with a whopping {total_messages} messages in the last few hours.\n\n"
            
            if most_controversial and most_controversial.controversy_score > 0.3:
                bulletin += f"The tea is particularly hot with one user dropping this bombshell: "
                bulletin += f'"{most_controversial.content[:100]}..."\n\n'
            
            bulletin += "Stay tuned for more chaos! 💅"
            
        elif persona == "investigative_journalist":
            bulletin = f"**DEVELOPING STORY:** Significant Activity Detected in #{ctx.channel.name}\n\n"
            bulletin += f"Following extensive analysis of {total_messages} messages from {unique_users} participants, "
            bulletin += "patterns indicate heightened discussion around "
            if top_words:
                bulletin += f"'{top_words[0][0]}' "
            bulletin += "with multiple engagement indicators.\n\n"
            
            if most_controversial and most_controversial.controversy_score > 0.3:
                bulletin += f"Key statement under scrutiny: \"{most_controversial.content[:100]}...\"\n\n"
            
            bulletin += "Investigation ongoing. More details as they develop."
            
        elif persona == "sports_commentator":
            bulletin = f"**AND IT'S HAPPENING LIVE IN #{ctx.channel.name.upper()}!** 🏟️\n\n"
            bulletin += f"We've got {unique_users} players on the field with {total_messages} plays called! "
            bulletin += "The crowd is going WILD! \n\n"
            
            if top_words:
                bulletin += f"The hot topic? '{top_words[0][0].upper()}'! "
            
            if most_controversial and most_controversial.controversy_score > 0.3:
                bulletin += f"OH MY! One player just dropped this MASSIVE play: "
                bulletin += f'"{most_controversial.content[:100]}..."\n\n'
            
            bulletin += "THIS IS WHAT WE LIVE FOR, FOLKS!"
            
        else:  # Default/other personas
            bulletin = f"**BREAKING NEWS from #{ctx.channel.name}**\n\n"
            bulletin += f"Activity surge detected: {total_messages} messages from {unique_users} users. "
            
            if top_words:
                bulletin += f"Primary discussion topic: '{top_words[0][0]}'. "
            
            if most_controversial and most_controversial.controversy_score > 0.3:
                bulletin += f"\n\nHighlighted message: \"{most_controversial.content[:100]}...\""
            
            bulletin += "\n\nStay informed with The Snitch!"
        
        return bulletin


# Register the command
from src.discord_bot.commands.base import command_registry
command_registry.register(BreakingNewsCommand())