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
            async for message in channel.history(limit=200):
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
            
            # Generate AI-powered personalized leak
            try:
                settings = ctx.container.get_settings()
                if settings.mock_ai_responses:
                    leak_content = self._generate_mock_leak(target_name, ctx.server_config.persona, recent_messages)
                else:
                    # Use Groq AI for personalized leaks
                    leak_content = await self._generate_ai_leak(target_name, target_user_id, ctx, recent_messages)
                    from pprint import pprint
                    pprint(leak_content)
            except Exception as ai_error:
                logger.warning(f"AI leak generation failed, falling back to mock: {ai_error}")
                leak_content = self._generate_mock_leak(target_name, ctx.server_config.persona, recent_messages)
            
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
            
            # Send to configured output channel or current channel
            from src.discord_bot.utils.channel_utils import send_to_output_channel
            await send_to_output_channel(
                ctx, 
                embed, 
                "The leak has been delivered"
            )
            
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
    
    async def _generate_ai_leak(self, target_name: str, target_user_id: str, ctx: CommandContext, recent_messages: list) -> str:
        """Generate AI-powered personalized leak using Groq."""
        try:
            from src.ai import get_ai_service
            ai_service = await get_ai_service()
            
            # Analyze target user's recent messages for context
            target_messages = []
            for msg in recent_messages[-50:]:  # Last 50 messages
                if str(msg.author.id) == target_user_id:
                    target_messages.append(msg.content)
            
            # Get context about other active users for potential mentions
            other_users = {}
            for msg in recent_messages[-30:]:  # Last 30 messages for context
                if not msg.author.bot and str(msg.author.id) != target_user_id:
                    user_name = msg.author.display_name if hasattr(msg.author, 'display_name') else msg.author.name
                    if user_name not in other_users:
                        other_users[user_name] = []
                    other_users[user_name].append(msg.content[:100])  # Truncate for context
            
            # Build context for AI
            context_info = {
                "target_name": target_name,
                "target_messages": target_messages[-10:],  # Last 5 messages from target
                "other_users": dict(list(other_users.items())[:10]),  # Top 3 other active users
                "server_name": ctx.interaction.guild.name if ctx.interaction.guild else "this server",
               "persona": ctx.server_config.persona
            }
            
            # Create AI prompt for leak generation
            prompt = f"""Create a humorous, harmless "leak" about {target_name} for a Discord server gossip bot called "The Snitch". 
"Alright, Snitch Squad! 🕵️‍♀️ It's time to spill some piping hot, totally innocent tea for "The Snitch" gossip bot on our Discord server! Your mission, should you choose to accept it, is to cook up a hilarious, slightly embarrassing, but *completely harmless* "leak" about {target_name}.

**Here's the 411:**
-   **Length:** Keep it short and sweet, max 20-30 words. We're talking quick, punchy gossip that hits different.
-   **Vibe Check:** This *has* to be innocent, fun, and embarrassing in the most wholesome way. Absolutely NO cussing, sexual content, or anything inappropriate. Think "OMG, I can't believe they did that!" not "OMG, they're cancelled!"
-   **Maturity:** It's cool to hint at light 18+ themes like crushes, dating fails, or awkward romantic situations, but keep it super classy and tasteful. A bit spicy deets! But not crossing limits
-   **Authenticity:** Make it sound like genuine, juicy (but obviously fake) server gossip.
-   **Slang Game Strong:** Inject some current internet slang and youth-speak naturally. Think "rizz," "simp," "bet," "no cap," "it's giving," "main character energy," "IYKYK," "glow up," "ratio'd," etc. (use sparingly and organically).

**TOPIC DRAFT - LET'S DIVERSIFY THE TEA!**
We need a *wide variety* of topics, so **DO NOT** give excessive weight to just one area (like gaming or Discord habits). Mix it up! Here are some ideas to get your gossip gears turning:
-   Funny social media blunders or attempts at viral trends (e.g., a failed TikTok dance, an embarrassing Insta story, getting ratio'd on Twitter).
-   Awkward real-life encounters or public mishaps (e.g., tripping in public, mispronouncing a word in a cringe way, getting caught singing off-key).
-   Relatable dating/crush drama (e.g., getting ghosted by their crush, a hilarious first date fail, a secret crush reveal gone wrong—keep it light and funny!).
-   Obsessions with pop culture (e.g., binging a super cheesy show, stanning a niche artist, having a weird fan theory, being obsessed with a meme).
-   Quirky personal habits or fashion choices (e.g., always wearing mismatched socks, having a secret love for Crocs, a questionable fashion "glow up" attempt).
-   Silly Discord behaviors (e.g., accidentally muting themselves mid-rant, spamming ancient emojis, falling asleep on voice chat).
-   Hilarious social interactions with other server members (e.g., {target_name} trying to impress {other_active_members[0]} and failing spectacularly, a funny misunderstanding with {other_active_members[1]}).

**SERVER CONTEXT (for personalization):**
-   **Target:** {target_name}
-   **Server Name:** {context_info['server_name']}
-   **Recent Activity Patterns (if available):** {', '.join(target_messages[-10:]) if target_messages else 'minimal activity'}
-   **Other Active Members (if available):** {', '.join(list(other_users.keys())[:10]) if other_users else 'none'}

Your final output should be a single, entertaining, and harmless gossip leak. Make it server-specific and personalized based on the context provided.

"""
            # Get AI response
        #     content: str,
        # analysis_type: str,
        # context: Optional[str] = None,
        # model: Optional[str] = None
            leak_content = await ai_service.groq_client.simple_completion(
                prompt=prompt,
                temperature=0.9,
                max_tokens=500
            )
            
            # Clean up the response and ensure it's appropriate length
            leak_content = leak_content.strip()
            if len(leak_content) > 4096:
                # Truncate if too long
                leak_content = leak_content[:4090] + "..."
                
            return leak_content
            
        except Exception as e:
            logger.error(f"AI leak generation failed: {e}")
            # Fallback to mock
            return self._generate_mock_leak(target_name, ctx.server_config.persona, recent_messages)
    
    def _generate_mock_leak(self, target_name: str, persona: str, recent_messages: list) -> str:
        """Generate a humorous fake leak about a user with some personalization."""
        
        # Try to get some context from recent messages
        topics_mentioned = []
        other_users = []
        for msg in recent_messages[-20:]:
            if not msg.author.bot:
                # Extract potential topics/interests
                content_lower = msg.content.lower()
                for topic in ['gaming', 'anime', 'music', 'food', 'work', 'school', 'netflix', 'movies', 'coffee', 'pizza']:
                    if topic in content_lower and topic not in topics_mentioned:
                        topics_mentioned.append(topic)
                
                # Collect other user names for potential mentions
                user_name = msg.author.display_name if hasattr(msg.author, 'display_name') else msg.author.name
                if user_name != target_name and user_name not in other_users and len(other_users) < 3:
                    other_users.append(user_name)
        
        # Enhanced leak templates with personalization hooks
        topic = random.choice(topics_mentioned) if topics_mentioned else random.choice(['gaming', 'snacks', 'memes', 'music'])
        other_user = random.choice(other_users) if other_users else "someone"
        
        leak_templates = {
            'sassy_reporter': [
                f"Tea has been SPILLED! 🍵 {target_name} was caught {random.choice(['sliding into DMs about', 'obsessing over', 'secretly judging people who dont like', 'writing love letters to', 'dreaming about'])} {topic}. The dedication is real! 💅",
                f"BREAKING: Multiple sources confirm {target_name} {random.choice(['has a secret crush on', 'starts arguments with', 'gets way too competitive with', 'sends memes to at 3AM', 'practices pickup lines on'])} {other_user}. Were here for this drama! 😱",
                f"Exclusive scoop: {target_name} allegedly {random.choice(['cried watching', 'spent their rent money on', 'stays up all night thinking about', 'has strong opinions about', 'writes fanfiction involving'])} {topic}. No shame in that game, hun! 💁‍♀️",
                f"Sources say {target_name} once {random.choice(['embarrassed themselves in front of', 'tried to impress', 'got roasted by', 'accidentally confessed their love to', 'challenged to a duel'])} {other_user} over {topic}. The secondhand embarrassment! 🤭"
            ],
            'investigative_journalist': [
                f"INVESTIGATION COMPLETE: After extensive analysis, sources confirm {target_name} has been {random.choice(['conducting secret research on', 'building a shrine dedicated to', 'writing detailed analysis reports about', 'creating conspiracy theories involving', 'collecting evidence about'])} {topic}. The implications are staggering.",
                f"Classified documents reveal {target_name} {random.choice(['maintains a secret alliance with', 'has been exchanging coded messages with', 'shares classified intel with', 'plots world domination with', 'practices synchronized activities with'])} {other_user}. Further investigation required.",
                f"Breaking investigation: {target_name} allegedly {random.choice(['keeps detailed logs of', 'has photographic evidence of', 'maintains secret files on', 'conducts surveillance of', 'has insider knowledge about'])} {topic} activities. Sources remain anonymous for safety.",
                f"CONFIDENTIAL REPORT: Multiple witnesses confirm {target_name} {random.choice(['holds secret meetings about', 'leads underground discussions on', 'organizes clandestine activities involving', 'masterminds elaborate schemes regarding', 'coordinates covert operations related to'])} {topic}."
            ],
            'sports_commentator': [
                f"AND {target_name.upper()} COMES IN WITH THE CHAMPIONSHIP MOVE! They've been {random.choice(['dominating the leaderboards in', 'training intensively for', 'setting new records in', 'going undefeated in', 'becoming the undisputed champion of'])} {topic}! THE CROWD IS ON THEIR FEET! 🏆",
                f"LADIES AND GENTLEMEN, {target_name.upper()} WITH THE PLAY OF THE SEASON! Sources confirm they {random.choice(['defeated', 'completely destroyed', 'schooled', 'obliterated in competition', 'left speechless'])} {other_user} in {topic}! WHAT A LEGENDARY PERFORMANCE! 🎯",
                f"BREAKING SPORTS NEWS! {target_name} has been caught {random.choice(['practicing victory speeches for', 'doing celebration dances about', 'trash-talking opponents in', 'studying film footage of', 'developing new strategies for'])} {topic}! THE DEDICATION IS UNREAL! 📣",
                f"EXCLUSIVE CHAMPIONSHIP LEAK! Multiple witnesses saw {target_name} {random.choice(['carrying good luck charms for', 'performing pre-game rituals involving', 'coaching others in the art of', 'holding secret training sessions for', 'establishing dominance in'])} {topic}! PURE ATHLETICISM! 💪"
            ],
            'conspiracy_theorist': [
                f"WAKE UP SHEEPLE! {target_name} is CLEARLY part of the {topic.upper()} ILLUMINATI! They've been {random.choice(['secretly controlling', 'manipulating the algorithms of', 'spreading propaganda about', 'conducting mind control experiments with', 'organizing the underground society of'])} {topic}! THE EVIDENCE IS EVERYWHERE! 👁️",
                f"THE TRUTH ABOUT {target_name.upper()} IS OUT THERE! Deep state sources reveal they {random.choice(['have classified intel on', 'maintain secret communications about', 'control the hidden networks of', 'possess forbidden knowledge of', 'orchestrate global conspiracies involving'])} {topic}! COINCIDENCE? I THINK NOT! 🛸",
                f"GOVERNMENT COVER-UP EXPOSED! {target_name} and {other_user} are OBVIOUSLY {random.choice(['co-conspirators in the', 'double agents working for', 'secret operatives of the', 'founding members of the', 'puppet masters behind the'])} {topic} conspiracy! THEY DON'T WANT YOU TO KNOW! 🔍",
                f"BREAKING: THE {topic.upper()} CONSPIRACY IS REAL! {target_name} has been {random.choice(['planting subliminal messages about', 'recruiting new members through', 'funding secret operations involving', 'decoding ancient prophecies about', 'preparing for the uprising of'])} {topic}! CONNECT THE DOTS, PEOPLE! 🎭"
            ]
        }
        
        # Default template for unknown personas
        default_templates = [
            f"LEAKED: {target_name} has been secretly {random.choice(['obsessing over', 'writing poetry about', 'creating elaborate theories involving', 'collecting rare items related to', 'practicing rituals centered around'])} {topic}. The evidence is mounting!",
            f"Sources confirm {target_name} and {other_user} have been {random.choice(['plotting something involving', 'sharing secret knowledge about', 'competing fiercely over', 'bonding over their mutual love of', 'forming an alliance based on'])} {topic}. Suspicious!",
            f"Breaking: {target_name} allegedly {random.choice(['has a secret stash of', 'dreams about', 'judges people based on their', 'keeps detailed records of', 'practices daily meditation with'])} {topic}. The truth is out there!",
            f"Exclusive: Multiple witnesses report {target_name} {random.choice(['gets emotional about', 'starts heated debates over', 'has strong spiritual connections to', 'plans their entire day around', 'finds deep meaning in'])} {topic}. No comment from the subject."
        ]
        
        # Get templates for the current persona or use default
        templates = leak_templates.get(persona, default_templates)
        
        return random.choice(templates)


# Register the command
from src.discord_bot.commands.base import command_registry
command_registry.register(LeakCommand())