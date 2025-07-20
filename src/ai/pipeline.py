"""
AI Pipeline orchestration for The Snitch Discord Bot.
Coordinates the full RAG/CoT newsletter generation process.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging

from src.ai.groq_client import GroqClient
from src.ai.chains.news_desk import NewsDeskChain
from src.ai.chains.editor_chief import EditorChiefChain
from src.ai.chains.star_reporter import StarReporterChain
from src.models.message import Message
from src.models.server import ServerConfig, PersonaType
from src.models.newsletter import Newsletter, StoryData
from src.core.exceptions import AIServiceError, InsufficientContentError
from src.core.logging import get_logger, log_performance

logger = get_logger(__name__)


class NewsletterPipeline:
    """Complete AI pipeline for newsletter generation using RAG and CoT approach."""
    
    def __init__(self, groq_client: GroqClient):
        self.groq_client = groq_client
        
        # Initialize the three chains
        self.news_desk = NewsDeskChain(groq_client)
        self.editor_chief = EditorChiefChain(groq_client)
        self.star_reporter = StarReporterChain(groq_client)
    
    @log_performance("newsletter_generation")
    async def generate_newsletter(
        self,
        messages: List[Message],
        server_config: ServerConfig,
        newsletter: Newsletter,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> Newsletter:
        """
        Generate a complete newsletter using the three-chain RAG/CoT pipeline.
        
        Args:
            messages: List of messages to analyze (last 24 hours)
            server_config: Server configuration including persona
            newsletter: Newsletter object to populate
            additional_context: Additional context for generation
            
        Returns:
            Completed newsletter with generated content
        """
        try:
            # Validate inputs
            if not messages:
                raise InsufficientContentError(
                    server_config.server_id,
                    0,
                    "No messages provided for newsletter generation"
                )
            
            # Filter messages based on server configuration
            filtered_messages = self._filter_messages(messages, server_config)
            
            if len(filtered_messages) < 5:
                raise InsufficientContentError(
                    server_config.server_id,
                    len(filtered_messages),
                    "Insufficient messages for meaningful newsletter generation"
                )
            
            logger.info(
                "Starting newsletter generation pipeline",
                server_id=server_config.server_id,
                total_messages=len(messages),
                filtered_messages=len(filtered_messages),
                persona=server_config.persona
            )
            
            # Update newsletter status
            newsletter.start_generation(server_config.persona)
            newsletter.analyzed_messages_count = len(filtered_messages)
            
            # CHAIN A: News Desk - Identify potential stories
            logger.info("Executing Chain A: News Desk")
            potential_stories = await self.news_desk.identify_stories(
                messages=filtered_messages,
                persona=server_config.persona,
                max_stories=5
            )
            
            if not potential_stories:
                raise InsufficientContentError(
                    server_config.server_id,
                    len(filtered_messages),
                    "No newsworthy stories identified from messages"
                )
            
            # CHAIN B: Editor-in-Chief - Select headline story
            logger.info("Executing Chain B: Editor-in-Chief")
            selected_story = await self.editor_chief.select_headline(
                story_candidates=potential_stories,
                persona=server_config.persona,
                server_context=self._build_server_context(server_config, additional_context)
            )
            
            # CHAIN C: Star Reporter - Write final article
            logger.info("Executing Chain C: Star Reporter")
            newsletter_content = await self.star_reporter.write_article(
                selected_story=selected_story,
                persona=server_config.persona,
                source_messages=filtered_messages,
                server_context=self._build_server_context(server_config, additional_context)
            )
            
            # Create story data object
            featured_story = StoryData(
                story_id=f"story_{newsletter.id}_{datetime.now().strftime('%Y%m%d')}",
                headline=selected_story.get("suggested_headline", selected_story.get("headline", "Community Update")),
                summary=selected_story.get("summary", ""),
                full_content=newsletter_content,
                source_messages=selected_story.get("related_message_ids", []),
                primary_channel_id=self._get_primary_channel(filtered_messages),
                involved_users=self._get_involved_users(filtered_messages),
                controversy_score=selected_story.get("average_controversy", 0.0),
                engagement_score=selected_story.get("total_engagement", 0.0),
                relevance_score=selected_story.get("story_score", 0.0),
                generated_by_chain="full_pipeline",
                generation_prompt=f"Generated using {server_config.persona} persona",
                generation_timestamp=datetime.now()
            )
            
            # Update newsletter with generated content
            newsletter.featured_story = featured_story
            newsletter.title = f"Daily Dispatch - {newsletter.newsletter_date.strftime('%B %d, %Y')}"
            newsletter.introduction = self._generate_introduction(server_config.persona)
            newsletter.conclusion = self._generate_conclusion(server_config.persona)
            
            # Add additional stories if available
            for story_data in potential_stories[1:4]:  # Add up to 3 additional stories
                if story_data != selected_story:
                    brief_story = f"**{story_data.get('headline', 'Update')}**: {story_data.get('summary', 'Community discussion')[:100]}..."
                    newsletter.add_brief_mention(brief_story)
            
            # Mark generation as complete
            newsletter.complete_generation()
            
            logger.info(
                "Newsletter generation completed successfully",
                server_id=server_config.server_id,
                newsletter_id=newsletter.id,
                headline=featured_story.headline,
                content_length=len(newsletter_content),
                additional_stories=len(newsletter.brief_mentions)
            )
            
            return newsletter
        
        except InsufficientContentError:
            newsletter.mark_failed("Insufficient content for newsletter generation", True)
            raise
        
        except Exception as e:
            error_msg = f"Newsletter generation failed: {str(e)}"
            newsletter.mark_failed(error_msg, True)
            logger.error(error_msg, exc_info=True)
            raise AIServiceError(error_msg)
    
    @log_performance("breaking_news_generation")
    async def generate_breaking_news(
        self,
        messages: List[Message],
        persona: PersonaType,
        channel_context: Optional[str] = None
    ) -> str:
        """
        Generate a breaking news bulletin from recent messages.
        
        Args:
            messages: Recent messages to analyze
            persona: Bot persona for writing style
            channel_context: Optional context about the channel
            
        Returns:
            Breaking news bulletin text
        """
        try:
            if not messages:
                raise InsufficientContentError("unknown", 0, "No messages for breaking news")
            
            # Use star reporter to generate breaking news
            bulletin = await self.star_reporter.generate_breaking_news(
                messages=messages,
                persona=persona,
                context=channel_context
            )
            
            logger.info(
                "Breaking news generated",
                message_count=len(messages),
                persona=persona,
                bulletin_length=len(bulletin)
            )
            
            return bulletin
        
        except Exception as e:
            logger.error(f"Breaking news generation failed: {e}")
            raise AIServiceError(f"Breaking news generation failed: {e}")
    
    async def analyze_content(
        self,
        content: str,
        analysis_types: List[str],
        context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze content for various attributes using AI.
        
        Args:
            content: Content to analyze
            analysis_types: Types of analysis to perform
            context: Optional context for analysis
            
        Returns:
            Analysis results dictionary
        """
        try:
            results = {}
            
            for analysis_type in analysis_types:
                try:
                    result = await self.groq_client.analyze_content(
                        content=content,
                        analysis_type=analysis_type,
                        context=context
                    )
                    results[analysis_type] = result
                    
                except Exception as e:
                    logger.warning(f"Analysis type {analysis_type} failed: {e}")
                    results[analysis_type] = {"error": str(e), "score": 0.0}
            
            return results
        
        except Exception as e:
            logger.error(f"Content analysis failed: {e}")
            raise AIServiceError(f"Content analysis failed: {e}")
    
    def _filter_messages(self, messages: List[Message], server_config: ServerConfig) -> List[Message]:
        """Filter messages based on server configuration."""
        
        filtered = []
        
        for message in messages:
            # Skip if excluded from analysis
            if message.excluded_from_analysis:
                continue
            
            # Check channel whitelist
            if not server_config.is_channel_whitelisted(message.channel_id):
                continue
            
            # Check blacklisted words
            content_lower = message.content.lower()
            if any(word.lower() in content_lower for word in server_config.blacklisted_words):
                continue
            
            # Skip very short messages
            if len(message.content.strip()) < 10:
                continue
            
            # Skip messages that are just links or mentions
            words = message.content.split()
            if len(words) <= 2 and all(
                word.startswith(('http', 'www', '<@', '<#')) for word in words
            ):
                continue
            
            filtered.append(message)
        
        # Sort by relevance (engagement + controversy + recency)
        def relevance_score(msg: Message) -> float:
            recency_hours = (datetime.now() - msg.timestamp).total_seconds() / 3600
            recency_factor = max(0, 1 - (recency_hours / 24))  # Decay over 24 hours
            
            return (
                msg.calculate_engagement_score() * 0.4 +
                msg.controversy_score * 0.3 +
                recency_factor * 0.3
            )
        
        filtered.sort(key=relevance_score, reverse=True)
        
        # Limit to max messages for analysis
        max_messages = min(server_config.max_messages_analysis, 500)  # Hard cap at 500
        return filtered[:max_messages]
    
    def _build_server_context(
        self,
        server_config: ServerConfig,
        additional_context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build context dictionary for AI processing."""
        
        context = {
            "server_name": server_config.server_name,
            "persona": server_config.persona,
            "features_enabled": {
                "breaking_news": server_config.breaking_news_enabled,
                "fact_check": server_config.fact_check_enabled,
                "leak_command": server_config.leak_command_enabled,
                "tip_submission": server_config.tip_submission_enabled
            },
            "community_size": "unknown",  # Could be populated from Discord data
            "server_age": "unknown"       # Could be calculated from creation date
        }
        
        if additional_context:
            context.update(additional_context)
        
        return context
    
    def _get_primary_channel(self, messages: List[Message]) -> str:
        """Get the primary channel ID from messages."""
        if not messages:
            return ""
        
        # Count messages by channel
        channel_counts = {}
        for msg in messages:
            channel_counts[msg.channel_id] = channel_counts.get(msg.channel_id, 0) + 1
        
        # Return channel with most messages
        return max(channel_counts.keys(), key=lambda cid: channel_counts[cid])
    
    def _get_involved_users(self, messages: List[Message]) -> List[str]:
        """Get list of users involved in the story."""
        users = set()
        
        # Get users from messages, prioritizing those with high engagement
        for msg in messages:
            users.add(msg.author_id)
            
            # Stop at reasonable number
            if len(users) >= 20:
                break
        
        return list(users)
    
    def _generate_introduction(self, persona: PersonaType) -> str:
        """Generate persona-appropriate newsletter introduction."""
        
        intros = {
            PersonaType.SASSY_REPORTER: "Hey beautiful people! ✨ Your favorite reporter is back with the hottest tea from around the server. Grab your favorite beverage because we're about to dive into today's drama! ☕",
            
            PersonaType.INVESTIGATIVE_JOURNALIST: "Good day, community members. Following extensive analysis of server activity, we present today's most significant developments and their implications for our community.",
            
            PersonaType.GOSSIP_COLUMNIST: "Darlings! 💅 The gossip desk has been BUSY today, and honey, do we have some juicy updates for you! Pull up a chair because the tea is piping hot! ☕✨",
            
            PersonaType.SPORTS_COMMENTATOR: "WELCOME BACK TO THE DAILY DISPATCH! 📣 Your favorite commentator here with today's play-by-play from the community arena! It's been an EXCITING day folks, so buckle up! 🏟️",
            
            PersonaType.WEATHER_ANCHOR: "Good morning! 🌤️ Today's community forecast shows active discussion patterns with a high chance of engaging conversations. Let's dive into the current conditions across our server landscape.",
            
            PersonaType.CONSPIRACY_THEORIST: "Wake up, sheeple! 👁️ The signs are everywhere if you know how to read them. Today's dispatch reveals the hidden patterns in our community's digital interactions. Connect the dots! 🕵️"
        }
        
        return intros.get(persona, "Welcome to today's community update! Here's what's been happening around the server.")
    
    def _generate_conclusion(self, persona: PersonaType) -> str:
        """Generate persona-appropriate newsletter conclusion."""
        
        conclusions = {
            PersonaType.SASSY_REPORTER: "And that's the tea for today, lovelies! ☕ Keep those conversations spicy and remember - your girl is always watching! 👀 Until tomorrow's drama unfolds... 💋",
            
            PersonaType.INVESTIGATIVE_JOURNALIST: "This concludes today's community analysis. Continue to engage thoughtfully and we'll return tomorrow with fresh insights from your ongoing discussions.",
            
            PersonaType.GOSSIP_COLUMNIST: "That's all the gossip that's fit to print, darlings! 💅 Keep serving those looks and those takes - mama needs content for tomorrow! Stay fabulous! ✨",
            
            PersonaType.SPORTS_COMMENTATOR: "AND THAT'S A WRAP on today's community action! 🏆 Great plays all around, team! Keep bringing that energy and we'll see you tomorrow for more THRILLING coverage! 📣",
            
            PersonaType.WEATHER_ANCHOR: "That's your community weather update for today! 🌤️ Tomorrow's forecast calls for continued engagement with scattered discussions throughout the day. Stay connected! 📡",
            
            PersonaType.CONSPIRACY_THEORIST: "The patterns are clear for those who seek the truth! 🔍 Keep your eyes open, question everything, and remember - the real story is always deeper than it appears! Stay woke! 👁️"
        }
        
        return conclusions.get(persona, "That's all for today's update! Thanks for staying engaged with the community. See you tomorrow!")


# Global pipeline instance
_newsletter_pipeline: Optional[NewsletterPipeline] = None


async def get_newsletter_pipeline(groq_client: Optional[GroqClient] = None) -> NewsletterPipeline:
    """Get or create the global newsletter pipeline."""
    global _newsletter_pipeline
    
    if _newsletter_pipeline is None:
        if groq_client is None:
            from src.ai.groq_client import get_groq_client
            groq_client = await get_groq_client()
        
        _newsletter_pipeline = NewsletterPipeline(groq_client)
    
    return _newsletter_pipeline