"""
Leak command for The Snitch Discord Bot.
Generates harmless, humorous fake "leaks" about random users.
"""

import discord
from typing import Dict, Any, List, Optional
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
    
    def define_parameters(self) -> Dict[str, Dict[str, Any]]:
        """Define command parameters for Discord."""
        return {
            "persona": {
                "type": str,
                "description": "Choose the personality style for the leak",
                "required": False,
                "default": None,  # Will use server default
                "choices": [
                    "sassy_reporter",
                    "investigative_journalist", 
                    "gossip_columnist",
                    "sports_commentator",
                    "weather_anchor",
                    "conspiracy_theorist"
                ]
            }
        }
    
    async def execute(self, ctx: CommandContext, persona: Optional[str] = None, **kwargs) -> None:
        """Execute the leak command with optional persona selection."""
        
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
            
            # Use enhanced user selector for better random selection
            from src.ai.chains.leak_chains.user_selector import EnhancedUserSelector
            
            user_selector = EnhancedUserSelector(
                min_recent_messages=ctx.server_config.leak_min_user_activity,
                exclude_recent_targets=ctx.server_config.leak_exclude_recent_targets_hours > 0,
                min_message_length=10,
                max_users_to_consider=ctx.server_config.leak_max_context_messages,
                fallback_candidate_limit=15  # Allow up to 15 random users in fallback
            )
            selected_user_info = await user_selector.select_random_user(
                recent_messages=recent_messages,
                command_user_id=ctx.user_id,
                server_id=ctx.guild_id
            )
            
            if not selected_user_info:
                embed = EmbedBuilder.warning(
                    "No Targets Available",
                    "No suitable candidates found from recent activity. Try again when there are more active users! 🕵️"
                )
                await ctx.respond(embed=embed)
                return
            
            # Extract user info from enhanced selector
            target_user_id = selected_user_info["user_id"]
            target_name = selected_user_info["display_name"]
            target_mention = f"<@{target_user_id}>"
            
            logger.info(f"Enhanced user selector chose: {target_name} (ID: {target_user_id}) from {selected_user_info.get('message_count', 0)} recent messages")
            
            # Determine which persona to use
            selected_persona = self._get_selected_persona(persona, ctx.server_config.persona)
            logger.info(f"Using persona: {selected_persona}")
            
            # Generate AI-powered personalized leak
            try:
                settings = ctx.container.get_settings()
                if settings.mock_ai_responses:
                    leak_content = self._generate_mock_leak(target_name, selected_persona, recent_messages)
                else:
                    # Use Groq AI for personalized leaks
                    leak_content = await self._generate_ai_leak(target_name, target_user_id, ctx, recent_messages, selected_persona)
                    from pprint import pprint
                    pprint(leak_content)
            except Exception as ai_error:
                logger.warning(f"AI leak generation failed, falling back to mock: {ai_error}")
                leak_content = self._generate_mock_leak(target_name, selected_persona, recent_messages)
            
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
    
    async def _generate_ai_leak(self, target_name: str, target_user_id: str, ctx: CommandContext, recent_messages: list, persona) -> str:
        """Generate AI-powered personalized leak using Chain of Thoughts approach."""
        try:
            # Check if CoT is enabled for this server
            if ctx.server_config.leak_cot_enabled:
                return await self._generate_ai_leak_with_cot(target_name, target_user_id, ctx, recent_messages, persona)
            else:
                logger.info("CoT disabled for this server, using legacy approach")
                return await self._generate_ai_leak_legacy(target_name, target_user_id, ctx, recent_messages, persona)
        except Exception as e:
            logger.warning(f"CoT leak generation failed, falling back to legacy approach: {e}")
            return await self._generate_ai_leak_legacy(target_name, target_user_id, ctx, recent_messages, persona)

    async def _generate_ai_leak_with_cot(self, target_name: str, target_user_id: str, ctx: CommandContext, recent_messages: list, persona) -> str:
        """Generate AI-powered leak using Chain of Thoughts approach."""
        try:
            from src.ai import get_ai_service
            from src.ai.chains.leak_chains import ContextAnalyzer, ContentPlanner, LeakWriter
            
            ai_service = await get_ai_service()
            
            # Step 1: Context Analysis
            logger.info("CoT Step 1: Analyzing context")
            context_analyzer = ContextAnalyzer(ai_service.llm_client)
            context_analysis = await context_analyzer.analyze_context(
                target_user_id=target_user_id,
                target_name=target_name,
                recent_messages=recent_messages,
                server_config=ctx.server_config
            )
            
            # Step 2: Content Planning
            logger.info("CoT Step 2: Planning content")
            content_planner = ContentPlanner(ai_service.llm_client)
            content_plan = await content_planner.plan_content(
                context_analysis=context_analysis,
                persona=persona,
                content_guidelines=self._get_content_guidelines()
            )
            
            # Step 3: Final Content Writing
            logger.info("CoT Step 3: Writing final content")
            leak_writer = LeakWriter(ai_service.llm_client)
            final_content = await leak_writer.write_leak(
                content_plan=content_plan,
                persona=persona,
                format_requirements=self._get_format_requirements(),
                target_name=target_name
            )
            
            logger.info(f"CoT leak generation completed. Reasoning chain: {len(context_analysis.reasoning)} + {len(content_plan.reasoning)} + {len(final_content.reasoning)} chars")
            
            return final_content.content
            
        except Exception as e:
            logger.error(f"CoT leak generation failed: {e}")
            raise  # Re-raise to trigger fallback

    async def _generate_ai_leak_legacy(self, target_name: str, target_user_id: str, ctx: CommandContext, recent_messages: list, persona) -> str:
        """Legacy AI leak generation (fallback method)."""
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
               "persona": persona
            }
            
            # Create simplified AI prompt for leak generation
            prompt = f"""Create a humorous, harmless "leak" about {target_name} for a Discord server gossip bot.

USER CONTEXT: {target_name} recently active in {context_info['server_name']}
PERSONA: {persona}
RECENT TOPICS: {', '.join(target_messages[-3:]) if target_messages else 'general chat'}

Generate a single, entertaining leak (max 150 characters) that is:
- Completely harmless and appropriate
- Obviously satirical 
- Funny and embarrassing in a wholesome way
- Relevant to the user or server context

Just return the leak content, nothing else."""
            
            leak_content = await ai_service.llm_client.simple_completion(
                prompt=prompt,
                temperature=0.9,
                max_tokens=200
            )
            
            # Clean up the response and ensure it's appropriate length
            leak_content = leak_content.strip()
            if len(leak_content) > 4096:
                # Truncate if too long
                leak_content = leak_content[:4090] + "..."
                
            return leak_content
            
        except Exception as e:
            logger.error(f"Legacy AI leak generation failed: {e}")
            # Final fallback to mock
            return self._generate_mock_leak(target_name, persona, recent_messages)
    
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

    def _get_selected_persona(self, user_choice: Optional[str], server_default):
        """Determine which persona to use based on user choice and server default."""
        if user_choice:
            # Convert user choice string to PersonaType enum
            try:
                from src.models.server import PersonaType
                return PersonaType(user_choice)
            except (ValueError, AttributeError):
                logger.warning(f"Invalid persona choice '{user_choice}', using server default")
                return server_default
        else:
            # Use server default
            return server_default

    def _get_content_guidelines(self) -> Dict[str, Any]:
        """Get content safety and style guidelines for CoT chains."""
        return {
            "max_length": 200,
            "min_length": 20,
            "safety_level": "family_friendly",
            "humor_style": "wholesome_embarrassing",
            "banned_topics": ["nsfw", "harassment", "real_drama", "personal_attacks"],
            "encouraged_topics": ["gaming", "social_mishaps", "hobby_obsessions", "personality_quirks"],
            "tone_requirements": ["obviously_fake", "harmless", "community_friendly"]
        }

    def _get_format_requirements(self) -> Dict[str, Any]:
        """Get format requirements for final content."""
        return {
            "max_characters": 200,
            "include_emojis": True,
            "style": "gossip_leak",
            "target_audience": "discord_community",
            "obviousness_level": "clearly_satirical"
        }


# Register the command
from src.discord_bot.commands.base import command_registry
command_registry.register(LeakCommand())