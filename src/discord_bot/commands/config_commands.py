"""
Utility configuration commands for The Snitch Discord Bot.
Contains admin utility commands not handled by app command groups.
"""

import discord
from typing import Dict, Any

from src.discord_bot.commands.base import AdminCommand, CommandContext, EmbedBuilder
from src.core.logging import get_logger

logger = get_logger(__name__)


class SyncCommandsCommand(AdminCommand):
    """Command for admins to manually sync Discord commands."""
    
    def __init__(self):
        super().__init__(
            name="sync-commands",
            description="Manually sync Discord slash commands (admin maintenance)",
            cooldown_seconds=30
        )
    
    async def execute(self, ctx: CommandContext, **kwargs) -> None:
        """Execute the sync commands command."""
        
        logger.info(
            "Sync commands executed", 
            user_id=ctx.user_id,
            guild_id=ctx.guild_id
        )
        
        try:
            # Get the bot instance
            bot = ctx.interaction.client
            
            # Sync commands
            if hasattr(bot, 'tree'):
                synced = await bot.tree.sync()
                
                embed = EmbedBuilder.success(
                    "Commands Synced",
                    f"Successfully synced {len(synced)} slash commands with Discord! ⚡\n\n"
                    f"Commands should now be available or updated in this server."
                )
                
                # Show synced commands
                if synced:
                    command_names = [cmd.name for cmd in synced[:10]]  # Show first 10
                    if len(synced) > 10:
                        command_names.append(f"... and {len(synced) - 10} more")
                    
                    embed.add_field(
                        name="📋 Synced Commands",
                        value="```" + ", ".join(command_names) + "```",
                        inline=False
                    )
                
                embed.add_field(
                    name="⏱️ Note",
                    value="It may take a few minutes for commands to appear in Discord.",
                    inline=False
                )
                
                await ctx.respond(embed=embed)
            else:
                embed = EmbedBuilder.error(
                    "Sync Failed",
                    "Bot command tree not available."
                )
                await ctx.respond(embed=embed)
                
        except Exception as e:
            embed = EmbedBuilder.error(
                "Sync Failed",
                f"An error occurred while syncing commands: {str(e)[:200]}"
            )
            await ctx.respond(embed=embed)
            logger.error(f"Error in sync-commands: {e}", exc_info=True)


# Register the remaining essential commands
from src.discord_bot.commands.base import command_registry
command_registry.register(SyncCommandsCommand())