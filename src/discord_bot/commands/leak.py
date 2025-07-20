"""
Leak command for The Snitch Discord Bot.
Generates harmless, humorous fake "leaks" about random users.
"""

import discord
from typing import Dict, Any, List
import random
from datetime import datetime, timedelta

from src.discord_bot.commands.base import PublicCommand, CommandContext, EmbedBuilder
from src.core.logging import get_logger

logger = get_logger(__name__)


class LeakCommand(PublicCommand):
    """Command to generate humorous fake leaks about users."""
    
    def __init__(self):
        super().__init__(
            name="leak",
            description="Generate a harmless, fake 'leak' about a random active user",
            cooldown_seconds=20  # Higher cooldown to prevent spam
        )
    
    async def execute(self, ctx: CommandContext, **kwargs) -> None:
        """Execute the leak command."""
        
        logger.info(
            "Leak command executed",
            user_id=ctx.user_id,
            guild_id=ctx.guild_id,
            channel_id=ctx.channel_id
        )
        
        try:
            # Get recent messages directly from Discord channel
            cutoff_time = datetime.now() - timedelta(hours=1)
            channel = ctx.interaction.client.get_channel(int(ctx.channel_id))
            if not channel:
                embed = EmbedBuilder.error(
                    "Channel Error",
                    "Could not access the current channel."
                )
                await ctx.respond(embed=embed)
                return
            
            # Fetch recent messages from the channel
            recent_messages = []
            async for message in channel.history(limit=100, after=cutoff_time):
                recent_messages.append(message)
            
            # Collect unique active users (excluding bots and the command user)
            active_users = set()
            for msg in recent_messages:
                # Skip bots and the user who ran the command
                if (not msg.author.bot and 
                    str(msg.author.id) != ctx.user_id):
                    active_users.add(str(msg.author.id))
            
            if not active_users:
                embed = EmbedBuilder.warning(
                    "No Targets Available",
                    "No recent activity detected. Try again when there are more active users! 🕵️"
                )
                await ctx.respond(embed=embed)
                return
            
            # Select random user
            target_user_id = random.choice(list(active_users))
            
            # Get user info
            try:
                target_user = ctx.guild.get_member(int(target_user_id))
                if not target_user:
                    # Try to fetch from Discord
                    target_user = await ctx.interaction.client.fetch_user(int(target_user_id))
                
                target_name = target_user.display_name if hasattr(target_user, 'display_name') else target_user.name
                target_mention = f"<@{target_user_id}>"
            except:
                target_name = f"User-{target_user_id[:8]}"
                target_mention = f"<@{target_user_id}>"
            
            # Generate fake leak
            leak_content = self._generate_leak(target_name, ctx.server_config.persona.value)
            
            # Create leak embed
            embed = discord.Embed(
                title="🕵️ EXCLUSIVE LEAK",
                description=f"**LEAKED INTEL ON {target_mention}**\n\n{leak_content}",
                color=discord.Color.dark_theme(),
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="🔒 Source",
                value="Anonymous Whistleblower",
                inline=True
            )
            
            embed.add_field(
                name="📊 Reliability",
                value=f"{random.randint(12, 99)}% Sus",
                inline=True
            )
            
            embed.add_field(
                name="⚠️ Disclaimer",
                value="*This is completely fabricated for entertainment purposes*",
                inline=False
            )
            
            embed.set_footer(
                text="🤐 The Snitch • Leaking fake news since today",
                icon_url=ctx.interaction.client.user.avatar.url if ctx.interaction.client.user.avatar else None
            )
            
            await ctx.respond(embed=embed)
            
            # Add mysterious emoji reaction
            try:
                await ctx.interaction.message.add_reaction("🤐")
            except:
                pass
            
            logger.info(
                "Leak generated successfully",
                user_id=ctx.user_id,
                guild_id=ctx.guild_id,
                target_user_id=target_user_id,
                leak_length=len(leak_content)
            )
            
        except Exception as e:
            embed = EmbedBuilder.error(
                "Leak Failed",
                "The leak was... leaked. Try again later! 🕳️"
            )
            await ctx.respond(embed=embed)
            logger.error(f"Error in leak command: {e}", exc_info=True)
    
    def _generate_leak(self, target_name: str, persona: str) -> str:
        """Generate a humorous fake leak about a user."""
        
        # Different leak templates based on persona
        leak_templates = {
            'sassy_reporter': [
                f"Sources confirm {target_name} has been secretly {random.choice(['binge-watching anime', 'collecting rubber ducks', 'practicing interpretive dance', 'learning to yodel', 'building a pillow fort empire'])} for the past {random.randint(2, 30)} days straight. 💅",
                f"BREAKING: {target_name} allegedly {random.choice(['ate pineapple on pizza', 'uses light mode Discord', 'puts milk before cereal', 'double-dips chips', 'leaves one second on the microwave'])}. The audacity! 😱",
                f"Tea has been spilled! 🍵 Insider reports {target_name} once {random.choice(['googled how to google', 'tried to pause an online game', 'asked Siri if she was single', 'waved at someone waving behind them', 'pushed a pull door for 5 minutes'])}.",
                f"Exclusive leak: {target_name} secretly {random.choice(['writes fanfiction about kitchen appliances', 'names all their plants', 'talks to their reflection', 'has a lucky rubber chicken', 'sleeps with a nightlight shaped like a taco'])}. We have questions! 🤔"
            ],
            'investigative_journalist': [
                f"After months of investigation, sources reveal {target_name} has been {random.choice(['operating an underground cookie empire', 'training carrier pigeons', 'developing a time machine in their garage', 'secretly learning ancient languages', 'mapping the migration patterns of dust bunnies'])}.",
                f"Confidential documents suggest {target_name} once {random.choice(['spent 3 hours trying to catch a wifi signal', 'got lost in their own neighborhood', 'argued with a smart TV', 'tried to high-five their reflection', 'bought a lottery ticket with birthday candle numbers'])}.",
                f"Investigation reveals: {target_name} allegedly {random.choice(['keeps a diary written entirely in emoji', 'has named their Wi-Fi router', 'practices acceptance speeches in the shower', 'uses a calculator to calculate calculator functions', 'owns 47 different rubber bands for mysterious purposes'])}.",
                f"Breaking investigation: Multiple sources confirm {target_name} {random.choice(['once tried to friend request their own alt account', 'bought a plant just to have someone to talk to', 'has a secret handshake with their coffee maker', 'rates their meals on Yelp even when cooking at home', 'apologizes to furniture when they bump into it'])}."
            ],
            'sports_commentator': [
                f"BREAKING NEWS FROM THE FIELD! {target_name} has been spotted {random.choice(['doing victory dances after opening jars', 'trash-talking NPCs in single-player games', 'celebrating goals scored in FIFA like they are real', 'high-fiving their pet after successful treats', 'doing play-by-play commentary while cooking'])}! What a legend! 🏆",
                f"AND HERE COMES {target_name.upper()} WITH THE PLAY OF THE CENTURY! Sources say they {random.choice(['once scored a perfect game of solitaire', 'achieved a high score in typing tests', 'won an argument with autocorrect', 'successfully untangled earbuds on the first try', 'parallel parked in one attempt'])}! UNBELIEVABLE! 🎯",
                f"LADIES AND GENTLEMEN, we have confirmation that {target_name} {random.choice(['practices their signature for when they become famous', 'does touchdown dances after successfully opening packages', 'celebrates personal victories with air guitar solos', 'has a victory playlist for completing mundane tasks', 'treats grocery shopping like a competitive sport'])}! THE CROWD GOES WILD! 📣",
                f"EXCLUSIVE SPORTS LEAK! {target_name} has been {random.choice(['training for the Olympics of procrastination', 'perfecting their victory speech for winning arguments in the shower', 'practicing their game face in mirrors', 'developing strategies for competitive Netflix watching', 'coaching their houseplants to grow faster'])}! WHAT DEDICATION! 💪"
            ],
            'conspiracy_theorist': [
                f"WAKE UP SHEEPLE! {target_name} is clearly {random.choice(['an agent for Big Cereal', 'secretly communicating with pigeons', 'part of the underground sock puppet mafia', 'a time traveler from the age of dial-up internet', 'working for the Department of Lost Socks'])}! The signs are everywhere! 👁️",
                f"THE TRUTH IS OUT THERE! Sources deep within the system reveal {target_name} {random.choice(['knows the real reason why hot dogs come in packs of 10 but buns in packs of 8', 'has been hoarding USB cables for the apocalypse', 'can communicate with printers and make them work', 'knows where all the missing Tupperware lids go', 'has the real explanation for why there is always that one sock missing'])}! 🛸",
                f"GOVERNMENT COVER-UP EXPOSED! {target_name} allegedly {random.choice(['discovered the secret to making printers work on the first try', 'knows the location of the missing area between floors in elevators', 'has photographic evidence of functioning ice cream machines', 'possesses the ancient knowledge of how to fold fitted sheets', 'holds the key to understanding why traffic is always worse in the other lane'])}! 🔍",
                f"THE ILLUMINATI DOESN'T WANT YOU TO KNOW: {target_name} has been {random.choice(['secretly organizing the migration patterns of shopping carts', 'controlling the algorithm that decides which sock goes missing', 'part of the conspiracy to make all USB plugs require 3 attempts', 'behind the plot to make every group project have one person who does nothing', 'orchestrating the great mystery of why phone chargers disappear'])}! COINCIDENCE? I THINK NOT! 🎭"
            ]
        }
        
        # Default template for unknown personas
        default_templates = [
            f"Leaked: {target_name} apparently {random.choice(['collects funny-shaped rocks', 'names their houseplants', 'practices conversations in the mirror', 'has strong opinions about cereal', 'owns more phone chargers than phones'])}.",
            f"Sources say {target_name} once {random.choice(['spent an hour looking for their phone while holding it', 'tried to push a door that said pull', 'googled Google', 'forgot their own password immediately after changing it', 'waved back at someone waving behind them'])}.",
            f"Breaking: {target_name} secretly {random.choice(['talks to their plants', 'has a lucky pen', 'practices their autograph', 'counts steps while walking', 'saves memes but never shares them'])}.",
            f"Exclusive: Multiple sources confirm {target_name} {random.choice(['apologizes to inanimate objects', 'has full conversations with their pets', 'makes sound effects while doing mundane tasks', 'celebrates small victories with personal victory dances', 'uses calculators for simple math'])}."
        ]
        
        # Get templates for the current persona or use default
        templates = leak_templates.get(persona, default_templates)
        
        return random.choice(templates)


# Register the command
from src.discord_bot.commands.base import command_registry
command_registry.register(LeakCommand())