"""
Main Discord bot client for The Snitch Discord Bot.
Handles Discord events, message processing, and command registration.
"""

import discord
from discord.ext import commands, tasks
import asyncio
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from src.core.config import get_settings
from src.core.dependencies import DependencyContainer
from src.core.exceptions import BotInitializationError, MessageProcessingError
from src.core.logging import get_logger, setup_logging
from src.discord.client import DiscordClient
from src.discord.commands.base import command_registry
from src.models.server import ServerConfig, PersonaType
from src.models.message import Message, MessageReaction
from src.ai import get_ai_service

logger = get_logger(__name__)


class SnitchBot(commands.Bot):
    """The main Discord bot client for The Snitch."""
    
    def __init__(self):
        # Bot intents - we need message content and reactions
        intents = discord.Intents.default()
        intents.message_content = True
        intents.reactions = True
        intents.members = True  # For user information
        
        super().__init__(
            command_prefix='!',  # Fallback prefix, we primarily use slash commands
            intents=intents,
            help_command=None  # We'll implement our own help
        )
        
        self.settings = get_settings()
        self.container: Optional[DependencyContainer] = None
        self.discord_client: Optional[DiscordClient] = None
        self.ai_service = None
        self.server_configs: Dict[str, ServerConfig] = {}
        self.processing_queue = asyncio.Queue()
        self.is_ready = False
        
    async def setup_hook(self):
        """Called when the bot is starting up."""
        logger.info("Setting up The Snitch Discord Bot...")
        
        try:
            # Initialize dependency container
            self.container = DependencyContainer()
            await self.container.initialize()
            
            # Initialize Discord client wrapper
            from src.discord.client import get_discord_client
            self.discord_client = await get_discord_client(self.settings)
            
            # Initialize AI service
            self.ai_service = await get_ai_service()
            
            # Register slash commands
            await self._register_slash_commands()
            
            # Start background tasks
            self.message_processor.start()
            self.newsletter_scheduler.start()
            
            logger.info("Bot setup completed successfully")
            
        except Exception as e:
            logger.error(f"Failed to setup bot: {e}")
            raise BotInitializationError(f"Bot setup failed: {e}")
    
    async def on_ready(self):
        """Called when the bot has finished logging in and is ready."""
        logger.info(f"Bot logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guilds")
        
        # Load server configurations
        await self._load_server_configs()
        
        # Set bot status
        activity = discord.Activity(
            type=discord.ActivityType.watching, 
            name="for community drama 👀"
        )
        await self.change_presence(activity=activity)
        
        self.is_ready = True
        logger.info("The Snitch is now online and ready!")
    
    async def on_guild_join(self, guild: discord.Guild):
        """Called when the bot joins a new guild."""
        logger.info(f"Joined new guild: {guild.name} (ID: {guild.id})")
        
        # Create default server configuration
        await self._create_default_server_config(guild.id, guild.name)
        
        # Send welcome message if possible
        await self._send_welcome_message(guild)
    
    async def on_guild_remove(self, guild: discord.Guild):
        """Called when the bot is removed from a guild."""
        logger.info(f"Removed from guild: {guild.name} (ID: {guild.id})")
        
        # Clean up server data if configured to do so
        if hasattr(self.ai_service, 'cleanup_server_data'):
            try:
                await self.ai_service.cleanup_server_data(str(guild.id), days_to_keep=0)
            except Exception as e:
                logger.warning(f"Failed to cleanup data for removed guild {guild.id}: {e}")
    
    async def on_message(self, message: discord.Message):
        """Called when a message is sent in a guild."""
        # Ignore bot messages
        if message.author.bot:
            return
            
        # Only process guild messages
        if not message.guild:
            return
            
        # Check if we should process this message
        if await self._should_process_message(message):
            await self.processing_queue.put(('message', message))
    
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        """Called when a reaction is added to a message."""
        if user.bot or not reaction.message.guild:
            return
            
        await self.processing_queue.put(('reaction_add', reaction, user))
    
    async def on_reaction_remove(self, reaction: discord.Reaction, user: discord.User):
        """Called when a reaction is removed from a message."""
        if user.bot or not reaction.message.guild:
            return
            
        await self.processing_queue.put(('reaction_remove', reaction, user))
    
    async def _register_slash_commands(self):
        """Register all slash commands with Discord."""
        logger.info("Registering slash commands...")
        
        registered_commands = []
        
        for command_class in command_registry.get_all_commands():
            try:
                # Create command instance
                cmd_instance = command_class()
                
                # Create Discord slash command
                slash_cmd = discord.app_commands.Command(
                    name=cmd_instance.name,
                    description=cmd_instance.description,
                    callback=self._create_command_callback(cmd_instance)
                )
                
                # Add to command tree
                self.tree.add_command(slash_cmd)
                registered_commands.append(cmd_instance.name)
                
            except Exception as e:
                logger.error(f"Failed to register command {command_class.__name__}: {e}")
        
        # Sync commands with Discord
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} slash commands: {registered_commands}")
        except Exception as e:
            logger.error(f"Failed to sync commands with Discord: {e}")
    
    def _create_command_callback(self, command_instance):
        """Create a callback function for a slash command."""
        async def callback(interaction: discord.Interaction, **kwargs):
            try:
                # Get server configuration
                server_config = self.server_configs.get(str(interaction.guild_id))
                if not server_config:
                    server_config = await self._create_default_server_config(
                        interaction.guild_id, 
                        interaction.guild.name
                    )
                
                # Create command context
                from src.discord.commands.base import CommandContext
                ctx = CommandContext(
                    interaction=interaction,
                    container=self.container,
                    server_config=server_config
                )
                
                # Execute command
                await command_instance.handle(ctx, **kwargs)
                
            except Exception as e:
                logger.error(f"Command {command_instance.name} failed: {e}", exc_info=True)
                
                # Send error response if not already responded
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ An error occurred while processing your command. Please try again later.",
                        ephemeral=True
                    )
        
        return callback
    
    async def _load_server_configs(self):
        """Load server configurations for all connected guilds."""
        logger.info("Loading server configurations...")
        
        try:
            # Get server repository
            server_repo = self.container.get_server_repository()
            
            for guild in self.guilds:
                try:
                    config = await server_repo.get_by_server_id(str(guild.id))
                    if config:
                        self.server_configs[str(guild.id)] = config
                    else:
                        # Create default config for new servers
                        config = await self._create_default_server_config(guild.id, guild.name)
                        
                except Exception as e:
                    logger.error(f"Failed to load config for guild {guild.id}: {e}")
                    # Create default config as fallback
                    await self._create_default_server_config(guild.id, guild.name)
            
            logger.info(f"Loaded configurations for {len(self.server_configs)} servers")
            
        except Exception as e:
            logger.error(f"Failed to load server configurations: {e}")
    
    async def _create_default_server_config(self, guild_id: int, guild_name: str) -> ServerConfig:
        """Create a default server configuration."""
        try:
            server_repo = self.container.get_server_repository()
            
            config = ServerConfig(
                server_id=str(guild_id),
                server_name=guild_name,
                persona=PersonaType.SASSY_REPORTER,  # Default persona
                newsletter_enabled=True,
                newsletter_channel_id=None,  # Will be set by admin
                newsletter_time="09:00",
                timezone="UTC"
            )
            
            # Save to database
            await server_repo.create(config)
            
            # Cache locally
            self.server_configs[str(guild_id)] = config
            
            logger.info(f"Created default config for guild {guild_id}")
            return config
            
        except Exception as e:
            logger.error(f"Failed to create default config for guild {guild_id}: {e}")
            # Return minimal config for bot to function
            return ServerConfig(
                server_id=str(guild_id),
                server_name=guild_name,
                persona=PersonaType.SASSY_REPORTER
            )
    
    async def _should_process_message(self, message: discord.Message) -> bool:
        """Check if a message should be processed."""
        server_config = self.server_configs.get(str(message.guild.id))
        if not server_config:
            return False
        
        # Check if channel is whitelisted (if whitelist exists)
        if not server_config.is_channel_whitelisted(str(message.channel.id)):
            return False
        
        # Check for blacklisted words
        content_lower = message.content.lower()
        if any(word.lower() in content_lower for word in server_config.blacklisted_words):
            return False
        
        # Skip very short messages
        if len(message.content.strip()) < 3:
            return False
            
        return True
    
    async def _send_welcome_message(self, guild: discord.Guild):
        """Send a welcome message to a new guild."""
        try:
            # Try to find a suitable channel (general, welcome, etc.)
            welcome_channel = None
            
            for channel in guild.text_channels:
                if channel.name.lower() in ['general', 'welcome', 'bot-commands', 'main']:
                    if channel.permissions_for(guild.me).send_messages:
                        welcome_channel = channel
                        break
            
            # Fallback to first available channel
            if not welcome_channel:
                for channel in guild.text_channels:
                    if channel.permissions_for(guild.me).send_messages:
                        welcome_channel = channel
                        break
            
            if welcome_channel:
                embed = discord.Embed(
                    title="👋 Hey there! The Snitch has arrived!",
                    description=(
                        "I'm here to keep your community entertained with daily newsletters, "
                        "breaking news, and some light-hearted fact-checking! ✨\n\n"
                        "**Get started:**\n"
                        "• Use `/config set-persona` to choose my personality\n"
                        "• Use `/config set-newsletter-channel` to set where I post newsletters\n"
                        "• Try `/breaking-news` to see me in action!\n\n"
                        "I'll analyze your server activity and create entertaining content "
                        "while respecting privacy and keeping things fun. 🎭"
                    ),
                    color=discord.Color.blue()
                )
                embed.set_footer(text="Use /help to see all my commands!")
                
                await welcome_channel.send(embed=embed)
                
        except Exception as e:
            logger.warning(f"Failed to send welcome message to guild {guild.id}: {e}")
    
    @tasks.loop(seconds=5)
    async def message_processor(self):
        """Background task to process messages and reactions."""
        try:
            # Process items from queue
            while not self.processing_queue.empty():
                try:
                    item = await asyncio.wait_for(self.processing_queue.get(), timeout=1.0)
                    
                    if item[0] == 'message':
                        await self._process_message(item[1])
                    elif item[0] == 'reaction_add':
                        await self._process_reaction_add(item[1], item[2])
                    elif item[0] == 'reaction_remove':
                        await self._process_reaction_remove(item[1], item[2])
                        
                except asyncio.TimeoutError:
                    break
                except Exception as e:
                    logger.error(f"Error processing queue item: {e}")
                    
        except Exception as e:
            logger.error(f"Message processor error: {e}")
    
    @message_processor.before_loop
    async def before_message_processor(self):
        """Wait for bot to be ready before starting message processor."""
        await self.wait_until_ready()
    
    @tasks.loop(minutes=30)
    async def newsletter_scheduler(self):
        """Background task to check for newsletter scheduling."""
        try:
            current_time = datetime.now()
            
            for server_id, config in self.server_configs.items():
                if not config.newsletter_enabled or not config.newsletter_channel_id:
                    continue
                
                # Check if it's time for newsletter (simplified logic)
                # TODO: Implement proper timezone handling and scheduling
                if await self._should_generate_newsletter(config, current_time):
                    await self._generate_and_send_newsletter(config)
                    
        except Exception as e:
            logger.error(f"Newsletter scheduler error: {e}")
    
    @newsletter_scheduler.before_loop
    async def before_newsletter_scheduler(self):
        """Wait for bot to be ready before starting newsletter scheduler."""
        await self.wait_until_ready()
    
    async def _process_message(self, message: discord.Message):
        """Process a Discord message and store it."""
        try:
            # Convert Discord message to our Message model
            msg_model = await self._convert_discord_message(message)
            
            # Store in database
            message_repo = self.container.get_message_repository()
            await message_repo.create(msg_model)
            
            # Embed for semantic search (async)
            if self.ai_service and hasattr(self.ai_service, 'embedding_service'):
                try:
                    await self.ai_service.embedding_service.embed_messages(
                        messages=[msg_model],
                        server_id=str(message.guild.id),
                        batch_size=1
                    )
                except Exception as e:
                    logger.warning(f"Failed to embed message {message.id}: {e}")
            
        except Exception as e:
            logger.error(f"Failed to process message {message.id}: {e}")
            raise MessageProcessingError(f"Message processing failed: {e}")
    
    async def _process_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        """Process a reaction being added."""
        try:
            # Update message in database with new reaction
            message_repo = self.container.get_message_repository()
            
            # Get existing message
            msg_model = await message_repo.get_by_message_id(str(reaction.message.id))
            if msg_model:
                # Add reaction to model
                reaction_model = MessageReaction(
                    emoji=str(reaction.emoji),
                    count=reaction.count,
                    users=[str(user.id) for user in await reaction.users().flatten()]
                )
                
                # Update reactions list
                existing_reactions = [r for r in msg_model.reactions if r.emoji != str(reaction.emoji)]
                existing_reactions.append(reaction_model)
                msg_model.reactions = existing_reactions
                msg_model.total_reactions = sum(r.count for r in msg_model.reactions)
                
                # Update in database
                await message_repo.update(msg_model)
                
        except Exception as e:
            logger.error(f"Failed to process reaction add: {e}")
    
    async def _process_reaction_remove(self, reaction: discord.Reaction, user: discord.User):
        """Process a reaction being removed."""
        try:
            # Similar to add but remove the reaction
            message_repo = self.container.get_message_repository()
            
            msg_model = await message_repo.get_by_message_id(str(reaction.message.id))
            if msg_model:
                # Update reaction count
                for r in msg_model.reactions:
                    if r.emoji == str(reaction.emoji):
                        r.count = reaction.count
                        if reaction.count == 0:
                            msg_model.reactions.remove(r)
                        break
                
                msg_model.total_reactions = sum(r.count for r in msg_model.reactions)
                await message_repo.update(msg_model)
                
        except Exception as e:
            logger.error(f"Failed to process reaction remove: {e}")
    
    async def _convert_discord_message(self, message: discord.Message) -> Message:
        """Convert a Discord message to our Message model."""
        
        return Message(
            message_id=str(message.id),
            server_id=str(message.guild.id),
            channel_id=str(message.channel.id),
            author_id=str(message.author.id),
            content=message.content,
            timestamp=message.created_at,
            reactions=[],  # Will be updated by reaction events
            reply_count=0,  # Discord doesn't provide this directly
            attachments=[att.url for att in message.attachments],
            embeds=[embed.to_dict() for embed in message.embeds],
            controversy_score=0.0  # Will be calculated by AI
        )
    
    async def _should_generate_newsletter(self, config: ServerConfig, current_time: datetime) -> bool:
        """Check if it's time to generate a newsletter."""
        # Simplified logic - generate once per day
        # TODO: Implement proper scheduling with timezone support
        
        try:
            newsletter_repo = self.container.get_newsletter_repository()
            
            # Check if we already generated today
            today_start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
            today_newsletters = await newsletter_repo.get_by_server_and_date_range(
                config.server_id, today_start, current_time
            )
            
            return len(today_newsletters) == 0
            
        except Exception as e:
            logger.error(f"Error checking newsletter schedule: {e}")
            return False
    
    async def _generate_and_send_newsletter(self, config: ServerConfig):
        """Generate and send a newsletter for a server."""
        try:
            logger.info(f"Generating newsletter for server {config.server_id}")
            
            # Get recent messages
            message_repo = self.container.get_message_repository()
            cutoff_time = datetime.now() - timedelta(hours=24)
            
            recent_messages = await message_repo.get_by_server_and_time_range(
                config.server_id, cutoff_time, datetime.now()
            )
            
            if len(recent_messages) < 5:
                logger.info(f"Insufficient messages for newsletter in server {config.server_id}")
                return
            
            # Create newsletter object
            from src.models.newsletter import Newsletter
            newsletter = Newsletter(
                server_id=config.server_id,
                newsletter_date=datetime.now().date()
            )
            
            # Generate using AI service
            if self.ai_service:
                completed_newsletter = await self.ai_service.generate_enhanced_newsletter(
                    messages=recent_messages,
                    server_config=config,
                    newsletter=newsletter,
                    use_semantic_enhancement=True
                )
                
                # Save to database
                newsletter_repo = self.container.get_newsletter_repository()
                await newsletter_repo.create(completed_newsletter)
                
                # Send to Discord channel
                await self._send_newsletter_to_channel(completed_newsletter, config)
                
                logger.info(f"Newsletter generated and sent for server {config.server_id}")
            
        except Exception as e:
            logger.error(f"Failed to generate newsletter for server {config.server_id}: {e}")
    
    async def _send_newsletter_to_channel(self, newsletter, config: ServerConfig):
        """Send newsletter to the configured Discord channel."""
        try:
            channel = self.get_channel(int(config.newsletter_channel_id))
            if not channel:
                logger.error(f"Newsletter channel not found: {config.newsletter_channel_id}")
                return
            
            # Create newsletter embed
            embed = discord.Embed(
                title=f"📰 {newsletter.title}",
                description=newsletter.introduction,
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            if newsletter.featured_story:
                embed.add_field(
                    name="📖 Featured Story",
                    value=newsletter.featured_story.full_content[:1000] + "..." 
                          if len(newsletter.featured_story.full_content) > 1000 
                          else newsletter.featured_story.full_content,
                    inline=False
                )
            
            if newsletter.brief_mentions:
                brief_text = "\n".join(newsletter.brief_mentions[:3])
                embed.add_field(
                    name="📝 Other News",
                    value=brief_text,
                    inline=False
                )
            
            embed.add_field(
                name="📊 Stats",
                value=f"Analyzed {newsletter.analyzed_messages_count} messages",
                inline=True
            )
            
            embed.set_footer(text=f"Generated by The Snitch • {config.persona.value.replace('_', ' ').title()}")
            
            await channel.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Failed to send newsletter to channel: {e}")


# Global bot instance
bot: Optional[SnitchBot] = None


def get_bot() -> SnitchBot:
    """Get the global bot instance."""
    global bot
    if bot is None:
        bot = SnitchBot()
    return bot


async def run_bot():
    """Run the Discord bot."""
    setup_logging()
    
    try:
        settings = get_settings()
        bot_instance = get_bot()
        
        logger.info("Starting The Snitch Discord Bot...")
        await bot_instance.start(settings.discord_token)
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise