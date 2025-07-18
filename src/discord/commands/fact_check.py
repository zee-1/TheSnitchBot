"""
Fact check command for The Snitch Discord Bot.
Provides humorous, non-authoritative verdicts on messages.
"""

import discord
from typing import Dict, Any
import random
from datetime import datetime

from src.discord.commands.base import PublicCommand, CommandContext, EmbedBuilder
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
    
    async def execute(self, ctx: CommandContext, **kwargs) -> None:
        """Execute the fact-check command."""
        message_id = kwargs['message_id']
        
        logger.info(
            "Fact-check command executed",
            user_id=ctx.user_id,
            guild_id=ctx.guild_id,
            channel_id=ctx.channel_id,
            target_message_id=message_id
        )
        
        try:
            # Get Discord client from container
            settings = ctx.container.get_settings()
            
            # Import here to avoid circular imports
            from src.discord.client import get_discord_client
            discord_client = await get_discord_client(settings)
            
            # Get the target message
            target_message = await discord_client.get_message(ctx.channel_id, message_id)
            
            if not target_message:
                embed = EmbedBuilder.warning(
                    "Message Not Found",
                    f"Could not find message with ID `{message_id}` in this channel."
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return
            
            # Don't fact-check bot messages
            if target_message.author_id == str(ctx.interaction.client.user.id):
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
            try:
                if settings.mock_ai_responses:
                    verdict = await self._generate_mock_verdict(target_message, ctx)
                else:
                    # Use AI service for fact checking
                    from src.ai import get_ai_service
                    ai_service = await get_ai_service()
                    
                    # Analyze the message content for fact-checking
                    analysis = await ai_service.groq_client.analyze_content(
                        content=target_message.content,
                        analysis_type="fact_check",
                        context=f"Discord message fact-check with {ctx.server_config.persona.value} persona"
                    )
                    
                    # Convert AI response to verdict format
                    verdict = await self._convert_ai_response_to_verdict(analysis, ctx)
                    
            except Exception as ai_error:
                logger.warning(f"AI fact-check failed, falling back to mock: {ai_error}")
                # Fallback to mock if AI service fails
                verdict = await self._generate_mock_verdict(target_message, ctx)
            
            # Create fact-check response
            embed = self._create_verdict_embed(target_message, verdict, ctx)
            
            await ctx.respond(embed=embed)
            
            # Add reaction to original message
            try:
                emoji = verdict['emoji']
                await discord_client.add_reaction(ctx.channel_id, message_id, emoji)
            except Exception as e:
                logger.warning(f"Failed to add reaction to message {message_id}: {e}")
            
            logger.info(
                "Fact-check completed",
                user_id=ctx.user_id,
                guild_id=ctx.guild_id,
                target_message_id=message_id,
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
        analysis_lower = analysis.lower().strip()
        
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
        persona = ctx.server_config.persona.value
        
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
        persona = ctx.server_config.persona.value
        
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
            author = ctx.guild.get_member(int(message.author_id))
            author_name = author.display_name if author else f"User {message.author_id}"
        except:
            author_name = f"User {message.author_id}"
        
        embed.add_field(
            name="👤 Message Author",
            value=author_name,
            inline=True
        )
        
        embed.add_field(
            name="📊 Fact-Check ID",
            value=f"`{message.message_id[:8]}...`",
            inline=True
        )
        
        # Disclaimer
        embed.set_footer(
            text="⚠️ This is a humorous, non-authoritative fact-check for entertainment purposes only."
        )
        
        return embed


# Register the command
from src.discord.commands.base import command_registry
command_registry.register(FactCheckCommand())