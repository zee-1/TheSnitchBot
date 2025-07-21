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
from src.models.message import Message

logger = get_logger(__name__)

MIN_MESSAGE = 10
MAX_MESSAGE = 10000
MIN_HRS = 1
MAX_HRS = 48
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
                "description": f"Number of recent messages to analyze for breaking news ({MIN_MESSAGE}-{MAX_MESSAGE})",
                "required": False,
                "default": 50,
                "min_value": MIN_MESSAGE,
                "max_value": MAX_MESSAGE
            },
            "time_window": {
                "type": int,
                "description": f"Hours of message history to analyze ({MIN_HRS}-{MAX_HRS})",
                "required": False,
                "default": 2,
                "min_value": MIN_HRS,
                "max_value": MAX_HRS
            }
        }
    
    async def validate_arguments(self, ctx: CommandContext, **kwargs) -> Dict[str, Any]:
        """Validate command arguments."""
        validated = {}
        
        # Message count (optional)
        message_count = kwargs.get('message_count', 50)
        if not isinstance(message_count, int) or message_count < MIN_MESSAGE or message_count > MAX_HRS:
            message_count = 50
        validated['message_count'] = message_count
        
        # Time window in hours (optional)
        time_window = kwargs.get('time_window', 2)
        if not isinstance(time_window, int) or time_window < MIN_HRS or time_window > MAX_HRS:
            time_window = 2
        validated['time_window'] = time_window
        
        return validated
    
    async def _convert_discord_messages_to_message_models(
        self, 
        discord_messages: list, 
        server_id: str
    ) -> list[Message]:
        """
        Convert Discord message objects to our Message model instances.
        
        Args:
            discord_messages: List of discord.Message objects
            server_id: Discord server/guild ID
            
        Returns:
            List of Message model instances
        """
        message_models = []
        
        for discord_msg in discord_messages:
            try:
                # Convert using the Message model's built-in method
                message_model = Message.from_discord_message(discord_msg, server_id)
                
                # Populate reaction users properly (async operation)
                for reaction_data in message_model.reactions:
                    try:
                        # Find the original reaction and get users
                        discord_reaction = next(
                            (r for r in discord_msg.reactions if str(r.emoji) == reaction_data.emoji), 
                            None
                        )
                        if discord_reaction:
                            users = []
                            async for user in discord_reaction.users():
                                users.append(str(user.id))
                            reaction_data.users = users
                            reaction_data.count = len(users)
                    except Exception as e:
                        logger.warning(f"Failed to populate reaction users for {reaction_data.emoji}: {e}")
                
                # Update calculated metrics
                message_model.update_metrics()
                message_models.append(message_model)
                
            except Exception as e:
                logger.warning(f"Failed to convert Discord message {discord_msg.id}: {e}")
                continue
        
        return message_models
    
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
            filtered_discord_messages = [
                msg for msg in messages 
                if len(msg.content.strip()) > 10
            ]
            
            if len(filtered_discord_messages) < 3:
                embed = EmbedBuilder.warning(
                    "Insufficient Content",
                    "Not enough meaningful messages to generate breaking news. "
                    "Try again when there's more discussion."
                )
                await ctx.respond(embed=embed)
                return
            
            # Convert Discord messages to our Message model instances
            filtered_messages = await self._convert_discord_messages_to_message_models(
                filtered_discord_messages, 
                ctx.guild_id
            )
            
            if len(filtered_messages) < 3:
                embed = EmbedBuilder.warning(
                    "Conversion Error",
                    "Failed to process enough messages for breaking news generation. "
                    "Try again later."
                )
                await ctx.respond(embed=embed)
                return
            
            # Get AI service for processing
            try:
                from src.ai import get_ai_service
                ai_service = await get_ai_service()
                # Use mock responses if enabled in settings
                settings = ctx.container.get_settings()
                if settings.mock_ai_responses:
                    bulletin = await self._generate_mock_bulletin(filtered_discord_messages, ctx)
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
                bulletin = await self._generate_mock_bulletin(filtered_discord_messages, ctx)
            
            # Create breaking news embed
            embed = EmbedBuilder.newsletter(
                title="🚨 BREAKING NEWS",
                content=bulletin,
                author_name=f"The Snitch • {ctx.server_config.persona.replace('_', ' ').title()}"
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
            
            # Send to configured output channel or current channel
            from src.discord_bot.utils.channel_utils import send_to_output_channel
            await send_to_output_channel(
                ctx, 
                embed, 
                "Breaking news bulletin sent"
            )
            
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
            
            if most_controversial and len(most_controversial.content) > MAX_MESSAGE:
                bulletin += f"The tea is particularly hot with one user dropping this bombshell: "
                bulletin += f'"{most_controversial.content[:MAX_MESSAGE]}..."\n\n'
            
            bulletin += "Stay tuned for more chaos! 💅"
            
        elif persona == "investigative_journalist":
            bulletin = f"**DEVELOPING STORY:** Significant Activity Detected in #{ctx.channel.name}\n\n"
            bulletin += f"Following extensive analysis of {total_messages} messages from {unique_users} participants, "
            bulletin += "patterns indicate heightened discussion around "
            if top_words:
                bulletin += f"'{top_words[0][0]}' "
            bulletin += "with multiple engagement indicators.\n\n"
            
            if most_controversial and len(most_controversial.content) > MAX_MESSAGE:
                bulletin += f"Key statement under scrutiny: \"{most_controversial.content[:MAX_MESSAGE]}...\"\n\n"
            
            bulletin += "Investigation ongoing. More details as they develop."
            
        elif persona == "sports_commentator":
            bulletin = f"**AND IT'S HAPPENING LIVE IN #{ctx.channel.name.upper()}!** 🏟️\n\n"
            bulletin += f"We've got {unique_users} players on the field with {total_messages} plays called! "
            bulletin += "The crowd is going WILD! \n\n"
            
            if top_words:
                bulletin += f"The hot topic? '{top_words[0][0].upper()}'! "
            
            if most_controversial and len(most_controversial.content) > MAX_MESSAGE:
                bulletin += f"OH MY! One player just dropped this MASSIVE play: "
                bulletin += f'"{most_controversial.content[:MAX_MESSAGE]}..."\n\n'
            
            bulletin += "THIS IS WHAT WE LIVE FOR, FOLKS!"
            
        else:  # Default/other personas
            bulletin = f"**BREAKING NEWS from #{ctx.channel.name}**\n\n"
            bulletin += f"Activity surge detected: {total_messages} messages from {unique_users} users. "
            
            if top_words:
                bulletin += f"Primary discussion topic: '{top_words[0][0]}'. "
            
            if most_controversial and len(most_controversial.content) > MAX_MESSAGE:
                bulletin += f"\n\nHighlighted message: \"{most_controversial.content[:MAX_MESSAGE]}...\""
            
            bulletin += "\n\nStay informed with The Snitch!"
        
        return bulletin


# Command is now handled by /content breaking-news app command
# No need to register in old command registry