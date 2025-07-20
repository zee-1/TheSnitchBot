"""
Tip submission command for The Snitch Discord Bot.
Allows users to submit anonymous tips for investigation.
"""

from typing import Dict, Any
from datetime import datetime

from src.discord_bot.commands.base import PublicCommand, CommandContext, EmbedBuilder
from src.core.exceptions import ValidationError, DatabaseError, TipValidationError
from src.core.logging import get_logger
from src.models.tip import Tip, TipCategory
from src.data.repositories.tip_repository import TipRepository

logger = get_logger(__name__)


class SubmitTipCommand(PublicCommand):
    """Command for submitting anonymous tips."""
    
    def __init__(self):
        super().__init__(
            name="submit-tip",
            description="Submit an anonymous tip to the bot for investigation",
            cooldown_seconds=300  # 5 minute cooldown to prevent spam
        )
    
    def define_parameters(self) -> Dict[str, Dict[str, Any]]:
        """Define command parameters."""
        return {
            "content": {
                "type": str,
                "description": "The tip content (what you want to report)",
                "required": True,
                "max_length": 2000
            },
            "category": {
                "type": str,
                "description": "Category of tip (general, drama, controversy, breaking_news, rumor, investigation)",
                "required": False,
                "default": "general",
                "choices": [category.value for category in TipCategory]
            },
            "anonymous": {
                "type": bool,
                "description": "Submit anonymously (default: True)",
                "required": False,
                "default": True
            }
        }
    
    async def execute(self, ctx: CommandContext, content: str, category: str = "general", anonymous: bool = True):
        """Execute the submit-tip command."""
        
        # Check if tip submission is enabled for this server
        if not ctx.server_config.tip_submission_enabled:
            embed = EmbedBuilder.warning(
                "Tips Disabled",
                "Tip submission is not enabled on this server. Contact a server admin to enable it."
            )
            await ctx.respond(embed=embed, ephemeral=True)
            return
        
        # Log command execution
        logger.info(
            "Submit tip command executed",
            extra={
                "user_id": ctx.user_id,
                "guild_id": ctx.guild_id,
                "channel_id": ctx.channel_id,
                "content_length": len(content),
                "category": category,
                "anonymous": anonymous
            }
        )
        
        try:
            # Validate category
            try:
                tip_category = TipCategory(category)
            except ValueError:
                embed = EmbedBuilder.error(
                    "Invalid Category",
                    f"Category '{category}' is not valid. Valid categories: {', '.join([c.value for c in TipCategory])}"
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return
            
            # Create tip
            tip = Tip.create_from_command(
                server_id=ctx.guild_id,
                content=content,
                submitter_id=None if anonymous else ctx.user_id,
                channel_id=ctx.channel_id,
                is_anonymous=anonymous
            )
            tip.category = tip_category
            
            # Save tip to repository
            tip_repo = TipRepository(ctx.container.cosmos_client)
            await tip_repo.create(tip)
            
            # Create success response
            if anonymous:
                embed = EmbedBuilder.success(
                    "Anonymous Tip Submitted",
                    f"Your anonymous tip has been submitted successfully! 🕵️\n\n"
                    f"**Category:** {tip_category.value.replace('_', ' ').title()}\n"
                    f"**Tip ID:** `{tip.id[:8]}...`\n\n"
                    f"The moderation team will review your tip. Thank you for helping keep the server informed!"
                )
            else:
                embed = EmbedBuilder.success(
                    "Tip Submitted",
                    f"Your tip has been submitted successfully! 🕵️\n\n"
                    f"**Category:** {tip_category.value.replace('_', ' ').title()}\n"
                    f"**Tip ID:** `{tip.id[:8]}...`\n"
                    f"**Submitted by:** <@{ctx.user_id}>\n\n"
                    f"The moderation team will review your tip. Thank you for contributing!"
                )
            
            # Add footer with additional info
            embed.add_field(
                name="What happens next?",
                value="• Tips are reviewed by the moderation team\n"
                      "• High-priority tips may be investigated immediately\n"
                      "• Some tips may be featured in server newsletters\n"
                      "• All tips are kept confidential",
                inline=False
            )
            
            await ctx.respond(embed=embed, ephemeral=True)
            
            # Log tip creation for moderation
            logger.info(
                "Tip submitted successfully",
                extra={
                    "tip_id": tip.id,
                    "user_id": ctx.user_id,
                    "guild_id": ctx.guild_id,
                    "category": category,
                    "anonymous": anonymous,
                    "content_length": len(content)
                }
            )
            
        except ValidationError as e:
            embed = EmbedBuilder.error(
                "Validation Error",
                f"Your tip could not be submitted: {str(e)}"
            )
            await ctx.respond(embed=embed, ephemeral=True)
            
        except DatabaseError as e:
            embed = EmbedBuilder.error(
                "Submission Failed",
                "There was an error saving your tip. Please try again later."
            )
            await ctx.respond(embed=embed, ephemeral=True)
            logger.error(f"Database error in tip submission: {e}")
            
        except Exception as e:
            embed = EmbedBuilder.error(
                "Submission Failed",
                "An unexpected error occurred while submitting your tip. Please try again later."
            )
            await ctx.respond(embed=embed, ephemeral=True)
            logger.error(f"Unexpected error in tip submission: {e}", exc_info=True)


# Register the command
from src.discord_bot.commands.base import command_registry
command_registry.register(SubmitTipCommand())