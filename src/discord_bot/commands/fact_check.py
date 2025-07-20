"""
Fact check command for The Snitch Discord Bot.
Provides humorous, non-authoritative verdicts on messages.
"""

import discord
from typing import Dict, Any
import random
from datetime import datetime

from src.discord_bot.commands.base import PublicCommand, CommandContext, EmbedBuilder
from src.core.exceptions import InvalidCommandArgumentError
from src.core.logging import get_logger
from src.utils.validation import validate_discord_id

logger = get_logger(__name__)


class FactCheckCommand(PublicCommand):
    """Command to fact-check messages with humorous verdicts."""
    
    def __init__(self):
        super().__init__(
            name="fact-check",
            description="Fact-check a message with a humorous verdict",
            cooldown_seconds=15  # Moderate cooldown
        )
    
    def define_parameters(self) -> Dict[str, Dict[str, Any]]:
        """Define command parameters for Discord slash command."""
        return {
            "message_id": {
                "type": str,
                "description": "Message ID (or right-click on message and use Apps > fact-check)",
                "required": False,
                "default": None
            }
        }
    
    async def validate_arguments(self, ctx: CommandContext, **kwargs) -> Dict[str, Any]:
        """Validate command arguments."""
        validated = {}
        
        # Message ID is required
        message_id = kwargs.get('message_id')
        if not message_id:
            raise InvalidCommandArgumentError(
                self.name, 
                'message_id', 
                'Message ID is required'
            )
        
        # Validate Discord ID format
        try:
            validated['message_id'] = validate_discord_id(message_id, 'message_id')
        except Exception as e:
            raise InvalidCommandArgumentError(
                self.name,
                'message_id',
                f'Invalid message ID format: {e}'
            )
        
        return validated
    
    async def execute(self, ctx: CommandContext, message_id: str = None) -> None:
        """Execute the fact-check command."""
        
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
                "How to Use Fact-Check",
                "🤔 **You need to specify which message to fact-check!**\n\n"
                "**Option 1 (Recommended):**\n"
                "Reply to any message and use `/content fact-check`\n\n"
                "**Option 2:**\n"
                "Right-click on any message → **Apps** → **fact-check**\n\n"
                "**Option 3 (Fallback):**\n"
                "Use `/content fact-check message_id:[paste ID]`\n\n"
                "💡 **Pro tip:** Just reply to the message you want to fact-check!"
            )
            await ctx.respond(embed=embed, ephemeral=True)
            return
        
        logger.info(
            "Fact-check command executed",
            user_id=ctx.user_id,
            guild_id=ctx.guild_id,
            channel_id=ctx.channel_id,
            target_message_id=target_message_id
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
            
            # Don't fact-check bot messages
            if target_message.author.bot or str(target_message.author.id) == str(ctx.interaction.client.user.id):
                embed = EmbedBuilder.warning(
                    "Cannot Fact-Check Bot",
                    "I don't fact-check my own messages. That would be weird. 🤖"
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return
            
            # Don't fact-check empty messages
            if not target_message.content.strip():
                embed = EmbedBuilder.warning(
                    "No Content",
                    "Can't fact-check a message with no text content."
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return
            
            # Generate fact-check verdict
            import traceback

            try:
                settings = ctx.container.get_settings()
                if settings.mock_ai_responses:
                    verdict = await self._generate_mock_verdict(target_message, ctx)
                else:
                    # Use AI service for fact checking
                    from src.ai import get_ai_service
                    ai_service = await get_ai_service()
                    
                    # Analyze the message content for fact-checking
                    # Fetch persona from database using container if ctx.server_config is None
                    persona_name = "sassy_reporter"  # Default fallback
                    if ctx.server_config and ctx.server_config.persona:
                        persona_name = ctx.server_config.persona
                    else:
                        
                        # Try to get server config from database
                        try:
                            server_repo = ctx.container.get_server_repository()
                            server_config = await server_repo.get_by_server_id_partition(str(ctx.guild_id))
                            if not server_config:
                                server_config = await server_repo.get_by_server_id(str(ctx.guild_id))
                            
                            if server_config and server_config.persona:
                                persona_name = server_config.persona
                        except Exception as e:
                            logger.warning(f"Failed to fetch server config for persona: {e}")
                    
                    analysis = await ai_service.groq_client.analyze_content(
                        content=target_message.content,
                        analysis_type="fact_check",
                        context=f"Discord message fact-check with {persona_name} persona"
                    )
                    
                    # Convert AI response to verdict format
                    verdict = await self._convert_ai_response_to_verdict(analysis, ctx)
                    
            except Exception as ai_error:
                print(repr(traceback.format_exception(ai_error)))
                logger.warning(f"AI fact-check failed, falling back to mock: {ai_error}")
                # Fallback to mock if AI service fails
                verdict = await self._generate_mock_verdict(target_message, ctx)
            
            # Create fact-check response
            embed = self._create_verdict_embed(target_message, verdict, ctx)
            
            await ctx.respond(embed=embed)
            
            # Add reaction to original message
            try:
                emoji = verdict['emoji']
                await target_message.add_reaction(emoji)
            except Exception as e:
                logger.warning(f"Failed to add reaction to message {target_message_id}: {e}")
            
            logger.info(
                "Fact-check completed",
                user_id=ctx.user_id,
                guild_id=ctx.guild_id,
                target_message_id=target_message_id,
                verdict=verdict['category']
            )
            
        except Exception as e:
            embed = EmbedBuilder.error(
                "Fact-Check Failed",
                "An error occurred while fact-checking the message."
            )
            await ctx.respond(embed=embed)
            logger.error(f"Error in fact-check command: {e}", exc_info=True)
    
    async def _convert_ai_response_to_verdict(self, analysis: str, ctx: CommandContext) -> Dict[str, Any]:
        """Convert AI analysis response to verdict format."""
        
        # Parse AI response for verdict category
        analysis_lower = analysis.get('fact-check','false').lower().strip()
        
        # Determine category based on AI response
        if "true" in analysis_lower and "false" not in analysis_lower:
            category = "true"
        elif "false" in analysis_lower and "true" not in analysis_lower:
            category = "false"  
        elif "needs investigation" in analysis_lower or "investigation" in analysis_lower:
            category = "needs_investigation"
        else:
            # Default to needs investigation if unclear
            category = "needs_investigation"
        
        # Get persona-specific response using the same format as mock
        # Fetch persona from database using container if ctx.server_config is None
        persona = "sassy_reporter"  # Default fallback
        if ctx.server_config and ctx.server_config.persona:
            persona = ctx.server_config.persona
        else:
            # Try to get server config from database
            try:
                server_repo = ctx.container.get_server_repository()
                server_config = await server_repo.get_by_server_id_partition(str(ctx.guild_id))
                if not server_config:
                    server_config = await server_repo.get_by_server_id(str(ctx.guild_id))
                
                if server_config and server_config.persona:
                    persona = server_config.persona
            except Exception as e:
                logger.warning(f"Failed to fetch server config for persona: {e}")
        
        # Define verdict structure (same as mock)
        verdicts = {
            'true': {
                'emoji': '✅',
                'title': 'TRUE',
                'color': discord.Color.green(),
                'responses': {
                    'sassy_reporter': [
                        "Okay, I'll give you this one. ✅",
                        "Finally, someone who knows what they're talking about!",
                        "Breaking: User actually tells the truth! More at 11."
                    ],
                    'investigative_journalist': [
                        "After careful analysis, this statement appears factual.",
                        "Cross-referencing sources... verdict: CONFIRMED ✅",
                        "Investigation concludes: Statement verified."
                    ],
                    'sports_commentator': [
                        "GOAL! That's a solid fact right there! ⚽",
                        "AND IT'S GOOD! Facts don't lie!",
                        "What a play! Truth wins the day!"
                    ],
                    'default': [
                        "This appears to be accurate! ✅",
                        "Fact-check verdict: TRUE",
                        "Confirmed: This checks out!"
                    ]
                }
            },
            'false': {
                'emoji': '❌', 
                'title': 'FALSE',
                'color': discord.Color.red(),
                'responses': {
                    'sassy_reporter': [
                        "Honey, no. Just... no. ❌",
                        "This is more cap than a baseball game! 🧢",
                        "Breaking: Local user spreads misinformation. Shocking!"
                    ],
                    'investigative_journalist': [
                        "Extensive fact-checking reveals this to be FALSE.",
                        "Investigation determines: Statement inaccurate.",
                        "Evidence overwhelmingly refutes this assertion."
                    ],
                    'sports_commentator': [
                        "FUMBLE! That statement didn't make it to the end zone!",
                        "STRIKE THREE! That claim is OUT!",
                        "PENALTY FLAG! False statement, 15 yard penalty!"
                    ],
                    'default': [
                        "This statement appears to be false. ❌",
                        "Fact-check verdict: FALSE",
                        "Disputed: This doesn't check out."
                    ]
                }
            },
            'needs_investigation': {
                'emoji': '🔍',
                'title': 'NEEDS INVESTIGATION', 
                'color': discord.Color.orange(),
                'responses': {
                    'sassy_reporter': [
                        "Hmm, this one's sus. Need to dig deeper. 🔍",
                        "The jury's still out on this tea... ☕",
                        "This needs more investigation than my dating life."
                    ],
                    'investigative_journalist': [
                        "Insufficient evidence to make a determination. 🔍",
                        "This claim requires further investigation.",
                        "Investigation ongoing. Verdict pending."
                    ],
                    'sports_commentator': [
                        "WE'RE GOING TO THE REPLAY BOOTH ON THIS ONE! 📹",
                        "UNDER REVIEW! The facts are still being examined!",
                        "TIME OUT! Need to check the playbook on this one!"
                    ],
                    'default': [
                        "This requires further investigation. 🔍",
                        "Fact-check verdict: NEEDS MORE INFO",
                        "Status: Under review."
                    ]
                }
            }
        }
        
        verdict_info = verdicts[category]
        persona_responses = verdict_info['responses'].get(persona, verdict_info['responses']['default'])
        
        import random
        return {
            'category': category,
            'emoji': verdict_info['emoji'],
            'title': verdict_info['title'], 
            'color': verdict_info['color'],
            'response': random.choice(persona_responses)
        }
    
    async def _generate_mock_verdict(self, message, ctx: CommandContext) -> Dict[str, Any]:
        """Generate mock fact-check verdict for testing."""
        
        content = message.content.lower()
        
        # Simple keyword-based mock analysis
        true_keywords = ['yes', 'correct', 'right', 'true', 'definitely', 'absolutely']
        false_keywords = ['no', 'wrong', 'false', 'lie', 'fake', 'incorrect', 'never']
        uncertain_keywords = ['maybe', 'probably', 'might', 'could', 'possibly', 'perhaps']
        
        # Check for obvious patterns
        if any(keyword in content for keyword in false_keywords):
            category_weights = {'false': 0.6, 'needs_investigation': 0.3, 'true': 0.1}
        elif any(keyword in content for keyword in true_keywords):
            category_weights = {'true': 0.6, 'needs_investigation': 0.3, 'false': 0.1}
        elif any(keyword in content for keyword in uncertain_keywords):
            category_weights = {'needs_investigation': 0.7, 'true': 0.15, 'false': 0.15}
        else:
            # Random distribution for other content
            category_weights = {'true': 0.3, 'false': 0.35, 'needs_investigation': 0.35}
        
        # Weighted random selection
        import random
        rand = random.random()
        cumulative = 0
        
        for category, weight in category_weights.items():
            cumulative += weight
            if rand <= cumulative:
                selected_category = category
                break
        else:
            selected_category = 'needs_investigation'
        
        # Generate response based on category and persona
        # Fetch persona from database using container if ctx.server_config is None
        persona = "sassy_reporter"  # Default fallback
        if ctx.server_config and ctx.server_config.persona:
            persona = ctx.server_config.persona
        else:
            # Try to get server config from database
            try:
                server_repo = ctx.container.get_server_repository()
                server_config = await server_repo.get_by_server_id_partition(str(ctx.guild_id))
                if not server_config:
                    server_config = await server_repo.get_by_server_id(str(ctx.guild_id))
                
                if server_config and server_config.persona:
                    persona = server_config.persona
            except Exception as e:
                logger.warning(f"Failed to fetch server config for persona: {e}")
        
        verdicts = {
            'true': {
                'emoji': '✅',
                'title': 'TRUE',
                'color': discord.Color.green(),
                'responses': {
                    'sassy_reporter': [
                        "Okay, I'll give you this one. ✅",
                        "Shockingly, this checks out! 📰",
                        "Finally, someone who knows what they're talking about!",
                        "Breaking: User actually tells the truth! More at 11."
                    ],
                    'investigative_journalist': [
                        "After careful analysis, this statement appears factual.",
                        "Cross-referencing sources... verdict: CONFIRMED ✅",
                        "The evidence supports this claim.",
                        "Investigation concludes: Statement verified."
                    ],
                    'sports_commentator': [
                        "GOAL! That's a solid fact right there! ⚽",
                        "TOUCHDOWN! This statement scores big!",
                        "AND IT'S GOOD! Facts don't lie!",
                        "What a play! Truth wins the day!"
                    ],
                    'default': [
                        "This appears to be accurate! ✅",
                        "Fact-check verdict: TRUE",
                        "The evidence supports this statement.",
                        "Confirmed: This checks out!"
                    ]
                }
            },
            'false': {
                'emoji': '❌',
                'title': 'FALSE',
                'color': discord.Color.red(),
                'responses': {
                    'sassy_reporter': [
                        "Honey, no. Just... no. ❌",
                        "This is more cap than a baseball game! 🧢",
                        "Press X to doubt... actually, don't. It's clearly false.",
                        "Breaking: Local user spreads misinformation. Shocking!"
                    ],
                    'investigative_journalist': [
                        "Extensive fact-checking reveals this to be FALSE.",
                        "Multiple sources contradict this claim. ❌",
                        "Investigation determines: Statement inaccurate.",
                        "Evidence overwhelmingly refutes this assertion."
                    ],
                    'sports_commentator': [
                        "FUMBLE! That statement didn't make it to the end zone!",
                        "FOUL! False information on the field!",
                        "STRIKE THREE! That claim is OUT!",
                        "PENALTY FLAG! False statement, 15 yard penalty!"
                    ],
                    'default': [
                        "This statement appears to be false. ❌",
                        "Fact-check verdict: FALSE",
                        "The evidence contradicts this claim.",
                        "Disputed: This doesn't check out."
                    ]
                }
            },
            'needs_investigation': {
                'emoji': '🔍',
                'title': 'NEEDS INVESTIGATION',
                'color': discord.Color.orange(),
                'responses': {
                    'sassy_reporter': [
                        "Hmm, this one's sus. Need to dig deeper. 🔍",
                        "The jury's still out on this tea... ☕",
                        "Interesting claim. Sources needed! 📚",
                        "This needs more investigation than my dating life."
                    ],
                    'investigative_journalist': [
                        "Insufficient evidence to make a determination. 🔍",
                        "This claim requires further investigation.",
                        "More sources needed to verify this statement.",
                        "Investigation ongoing. Verdict pending."
                    ],
                    'sports_commentator': [
                        "WE'RE GOING TO THE REPLAY BOOTH ON THIS ONE! 📹",
                        "The refs need more time to review this play!",
                        "UNDER REVIEW! The facts are still being examined!",
                        "TIME OUT! Need to check the playbook on this one!"
                    ],
                    'default': [
                        "This requires further investigation. 🔍",
                        "Fact-check verdict: NEEDS MORE INFO",
                        "Unable to verify with available information.",
                        "Status: Under review."
                    ]
                }
            }
        }
        
        verdict_info = verdicts[selected_category]
        persona_responses = verdict_info['responses'].get(persona, verdict_info['responses']['default'])
        
        return {
            'category': selected_category,
            'emoji': verdict_info['emoji'],
            'title': verdict_info['title'],
            'color': verdict_info['color'],
            'response': random.choice(persona_responses)
        }
    
    def _create_verdict_embed(self, message, verdict, ctx: CommandContext) -> discord.Embed:
        """Create the fact-check verdict embed."""
        
        embed = discord.Embed(
            title=f"{verdict['emoji']} FACT-CHECK: {verdict['title']}",
            description=verdict['response'],
            color=verdict['color'],
            timestamp=datetime.now()
        )
        
        # Add the original message content (truncated)
        original_content = message.content
        if len(original_content) > 200:
            original_content = original_content[:200] + "..."
        
        embed.add_field(
            name="📝 Original Message",
            value=f"```{original_content}```",
            inline=False
        )
        
        # Add author info
        try:
            author = ctx.interaction.guild.get_member(int(message.author.id))
            author_name = author.display_name if author else f"User {message.author.id}"
        except:
            author_name = f"User {message.author.id}"
        
        embed.add_field(
            name="👤 Message Author",
            value=author_name,
            inline=True
        )
        
        embed.add_field(
            name="📊 Fact-Check ID",
            value=f"`{str(message.id)[:8]}...`",
            inline=True
        )
        
        # Disclaimer
        embed.set_footer(
            text="⚠️ This is a humorous, non-authoritative fact-check for entertainment purposes only."
        )
        
        return embed


# Context menu command for right-click fact-check
import discord
from discord import app_commands

@app_commands.context_menu(name='Fact Check')
async def fact_check_context_menu(interaction: discord.Interaction, message: discord.Message):
    """Context menu command for fact-checking messages."""
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
    
    # Create fact check command instance and execute
    fact_check_cmd = FactCheckCommand()
    
    # Use the target message ID from the context menu
    await fact_check_cmd.execute(ctx, message_id=str(message.id))


# Register the commands
from src.discord_bot.commands.base import command_registry
command_registry.register(FactCheckCommand())

# Note: Context menu commands need to be registered separately in the bot setup
# This is handled in the bot.py file during command sync