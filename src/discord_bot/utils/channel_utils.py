"""
Channel utility functions for The Snitch Discord Bot.
Handles sending messages to configured channels.
"""

import discord
from typing import Optional, Union
from src.core.logging import get_logger
from src.models.server import ServerConfig
from src.discord_bot.commands.base import EmbedBuilder

logger = get_logger(__name__)


async def send_to_output_channel(
    ctx,
    embed: discord.Embed,
    confirmation_message: str = "Message sent to output channel"
) -> None:
    """
    Send an embed to the configured output channel or current channel.
    
    Args:
        ctx: Command context
        embed: Discord embed to send
        confirmation_message: Message to show in command channel if sent elsewhere
    """
    output_channel_id = ctx.server_config.get_output_channel()
    
    if output_channel_id and output_channel_id != ctx.channel_id:
        try:
            # Get the Discord client to send to output channel
            settings = ctx.container.get_settings()
            from src.discord_bot.client import get_discord_client
            discord_client = await get_discord_client(settings)
            output_channel = await discord_client.get_channel(output_channel_id)
            
            if output_channel:
                await output_channel.send(embed=embed)
                
                # Send confirmation to command channel
                confirmation_embed = EmbedBuilder.success(
                    "Output Sent",
                    f"{confirmation_message} ({output_channel.mention})! 📤"
                )
                await ctx.respond(embed=confirmation_embed)
            else:
                # Output channel not found, send to current channel
                logger.warning(f"Output channel {output_channel_id} not found, using current channel")
                await ctx.respond(embed=embed)
        except Exception as e:
            logger.warning(f"Failed to send to output channel: {e}")
            # Fallback to current channel
            await ctx.respond(embed=embed)
    else:
        # No output channel configured or same as current channel
        await ctx.respond(embed=embed)


async def send_bot_update(
    server_config: ServerConfig,
    embed: discord.Embed,
    discord_client=None,
    use_fallback: bool = False
) -> bool:
    """
    Send a bot update to the configured bot updates channel.
    
    Args:
        server_config: Server configuration
        embed: Discord embed to send
        discord_client: Discord client instance (optional)
        use_fallback: Whether to use fallback channels if bot updates channel not configured
        
    Returns:
        bool: True if sent successfully, False otherwise
    """
    bot_updates_channel_id = server_config.get_bot_updates_channel()
    
    # Try fallback channels if bot updates channel not configured and fallback enabled
    if not bot_updates_channel_id and use_fallback:
        # Try newsletter channel as fallback
        if server_config.newsletter_channel_id:
            bot_updates_channel_id = server_config.newsletter_channel_id
            logger.info(f"Using newsletter channel {bot_updates_channel_id} as fallback for bot updates")
        else:
            logger.info(f"No bot updates channel or newsletter channel configured for server {server_config.server_id}")
            return False
    elif not bot_updates_channel_id:
        return False  # No bot updates channel configured and no fallback requested
    
    try:
        if not discord_client:
            # Get Discord client if not provided
            from src.core.dependencies import get_container
            container = await get_container()
            settings = container.get_settings()
            from src.discord_bot.client import get_discord_client
            discord_client = await get_discord_client(settings)
        
        bot_updates_channel = await discord_client.get_channel(bot_updates_channel_id)
        
        if bot_updates_channel:
            await bot_updates_channel.send(embed=embed)
            logger.info(f"Bot update sent to channel {bot_updates_channel_id}")
            return True
        else:
            logger.warning(f"Bot updates channel {bot_updates_channel_id} not found")
            return False
            
    except Exception as e:
        logger.error(f"Failed to send bot update: {e}")
        return False


async def send_startup_notification(server_configs: list[ServerConfig]) -> None:
    """
    Send startup notification to all configured bot updates channels.
    
    Args:
        server_configs: List of server configurations
    """
    if not server_configs:
        return
    
    try:
        from src.core.dependencies import get_container
        container = await get_container()
        settings = container.get_settings()
        from src.discord_bot.client import get_discord_client
        discord_client = await get_discord_client(settings)
        
        startup_embed = EmbedBuilder.success(
            "🤖 The Snitch Bot Started",
            "The bot is now online and ready to serve! All systems operational."
        )
        startup_embed.add_field(
            name="📋 Available Features",
            value="• Breaking News\n• Server Leaks\n• Newsletter\n• Tip Submissions\n• Admin Commands",
            inline=True
        )
        startup_embed.add_field(
            name="⚡ Status",
            value="All services online",
            inline=True
        )
        
        sent_count = 0
        for server_config in server_configs:
            if await send_bot_update(server_config, startup_embed, discord_client, use_fallback=True):
                sent_count += 1
        
        logger.info(f"Startup notifications sent to {sent_count} servers")
        
    except Exception as e:
        logger.error(f"Failed to send startup notifications: {e}")


async def send_error_notification(
    server_config: ServerConfig,
    error_title: str,
    error_description: str,
    error_details: Optional[str] = None
) -> bool:
    """
    Send an error notification to the bot updates channel.
    
    Args:
        server_config: Server configuration
        error_title: Title of the error
        error_description: Description of the error
        error_details: Optional additional error details
        
    Returns:
        bool: True if sent successfully, False otherwise
    """
    error_embed = EmbedBuilder.error(error_title, error_description)
    
    if error_details:
        error_embed.add_field(
            name="📋 Details",
            value=f"```{error_details[:1000]}```",  # Limit to 1000 chars
            inline=False
        )
    
    error_embed.add_field(
        name="⏰ Time",
        value=f"<t:{int(discord.utils.utcnow().timestamp())}:F>",
        inline=True
    )
    
    return await send_bot_update(server_config, error_embed)


async def send_feature_update(
    server_configs: list[ServerConfig],
    update_title: str,
    update_description: str,
    features: Optional[list[str]] = None
) -> None:
    """
    Send feature update notification to all configured bot updates channels.
    
    Args:
        server_configs: List of server configurations
        update_title: Title of the update
        update_description: Description of the update
        features: Optional list of new features
    """
    update_embed = EmbedBuilder.newsletter(
        title=f"📢 {update_title}",
        content=update_description,
        author_name="The Snitch Bot Updates"
    )
    
    if features:
        update_embed.add_field(
            name="🆕 New Features",
            value="\n".join([f"• {feature}" for feature in features]),
            inline=False
        )
    
    update_embed.add_field(
        name="⏰ Released",
        value=f"<t:{int(discord.utils.utcnow().timestamp())}:F>",
        inline=True
    )
    
    try:
        from src.core.dependencies import get_container
        container = await get_container()
        settings = container.get_settings()
        from src.discord_bot.client import get_discord_client
        discord_client = await get_discord_client(settings)
        
        sent_count = 0
        for server_config in server_configs:
            if await send_bot_update(server_config, update_embed, discord_client, use_fallback=True):
                sent_count += 1
        
        logger.info(f"Feature update notifications sent to {sent_count} servers")
        
    except Exception as e:
        logger.error(f"Failed to send feature update notifications: {e}")