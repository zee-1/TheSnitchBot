"""
Controversy check command for The Snitch Discord Bot.
Analyzes how controversial a message is using AI.
"""

from typing import Dict, Any
from datetime import datetime
import discord

from src.discord_bot.commands.base import PublicCommand, CommandContext, EmbedBuilder
from src.core.exceptions import ValidationError, AIServiceError
from src.core.logging import get_logger
from src.utils.validation import validate_discord_id
from src.models.message import Message

logger = get_logger(__name__)


class ControversyCheckCommand(PublicCommand):
    """Command for checking how controversial a message is."""
    
    def __init__(self):
        super().__init__(
            name="controversy-check",
            description="Check how controversial a message is using AI analysis",
            cooldown_seconds=20  # Moderate cooldown for AI operations
        )
    
    def define_parameters(self) -> Dict[str, Dict[str, Any]]:
        """Define command parameters for Discord slash command."""
        return {
            "message_id": {
                "type": str,
                "description": "Message ID (or right-click on message and use Apps > controversy-check)",
                "required": False,
                "default": None
            }
        }
    
    async def execute(self, ctx: CommandContext, message_id: str = None) -> None:
        """Execute the controversy check command."""
        
        # Handle different ways the command can be used
        target_message_id = None
        
        # Method 1: Check if this command was used as a reply to another message (RECOMMENDED)
        if ctx.interaction.message and ctx.interaction.message.reference and ctx.interaction.message.reference.message_id:
            target_message_id = str(ctx.interaction.message.reference.message_id)
            
        # Method 2: Check if it's a context menu command (right-click Apps)
        elif hasattr(ctx.interaction, 'data') and ctx.interaction.data.get('resolved', {}).get('messages'):
            resolved_messages = ctx.interaction.data['resolved']['messages']
            target_message_id = list(resolved_messages.keys())[0]
            
        # Method 3: Check if message_id parameter was provided (fallback)
        elif message_id:
            target_message_id = message_id
            
        # Method 4: No message specified - show help
        else:
            embed = EmbedBuilder.warning(
                "How to Use Controversy Check",
                "🤔 **You need to specify which message to analyze!**\n\n"
                "**Option 1 (Recommended):**\n"
                "Reply to any message and use `/content controversy-check`\n\n"
                "**Option 2:**\n"
                "Right-click on any message → **Apps** → **controversy-check**\n\n"
                "**Option 3 (Fallback):**\n"
                "Use `/content controversy-check message_id:[paste ID]`\n\n"
                "💡 **Pro tip:** Just reply to the message you want to analyze!"
            )
            await ctx.respond(embed=embed, ephemeral=True)
            return
        
        logger.info(
            "Controversy check command executed",
            extra={
                "user_id": ctx.user_id,
                "guild_id": ctx.guild_id,
                "channel_id": ctx.channel_id,
                "target_message_id": target_message_id
            }
        )
        
        try:
            # Get the target message directly from Discord
            channel = ctx.interaction.client.get_channel(int(ctx.channel_id))
            if not channel:
                embed = EmbedBuilder.error(
                    "Channel Error",
                    "Could not access the current channel."
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return
                
            try:
                target_message = await channel.fetch_message(int(target_message_id))
            except discord.NotFound:
                embed = EmbedBuilder.warning(
                    "Message Not Found",
                    f"Could not find the target message in this channel."
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return
            
            # Don't analyze bot messages or empty messages
            if target_message.author.bot or str(target_message.author.id) == str(ctx.interaction.client.user.id):
                embed = EmbedBuilder.warning(
                    "Cannot Analyze Bot Messages",
                    "I don't analyze bot messages. That would be weird. 🤖"
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return
            
            if not target_message.content.strip():
                embed = EmbedBuilder.warning(
                    "Empty Message",
                    "Cannot analyze empty messages or media-only messages."
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return
            
            # Defer response since AI processing takes time
            await ctx.defer()
            
            # Create Message object for AI analysis using the proper conversion method
            message_obj = Message.from_discord_message(target_message, str(target_message.guild.id))
            
            # Get recent context messages for better analysis
            context_messages = []
            try:
                async for msg in channel.history(limit=5, before=target_message, oldest_first=False):
                    if not msg.author.bot and msg.content.strip():
                        context_msg = Message.from_discord_message(msg, str(msg.guild.id))
                        context_messages.append(context_msg)
            except:
                # If we can't get context, continue without it
                pass
            
            # Get AI service for analysis
            try:
                from src.ai import get_ai_service
                ai_service = await get_ai_service()
                
                # Use mock responses if enabled in settings
                settings = ctx.container.get_settings()
                if settings.mock_ai_responses:
                    analysis = await self._generate_mock_analysis(message_obj, context_messages, ctx)
                else:
                    # Analyze message controversy using AI service
                    analysis = await ai_service.analyze_message_controversy(
                        message=message_obj,
                        context_messages=context_messages
                    )
                    
            except Exception as ai_error:
                logger.warning(f"AI service failed, falling back to mock: {ai_error}")
                # Fallback to mock if AI service fails
                analysis = await self._generate_mock_analysis(message_obj, context_messages, ctx)
            
            # Create analysis embed
            controversy_score = analysis.get("controversy_score", 0.0)
            confidence = analysis.get("confidence", 0.0)
            
            # Determine controversy level and color
            if controversy_score >= 0.8:
                level = "🔥 EXTREMELY CONTROVERSIAL"
                color = discord.Color.red()
            elif controversy_score >= 0.6:
                level = "⚠️ HIGHLY CONTROVERSIAL"
                color = discord.Color.orange()
            elif controversy_score >= 0.4:
                level = "📢 MODERATELY CONTROVERSIAL"
                color = discord.Color.yellow()
            elif controversy_score >= 0.2:
                level = "💬 SLIGHTLY CONTROVERSIAL"
                color = discord.Color.blue()
            else:
                level = "😴 NOT CONTROVERSIAL"
                color = discord.Color.green()
            
            embed = discord.Embed(
                title="🔍 Controversy Analysis",
                description=f"Analysis of message from {target_message.author.mention}",
                color=color,
                timestamp=datetime.now()
            )
            
            # Add message preview
            message_preview = target_message.content[:200]
            if len(target_message.content) > 200:
                message_preview += "..."
            
            embed.add_field(
                name="📝 Message Preview",
                value=f"```{message_preview}```",
                inline=False
            )
            
            # Add controversy metrics
            embed.add_field(
                name="🎯 Controversy Level",
                value=level,
                inline=True
            )
            
            embed.add_field(
                name="📊 Controversy Score",
                value=f"{controversy_score:.1%}",
                inline=True
            )
            
            embed.add_field(
                name="🎲 Confidence",
                value=f"{confidence:.1%}",
                inline=True
            )
            
            # Add analysis details if available
            reasons = analysis.get("reasons", [])
            if reasons:
                embed.add_field(
                    name="🔍 Analysis Factors",
                    value="\n".join([f"• {reason}" for reason in reasons[:3]]),
                    inline=False
                )
            
            # Add context info
            context_info = []
            if analysis.get("related_messages_count", 0) > 0:
                context_info.append(f"📚 {analysis['related_messages_count']} related messages found")
            if len(context_messages) > 0:
                context_info.append(f"💬 {len(context_messages)} context messages analyzed")
            
            if context_info:
                embed.add_field(
                    name="🔗 Context Analysis",
                    value="\n".join(context_info),
                    inline=False
                )
            
            # Add disclaimer
            embed.add_field(
                name="⚠️ Disclaimer",
                value="This analysis is for entertainment purposes only and should not be used for moderation decisions.",
                inline=False
            )
            
            # Set footer with persona (with fallback)
            try:
                persona_name = ctx.server_config.persona.replace('_', ' ').title() if ctx.server_config and ctx.server_config.persona else "Sassy Reporter"
                embed.set_footer(text=f"Analyzed by {persona_name}")
            except AttributeError:
                embed.set_footer(text="Analyzed by Sassy Reporter")
            
            await ctx.respond(embed=embed)
            
            # Log analysis completion
            logger.info(
                "Controversy analysis completed",
                extra={
                    "user_id": ctx.user_id,
                    "guild_id": ctx.guild_id,
                    "target_message_id": target_message_id,
                    "controversy_score": controversy_score,
                    "confidence": confidence,
                    "context_messages": len(context_messages)
                }
            )
            
        except ValidationError as e:
            embed = EmbedBuilder.error(
                "Validation Error",
                f"Invalid message ID: {str(e)}"
            )
            await ctx.respond(embed=embed, ephemeral=True)
            
        except AIServiceError as e:
            embed = EmbedBuilder.error(
                "Analysis Failed",
                "AI service is currently unavailable. Please try again later."
            )
            await ctx.respond(embed=embed, ephemeral=True)
            logger.error(f"AI service error in controversy check: {e}")
            
        except Exception as e:
            embed = EmbedBuilder.error(
                "Command Failed",
                "An unexpected error occurred while analyzing the message."
            )
            await ctx.respond(embed=embed, ephemeral=True)
            logger.error(f"Unexpected error in controversy check: {e}", exc_info=True)
    
    async def _generate_mock_analysis(self, message: Message, context_messages: list, ctx: CommandContext) -> Dict[str, Any]:
        """Generate mock controversy analysis for testing."""
        import random
        
        # Simple controversy heuristics for mock analysis
        content = message.content.lower()
        
        # Basic controversy indicators
        controversy_keywords = [
            'disagree', 'wrong', 'terrible', 'awful', 'hate', 'stupid', 'dumb',
            'politics', 'religion', 'debate', 'argue', 'fight', 'drama', 'toxic',
            'ban', 'report', 'mute', 'kick', 'controversy', 'problematic'
        ]
        
        # Calculate base score from keywords
        keyword_matches = sum(1 for keyword in controversy_keywords if keyword in content)
        base_score = min(keyword_matches * 0.15, 0.7)
        
        # Add randomness and message length factor
        length_factor = min(len(content) / 500, 0.3)  # Longer messages slightly more controversial
        excitement_factor = content.count('!') * 0.05  # Exclamation marks add controversy
        caps_factor = sum(1 for c in content if c.isupper()) / max(len(content), 1) * 0.2  # CAPS
        
        controversy_score = min(base_score + length_factor + excitement_factor + caps_factor + random.uniform(0, 0.2), 1.0)
        confidence = random.uniform(0.6, 0.9)
        
        # Generate reasons based on content analysis
        reasons = []
        if keyword_matches > 0:
            reasons.append(f"Contains {keyword_matches} potentially controversial keyword(s)")
        if caps_factor > 0.1:
            reasons.append("Excessive use of capital letters detected")
        if excitement_factor > 0.1:
            reasons.append("High emotional intensity (multiple exclamation marks)")
        if length_factor > 0.2:
            reasons.append("Long message with potential for complex discussion")
        if len(context_messages) > 2:
            reasons.append("Part of an ongoing conversation thread")
        
        # Add persona-specific analysis flavor
        persona = ctx.server_config.persona
        if persona == "sassy_reporter":
            if controversy_score > 0.5:
                reasons.append("The tea is HOT on this one! ☕")
            else:
                reasons.append("Pretty tame tbh, not much drama here")
        elif persona == "conspiracy_theorist":
            reasons.append("There are deeper layers to analyze here...")
            if random.random() > 0.5:
                reasons.append("Suspiciously innocent... or IS it?")
        elif persona == "investigative_journalist":
            reasons.append("Thorough analysis of linguistic patterns completed")
            if controversy_score > 0.3:
                reasons.append("Requires further investigation for full context")
        
        if not reasons:
            reasons = ["Standard message analysis completed", "No significant controversy indicators found"]
        
        return {
            "controversy_score": controversy_score,
            "confidence": confidence,
            "reasons": reasons,
            "related_messages_count": len(context_messages),
            "analysis_method": "mock_heuristic"
        }


# Context menu command for right-click controversy check
import discord
from discord import app_commands

@app_commands.context_menu(name='Controversy Check')
async def controversy_check_context_menu(interaction: discord.Interaction, message: discord.Message):
    """Context menu command for checking message controversy."""
    # Import here to avoid circular imports
    from src.core.dependencies import get_container
    from src.discord_bot.commands.base import CommandContext
    
    # Create a context object similar to slash commands
    container = await get_container()
    server_repo = container.get_server_repository()
    
    # Try to get server config using partition method first
    try:
        server_config = await server_repo.get_by_server_id_partition(str(interaction.guild_id))
        if not server_config:
            # Fallback to regular method
            server_config = await server_repo.get_by_server_id(str(interaction.guild_id))
    except Exception:
        server_config = await server_repo.get_by_server_id(str(interaction.guild_id))
    
    # If still no config, create a default one
    if not server_config:
        from src.models.server import PersonaType, ServerStatus
        # Create minimal server config for the command to work
        server_config = type('ServerConfig', (), {
            'persona': PersonaType.SASSY_REPORTER,
            'status': ServerStatus.ACTIVE,
            'server_id': str(interaction.guild_id),
            'server_name': interaction.guild.name if interaction.guild else 'Unknown Server'
        })()
    
    # Create context
    ctx = CommandContext(
        interaction=interaction,
        container=container,
        server_config=server_config
    )
    
    # Create controversy check command instance and execute
    controversy_cmd = ControversyCheckCommand()
    
    # Use the target message ID from the context menu
    await controversy_cmd.execute(ctx, message_id=str(message.id))


# Register the command
from src.discord_bot.commands.base import command_registry
command_registry.register(ControversyCheckCommand())