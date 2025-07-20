"""
Tip management commands for The Snitch Discord Bot.
Allows admins to review, approve, assign, and manage submitted tips.
"""

import discord
from typing import Dict, Any, Optional, List
from datetime import datetime

from src.discord_bot.commands.base import AdminCommand, ModeratorCommand, CommandContext, EmbedBuilder
from src.core.exceptions import InvalidCommandArgumentError, DatabaseError
from src.core.logging import get_logger
from src.models.tip import Tip, TipStatus, TipPriority, TipCategory
from src.utils.validation import validate_discord_id

logger = get_logger(__name__)


class ApproveTipCommand(AdminCommand):
    """Command to approve/review tips."""
    
    def __init__(self):
        super().__init__(
            name="approve-tip",
            description="Approve or process a submitted tip",
            cooldown_seconds=5
        )
    
    def define_parameters(self) -> Dict[str, Dict[str, Any]]:
        """Define command parameters."""
        return {
            "tip_id": {
                "type": str,
                "description": "The ID of the tip to approve (first 8 characters minimum)",
                "required": True
            },
            "action": {
                "type": str,
                "description": "Action to take (approve, process, dismiss)",
                "required": True,
                "choices": ["approve", "process", "dismiss"]
            },
            "notes": {
                "type": str,
                "description": "Notes about the approval/processing",
                "required": False,
                "max_length": 500
            },
            "newsletter": {
                "type": bool,
                "description": "Mark if this resulted in newsletter content (for process action)",
                "required": False,
                "default": False
            }
        }
    
    async def validate_arguments(self, ctx: CommandContext, **kwargs) -> Dict[str, Any]:
        """Validate command arguments."""
        validated = {}
        
        # Validate tip_id
        tip_id = kwargs.get('tip_id', '').strip()
        if not tip_id or len(tip_id) < 8:
            raise InvalidCommandArgumentError(
                self.name,
                'tip_id',
                'Tip ID must be at least 8 characters'
            )
        validated['tip_id'] = tip_id
        
        # Validate action
        action = kwargs.get('action', '').lower()
        if action not in ['approve', 'process', 'dismiss']:
            raise InvalidCommandArgumentError(
                self.name,
                'action',
                'Action must be approve, process, or dismiss'
            )
        validated['action'] = action
        
        # Validate notes (optional)
        notes = kwargs.get('notes', '').strip()
        validated['notes'] = notes if notes else ""
        
        # Validate newsletter flag
        validated['newsletter'] = kwargs.get('newsletter', False)
        
        return validated
    
    async def execute(self, ctx: CommandContext, tip_id: str, action: str, notes: str = "", newsletter: bool = False):
        """Execute the approve-tip command."""
        
        logger.info(
            "Approve tip command executed",
            extra={
                "user_id": ctx.user_id,
                "guild_id": ctx.guild_id,
                "tip_id": tip_id,
                "action": action
            }
        )
        
        try:
            # Get tip repository
            tip_repo = ctx.container.get_tip_repository()
            
            # Find tip by partial ID
            tip = await self._find_tip_by_partial_id(tip_repo, tip_id, ctx.guild_id)
            
            if not tip:
                embed = EmbedBuilder.error(
                    "Tip Not Found",
                    f"No tip found with ID starting with `{tip_id}`. Use `/list-tips` to see available tips."
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return
            
            # Perform the requested action
            success = False
            action_description = ""
            
            if action == "approve":
                success = await tip_repo.update_tip_status(
                    tip.id, ctx.guild_id, TipStatus.REVIEWED, notes
                )
                action_description = "approved for review"
                
            elif action == "process":
                resolution = notes if notes else "Tip processed by moderator"
                success = await tip_repo.mark_tip_processed(
                    tip.id, ctx.guild_id, resolution, newsletter
                )
                action_description = "marked as processed"
                
            elif action == "dismiss":
                reason = notes if notes else "Dismissed by moderator"
                success = await tip_repo.dismiss_tip(tip.id, ctx.guild_id, reason)
                action_description = "dismissed"
            
            if success:
                # Create success embed
                embed = EmbedBuilder.success(
                    "Tip Updated",
                    f"Tip has been successfully {action_description}! ✅"
                )
                
                # Add tip details
                embed.add_field(
                    name="Tip ID",
                    value=f"`{tip.id[:8]}...`",
                    inline=True
                )
                
                embed.add_field(
                    name="Category",
                    value=tip.category.value.replace('_', ' ').title(),
                    inline=True
                )
                
                embed.add_field(
                    name="Age",
                    value=f"{tip.age_hours:.1f} hours",
                    inline=True
                )
                
                # Add content preview (first 100 chars)
                content_preview = tip.content[:100]
                if len(tip.content) > 100:
                    content_preview += "..."
                
                embed.add_field(
                    name="Content Preview",
                    value=f"```{content_preview}```",
                    inline=False
                )
                
                if notes:
                    embed.add_field(
                        name="Notes",
                        value=notes,
                        inline=False
                    )
                
                if action == "process" and newsletter:
                    embed.add_field(
                        name="Newsletter",
                        value="✅ Marked as resulting in newsletter content",
                        inline=False
                    )
                
                # Add footer with moderator info
                embed.set_footer(text=f"Action performed by {ctx.user.display_name}")
                
            else:
                embed = EmbedBuilder.error(
                    "Update Failed",
                    f"Failed to {action} the tip. Please try again."
                )
            
            await ctx.respond(embed=embed)
            
        except DatabaseError as e:
            embed = EmbedBuilder.error(
                "Database Error",
                "There was an error accessing the tip database. Please try again later."
            )
            await ctx.respond(embed=embed, ephemeral=True)
            logger.error(f"Database error in approve-tip command: {e}")
            
        except Exception as e:
            embed = EmbedBuilder.error(
                "Command Failed",
                "An unexpected error occurred while processing the tip."
            )
            await ctx.respond(embed=embed, ephemeral=True)
            logger.error(f"Unexpected error in approve-tip command: {e}", exc_info=True)
    
    async def _find_tip_by_partial_id(self, tip_repo, partial_id: str, server_id: str) -> Optional[Tip]:
        """Find tip by partial ID match."""
        try:
            # First try exact match
            tip = await tip_repo.get_tip_by_id(partial_id, server_id)
            if tip:
                return tip
            
            # Search for tips with matching prefix
            all_tips = await tip_repo.get_tips_by_server(server_id, max_count=100)
            
            matches = [tip for tip in all_tips if tip.id.startswith(partial_id)]
            
            if len(matches) == 1:
                return matches[0]
            elif len(matches) > 1:
                logger.warning(f"Multiple tips found for partial ID {partial_id}")
                return None
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error finding tip by partial ID {partial_id}: {e}")
            return None


class ListTipsCommand(ModeratorCommand):
    """Command to list pending tips for review."""
    
    def __init__(self):
        super().__init__(
            name="list-tips",
            description="List tips that need review",
            cooldown_seconds=10
        )
    
    def define_parameters(self) -> Dict[str, Dict[str, Any]]:
        """Define command parameters."""
        return {
            "status": {
                "type": str,
                "description": "Filter by status (pending, reviewed, investigating, processed, dismissed)",
                "required": False,
                "choices": ["pending", "reviewed", "investigating", "processed", "dismissed", "all"]
            },
            "category": {
                "type": str,
                "description": "Filter by category",
                "required": False,
                "choices": [category.value for category in TipCategory]
            },
            "limit": {
                "type": int,
                "description": "Maximum number of tips to show (default: 10)",
                "required": False,
                "min_value": 1,
                "max_value": 25
            }
        }
    
    async def validate_arguments(self, ctx: CommandContext, **kwargs) -> Dict[str, Any]:
        """Validate command arguments."""
        validated = {}
        
        # Status filter
        status = kwargs.get('status', 'pending').lower()
        if status == 'all':
            validated['status'] = None
        else:
            try:
                validated['status'] = TipStatus(status)
            except ValueError:
                raise InvalidCommandArgumentError(
                    self.name,
                    'status',
                    f'Invalid status: {status}'
                )
        
        # Category filter
        category = kwargs.get('category')
        if category:
            try:
                validated['category'] = TipCategory(category)
            except ValueError:
                raise InvalidCommandArgumentError(
                    self.name,
                    'category',
                    f'Invalid category: {category}'
                )
        else:
            validated['category'] = None
        
        # Limit
        validated['limit'] = kwargs.get('limit', 10)
        
        return validated
    
    async def execute(self, ctx: CommandContext, status: Optional[TipStatus] = TipStatus.PENDING, 
                     category: Optional[TipCategory] = None, limit: int = 10):
        """Execute the list-tips command."""
        
        logger.info(
            "List tips command executed",
            extra={
                "user_id": ctx.user_id,
                "guild_id": ctx.guild_id,
                "status_filter": status.value if status else "all",
                "category_filter": category.value if category else "all"
            }
        )
        
        try:
            # Get tip repository
            tip_repo = ctx.container.get_tip_repository()
            
            # Get tips based on filters
            if category:
                tips = await tip_repo.get_tips_by_category(ctx.guild_id, category, limit)
                if status:
                    tips = [tip for tip in tips if tip.status == status]
            else:
                tips = await tip_repo.get_tips_by_server(ctx.guild_id, status, limit)
            
            if not tips:
                status_text = status.value if status else "any status"
                category_text = category.value if category else "any category"
                
                embed = EmbedBuilder.info(
                    "No Tips Found",
                    f"No tips found with status `{status_text}` and category `{category_text}`."
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return
            
            # Create embed with tip list
            status_text = status.value if status else "all statuses"
            embed = EmbedBuilder.info(
                f"Tips ({status_text.title()})",
                f"Found {len(tips)} tip(s) matching your criteria."
            )
            
            # Add tips to embed (max 10 fields)
            for i, tip in enumerate(tips[:10]):
                # Format tip info
                content_preview = tip.content[:80]
                if len(tip.content) > 80:
                    content_preview += "..."
                
                # Status emoji
                status_emojis = {
                    TipStatus.PENDING: "⏳",
                    TipStatus.REVIEWED: "👀",
                    TipStatus.INVESTIGATING: "🔍",
                    TipStatus.PROCESSED: "✅",
                    TipStatus.DISMISSED: "❌"
                }
                status_emoji = status_emojis.get(tip.status, "❓")
                
                # Priority emoji
                priority_emojis = {
                    TipPriority.LOW: "🟢",
                    TipPriority.MEDIUM: "🟡",
                    TipPriority.HIGH: "🟠",
                    TipPriority.URGENT: "🔴"
                }
                priority_emoji = priority_emojis.get(tip.priority, "⚪")
                
                field_name = f"{status_emoji} {priority_emoji} `{tip.id[:8]}...` - {tip.category.value.title()}"
                field_value = f"**Age:** {tip.age_hours:.1f}h\n**Content:** {content_preview}"
                
                if tip.ai_relevance_score > 0:
                    field_value += f"\n**AI Score:** {tip.ai_relevance_score:.2f}"
                
                embed.add_field(
                    name=field_name,
                    value=field_value,
                    inline=False
                )
            
            # Add usage hint
            if tips:
                embed.set_footer(
                    text="Use /approve-tip <tip_id> <action> to manage tips. "
                         "Only first 8 characters of tip ID needed."
                )
            
            await ctx.respond(embed=embed)
            
        except DatabaseError as e:
            embed = EmbedBuilder.error(
                "Database Error",
                "There was an error accessing the tip database. Please try again later."
            )
            await ctx.respond(embed=embed, ephemeral=True)
            logger.error(f"Database error in list-tips command: {e}")
            
        except Exception as e:
            embed = EmbedBuilder.error(
                "Command Failed",
                "An unexpected error occurred while listing tips."
            )
            await ctx.respond(embed=embed, ephemeral=True)
            logger.error(f"Unexpected error in list-tips command: {e}", exc_info=True)


class TipStatsCommand(ModeratorCommand):
    """Command to show tip statistics."""
    
    def __init__(self):
        super().__init__(
            name="tip-stats",
            description="Show tip submission and processing statistics",
            cooldown_seconds=30
        )
    
    async def execute(self, ctx: CommandContext):
        """Execute the tip-stats command."""
        
        logger.info(
            "Tip stats command executed",
            extra={
                "user_id": ctx.user_id,
                "guild_id": ctx.guild_id
            }
        )
        
        try:
            # Get tip repository
            tip_repo = ctx.container.get_tip_repository()
            
            # Get statistics
            stats = await tip_repo.get_tip_statistics(ctx.guild_id)
            
            if not stats:
                embed = EmbedBuilder.error(
                    "Stats Unavailable",
                    "Unable to retrieve tip statistics at this time."
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return
            
            # Create stats embed
            embed = EmbedBuilder.info(
                "📊 Tip Statistics",
                "Server tip submission and processing statistics"
            )
            
            # Basic stats
            embed.add_field(
                name="📝 Total Tips",
                value=str(stats.get('total_tips', 0)),
                inline=True
            )
            
            embed.add_field(
                name="⏳ Pending",
                value=str(stats.get('pending_tips', 0)),
                inline=True
            )
            
            embed.add_field(
                name="✅ Processed",
                value=str(stats.get('processed_tips', 0)),
                inline=True
            )
            
            embed.add_field(
                name="❌ Dismissed",
                value=str(stats.get('dismissed_tips', 0)),
                inline=True
            )
            
            embed.add_field(
                name="🔥 High Priority",
                value=str(stats.get('high_priority_tips', 0)),
                inline=True
            )
            
            embed.add_field(
                name="📰 Newsletter Tips",
                value=str(stats.get('newsletter_tips', 0)),
                inline=True
            )
            
            # Success rate
            success_rate = stats.get('success_rate', 0)
            embed.add_field(
                name="🎯 Success Rate",
                value=f"{success_rate:.1f}%",
                inline=True
            )
            
            # Category distribution
            category_stats = stats.get('category_distribution', {})
            if category_stats:
                category_text = "\n".join([
                    f"• {cat.replace('_', ' ').title()}: {count}"
                    for cat, count in category_stats.items()
                    if count > 0
                ])
                
                if category_text:
                    embed.add_field(
                        name="📁 By Category",
                        value=category_text,
                        inline=False
                    )
            
            embed.set_footer(text=f"Statistics generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            await ctx.respond(embed=embed)
            
        except DatabaseError as e:
            embed = EmbedBuilder.error(
                "Database Error",
                "There was an error accessing the tip database. Please try again later."
            )
            await ctx.respond(embed=embed, ephemeral=True)
            logger.error(f"Database error in tip-stats command: {e}")
            
        except Exception as e:
            embed = EmbedBuilder.error(
                "Command Failed",
                "An unexpected error occurred while retrieving statistics."
            )
            await ctx.respond(embed=embed, ephemeral=True)
            logger.error(f"Unexpected error in tip-stats command: {e}", exc_info=True)


# Register the commands
from src.discord_bot.commands.base import command_registry

command_registry.register(ApproveTipCommand())
command_registry.register(ListTipsCommand())
command_registry.register(TipStatsCommand())