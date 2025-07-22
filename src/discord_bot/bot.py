"""
Main Discord bot client for The Snitch Discord Bot.
Handles Discord events, message processing, and command registration.
"""

import discord
from discord import app_commands

from discord.ext import commands, tasks
import asyncio
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from src.core.config import get_settings
from src.core.dependencies import DependencyContainer
from src.core.exceptions import BotInitializationError, MessageProcessingError
from src.core.logging import get_logger, setup_logging
from src.discord_bot.client import SnitchDiscordClient
from src.discord_bot.commands.base import command_registry
# Import command modules to trigger registration
import src.discord_bot.commands.config_commands
import src.discord_bot.commands.breaking_news
import src.discord_bot.commands.fact_check
import src.discord_bot.commands.leak
import src.discord_bot.commands.help_command
import src.discord_bot.commands.tip_command
import src.discord_bot.commands.tip_management
import src.discord_bot.commands.controversy_check
import src.discord_bot.commands.community_pulse
from src.models.server import ServerConfig, PersonaType
from src.models.message import Message, ReactionData
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
        self.discord_client: Optional[SnitchDiscordClient] = None
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
            from src.discord_bot.client import get_discord_client
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
        
        # Send startup notifications to bot updates channels
        try:
            server_repo = self.container.get_server_repository()
            all_server_configs = await server_repo.get_active_servers()
            
            from src.discord_bot.utils.channel_utils import send_startup_notification
            await send_startup_notification(all_server_configs, self)
        except Exception as e:
            logger.error(f"Failed to send startup notifications: {e}")
    
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
        
        # Register proper config commands with parameters
        from src.discord_bot.commands.config_app_commands import setup_config_commands
        config_group = setup_config_commands(self, self.container)
        logger.info("Registered config command group")
        
        # Register content commands with parameters
        from src.discord_bot.commands.content_app_commands import setup_content_commands
        await setup_content_commands(self.tree, self.container)
        logger.info("Registered content command group")
        
        # Register simple commands without parameters
        all_commands = command_registry.get_all_commands()
        print("All commands list===>")
        print(all_commands)
        logger.info(f"Found {len(all_commands)} simple commands to register")
        
        registered_commands = ["config"]  # Config group already added
        
        for command_instance in all_commands:
            try:
                # All commands are now properly organized - no need to skip any
                # Old duplicate commands have been removed from command registry
                    
                logger.info(f"Registering command: {command_instance.name}")
                
                # Create a simple command without parameters
                def make_callback(cmd_inst):
                    async def simple_callback(interaction: discord.Interaction):
                        await cmd_inst.handle_command(interaction, self.container)
                    return simple_callback
                
                slash_cmd = app_commands.Command(
                    name=command_instance.name,
                    description=command_instance.description,
                    callback=make_callback(command_instance)
                )
                
                # Add to command tree
                self.tree.add_command(slash_cmd)
                registered_commands.append(command_instance.name)
                logger.info(f"Successfully registered command: {command_instance.name}")
                
            except Exception as e:
                logger.error(f"Failed to register command {command_instance.name}: {e}", exc_info=True)
        
        logger.info(f"Registered {len(registered_commands)} commands locally: {registered_commands}")
        
        # Register context menu commands
        await self._register_context_menus()
        
        # Sync commands with Discord
        try:
            logger.info("Syncing commands with Discord...")
            
            # For development: sync to current guild for immediate testing
            # For production: sync globally (takes up to 1 hour)
            if self.settings.environment == "development" and self.guilds:
                # Sync to first guild for faster testing
                test_guild = self.guilds[0]
                synced = await self.tree.sync(guild=test_guild)
                logger.info(f"Successfully synced {len(synced)} commands to guild {test_guild.name} for testing")
                
                # Also sync globally for other guilds
                synced_global = await self.tree.sync()
                logger.info(f"Successfully synced {len(synced_global)} commands globally")
            else:
                # Production: sync globally only
                synced = await self.tree.sync()
                logger.info(f"Successfully synced {len(synced)} slash commands with Discord")
            
            logger.info(f"Synced commands: {[cmd.name for cmd in synced]}")
        except Exception as e:
            logger.error(f"Failed to sync commands with Discord: {e}", exc_info=True)
            raise
    
    async def _register_context_menus(self):
        """Register context menu commands."""
        try:
            from src.discord_bot.commands.fact_check import fact_check_context_menu
            from src.discord_bot.commands.controversy_check import controversy_check_context_menu
            
            # Add context menu commands to the tree
            self.tree.add_command(fact_check_context_menu)
            self.tree.add_command(controversy_check_context_menu)
            
            logger.info("Registered context menus: Fact Check, Controversy Check")
            
        except Exception as e:
            logger.error(f"Failed to register context menus: {e}", exc_info=True)
    
    def _create_command_callback(self, command_instance):
        """Create a callback function for a slash command."""
        async def callback(interaction: discord.Interaction):
            # Use the base command's handle_command method which has proper error handling
            await command_instance.handle_command(interaction, self.container)
        
        return callback
    
    async def _load_server_configs(self):
        """Load server configurations for all connected guilds."""
        logger.info("Loading server configurations...")
        
        try:
            # Get server repository
            server_repo = self.container.get_server_repository()
            
            for guild in self.guilds:
                try:
                    config = await server_repo.get_by_server_id_partition(str(guild.id))
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
            
            # Get guild object to access owner_id
            guild = self.get_guild(guild_id)
            owner_id = str(guild.owner_id) if guild and guild.owner_id else "0"
            
            config = ServerConfig(
                server_id=str(guild_id),
                server_name=guild_name,
                owner_id=owner_id,
                persona=PersonaType.SASSY_REPORTER,  # Default persona
                newsletter_enabled=True,
                newsletter_channel_id=None,  # Will be set by admin
                newsletter_time="09:00",
                newsletter_timezone="UTC"
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
            guild = self.get_guild(guild_id)
            owner_id = str(guild.owner_id) if guild and guild.owner_id else "0"
            return ServerConfig(
                server_id=str(guild_id),
                server_name=guild_name,
                owner_id=owner_id,
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
            msg_model = Message.from_discord_message(message, str(message.guild.id))
            
            # Validate that we have a proper Message model
            if not isinstance(msg_model, Message):
                raise MessageProcessingError("Failed to create proper Message model from Discord message")
            
            # Populate reaction users properly (async operation)
            for reaction_data in msg_model.reactions:
                try:
                    # Find the original reaction and get users
                    discord_reaction = next(
                        (r for r in message.reactions if str(r.emoji) == reaction_data.emoji), 
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
            msg_model.update_metrics()
            
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
            msg_model = await message_repo.get_by_message_id(
                str(reaction.message.id), 
                str(reaction.message.guild.id)
            )
            if msg_model:
                # Add reaction to model
                reaction_model = ReactionData(
                    message_id=str(reaction.message.id),
                    channel_id=str(reaction.message.channel.id),
                    server_id=str(reaction.message.guild.id),
                    author_id=str(user.id),
                    content=str(reaction.emoji),
                    timestamp=reaction.message.created_at.isoformat(),
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
            
            msg_model = await message_repo.get_by_message_id(
                str(reaction.message.id), 
                str(reaction.message.guild.id)
            )
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
    
    
    async def _should_generate_newsletter(self, config: ServerConfig, current_time: datetime) -> bool:
        """Check if it's time to generate a newsletter."""
        # Simplified logic - generate once per day
        # TODO: Implement proper scheduling with timezone support
        
        try:
            newsletter_repo = self.container.get_newsletter_repository()
            
            # Check if we already generated today
            today_date = current_time.date()
            existing_newsletter = await newsletter_repo.get_newsletter_by_date(
                config.server_id, today_date
            )
            
            # No newsletter exists for today - generate one
            if existing_newsletter is None:
                return True
            
            # Check if existing newsletter failed and can be retried
            if hasattr(existing_newsletter, 'status') and existing_newsletter.status == "failed":
                # Check if enough time has passed since last failure (retry every 2 hours)
                if hasattr(existing_newsletter, 'updated_at'):
                    time_since_failure = current_time - existing_newsletter.updated_at
                    if time_since_failure.total_seconds() >= 7200:  # 2 hours
                        logger.info(f"Retrying failed newsletter for server {config.server_id}")
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking newsletter schedule: {e}")
            return False
    
    async def _generate_and_send_newsletter(self, config: ServerConfig):
        """Generate and send a newsletter for a server with retry logic."""
        max_retries = 3
        retry_delay = 5  # seconds
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Generating newsletter for server {config.server_id} (attempt {attempt + 1}/{max_retries})")
                
                # Get recent messages
                message_repo = self.container.get_message_repository()
                cutoff_time = datetime.now() - timedelta(hours=24)
                
                recent_messages = await message_repo.get_by_server_and_time_range(
                    config.server_id, cutoff_time, datetime.now()
                )
                
                if len(recent_messages) < 5:
                    logger.info(f"Insufficient messages for newsletter in server {config.server_id}")
                    return
                
                # Create newsletter object with all required fields
                from src.models.newsletter import Newsletter
                current_time = datetime.now()
                newsletter = Newsletter(
                    server_id=config.server_id,
                    newsletter_date=current_time.date(),
                    title=f"Daily Newsletter - {current_time.strftime('%B %d, %Y')}",
                    time_period_start=cutoff_time,
                    time_period_end=current_time,
                    analyzed_messages_count=len(recent_messages),
                    persona_used=config.persona
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
                    return  # Success - exit retry loop
                
            except Exception as e:
                logger.error(f"Failed to generate newsletter for server {config.server_id} (attempt {attempt + 1}): {e}")
                
                if attempt < max_retries - 1:
                    logger.info(f"Retrying newsletter generation in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.error(f"All {max_retries} attempts failed for newsletter generation in server {config.server_id}")
                    
                    # Create failed newsletter record for retry tracking
                    try:
                        from src.models.newsletter import Newsletter
                        current_time = datetime.now()
                        failed_newsletter = Newsletter(
                            server_id=config.server_id,
                            newsletter_date=current_time.date(),
                            title=f"Failed Newsletter - {current_time.strftime('%B %d, %Y')}",
                            time_period_start=current_time - timedelta(hours=24),
                            time_period_end=current_time,
                            analyzed_messages_count=0,
                            persona_used=config.persona
                        )
                        failed_newsletter.mark_failed(f"Failed after {max_retries} attempts: {str(e)}", True)
                        
                        # Save failed newsletter to database for retry tracking
                        newsletter_repo = self.container.get_newsletter_repository()
                        await newsletter_repo.create(failed_newsletter)
                        logger.info(f"Created failed newsletter record for retry tracking in server {config.server_id}")
                        
                    except Exception as failed_record_error:
                        logger.error(f"Failed to create failed newsletter record: {failed_record_error}")
                    
                    # Send notification about failure to bot updates channel if configured
                    try:
                        if config.bot_updates_channel_id:
                            channel = self.get_channel(int(config.bot_updates_channel_id))
                            if channel:
                                embed = discord.Embed(
                                    title="⚠️ Newsletter Generation Failed",
                                    description=f"Failed to generate newsletter after {max_retries} attempts. Will retry in 2 hours. Error: {str(e)[:200]}",
                                    color=discord.Color.red(),
                                    timestamp=datetime.now()
                                )
                                await channel.send(embed=embed)
                    except Exception as notification_error:
                        logger.error(f"Failed to send newsletter failure notification: {notification_error}")
    
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
            
            embed.set_footer(text=f"Generated by The Snitch • {config.persona.replace('_', ' ').title()}")
            
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
    try:
        settings = get_settings()
        setup_logging(settings)
        
        bot_instance = get_bot()
        
        logger.info("Starting The Snitch Discord Bot...")
        await bot_instance.start(settings.discord_token)
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise