"""
Star Reporter Chain - Chain C of the newsletter pipeline.
Writes the final newsletter article based on selected story.
"""

from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

from src.ai.groq_client import GroqClient
from src.ai.prompts.newsletter import NewsletterPrompts
from src.models.message import Message
from src.models.server import PersonaType
from src.core.exceptions import AIServiceError
from src.core.logging import get_logger

logger = get_logger(__name__)


class StarReporterChain:
    """Chain C: Writes the final newsletter article."""
    
    def __init__(self, groq_client: GroqClient):
        self.groq_client = groq_client
    
    async def write_article(
        self,
        selected_story: Dict[str, Any],
        persona: PersonaType,
        source_messages: List[Message],
        server_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Write the final newsletter article based on the selected story.
        
        Args:
            selected_story: The story selected by Editor-in-Chief
            persona: Bot persona for writing style
            source_messages: Original source messages for quotes
            server_context: Additional server context
            
        Returns:
            Complete newsletter article text
        """
        try:
            # Prepare article context
            article_context = self._prepare_article_context(
                selected_story, source_messages, server_context
            )
            
            # Get appropriate prompt
            system_prompt = NewsletterPrompts.get_star_reporter_prompt(persona)
            
            # Create article writing prompt
            writing_prompt = f"""
            Write the complete newsletter article based on this editorial assignment:
            
            SELECTED STORY:
            Headline: {selected_story.get('suggested_headline', selected_story.get('headline', 'Community Update'))}
            Editorial Reasoning: {selected_story.get('editorial_reasoning', 'Story of interest')}
            Reporting Angle: {selected_story.get('reporting_angle', 'Standard community reporting')}
            
            STORY CONTEXT:
            {article_context}
            
            WRITING REQUIREMENTS:
            - Write as a {persona.replace('_', ' ')} personality
            - Include actual quotes from messages (but anonymize usernames)
            - Make it 200-400 words
            - Include engaging headline and conclusion
            - Use appropriate emojis and formatting
            - Focus on entertainment value for the community
            
            Write the complete newsletter article now:
            """
            
            # Generate the article
            article = await self.groq_client.conversation_completion(
                conversation=[{"role": "user", "content": writing_prompt}],
                system_prompt=system_prompt,
                temperature=0.8,  # Higher temperature for creative writing
                max_tokens=1200
            )
            
            # Post-process the article
            processed_article = self._post_process_article(article, selected_story, persona)
            
            logger.info(
                "Newsletter article written",
                headline=selected_story.get("headline", "Unknown"),
                article_length=len(processed_article),
                persona=persona,
                source_messages=len(source_messages)
            )
            
            return processed_article
        
        except Exception as e:
            logger.error(f"Error in star reporter article writing: {e}")
            
            # Generate fallback article
            fallback_article = self._generate_fallback_article(selected_story, persona)
            return fallback_article
    
    def _prepare_article_context(
        self,
        story: Dict[str, Any],
        messages: List[Message],
        server_context: Optional[Dict[str, Any]]
    ) -> str:
        """Prepare context information for article writing."""
        
        context_parts = []
        
        # Story summary
        context_parts.append(f"STORY SUMMARY:\n{story.get('summary', 'No summary available')}")
        
        # Story metrics for context
        metrics = f"""
        STORY METRICS:
        - Engagement Score: {story.get('total_engagement', 0):.2f}
        - Participants: {story.get('unique_participants', 0)} users
        - Time Span: {story.get('time_span_hours', 0):.1f} hours
        - Controversy Level: {story.get('average_controversy', 0):.2f}/1.0
        """
        context_parts.append(metrics)
        
        # Related messages for quotes
        related_message_ids = story.get('related_message_ids', [])
        relevant_messages = [msg for msg in messages if msg.message_id in related_message_ids]
        
        if relevant_messages:
            quotes_section = "AVAILABLE QUOTES (anonymized):\n"
            
            # Sort by engagement and take top quotes
            sorted_messages = sorted(
                relevant_messages,
                key=lambda m: m.calculate_engagement_score(),
                reverse=True
            )
            
            for i, msg in enumerate(sorted_messages[:5], 1):
                # Anonymize the quote
                anonymized_author = f"User_{msg.author_id[-3:]}"
                
                # Truncate long messages
                quote_content = msg.content
                if len(quote_content) > 150:
                    quote_content = quote_content[:150] + "..."
                
                quote_info = f"""
                Quote {i}: "{quote_content}"
                - Author: {anonymized_author}
                - Reactions: {msg.total_reactions}
                - Replies: {msg.reply_count}
                - Timestamp: {msg.timestamp.strftime('%H:%M')}
                """
                
                quotes_section += quote_info
            
            context_parts.append(quotes_section)
        
        # Server context if available
        if server_context:
            context_parts.append(f"SERVER CONTEXT:\n{server_context}")
        
        return "\n\n".join(context_parts)
    
    def _post_process_article(
        self,
        article: str,
        story: Dict[str, Any],
        persona: PersonaType
    ) -> str:
        """Post-process the generated article for consistency and formatting."""
        
        processed = article.strip()
        
        # Ensure article has a clear structure
        if not any(marker in processed for marker in ['#', '**', '*']):
            # Add basic formatting if none exists
            lines = processed.split('\n')
            if lines:
                # Make first line the headline
                lines[0] = f"## {lines[0].strip()}"
                processed = '\n'.join(lines)
        
        # Add newsletter footer if not present
        footer_text = "\n\n---\n*Generated by The Snitch 🤖 | Stay informed, stay entertained*"
        if not processed.endswith("---"):
            processed += footer_text
        
        # Ensure appropriate length
        if len(processed) < 100:
            # Article too short, add filler content
            processed += f"\n\nThis story continues to develop as community discussions evolve. "
            processed += f"The {persona.replace('_', ' ')} will keep monitoring the situation!"
        
        elif len(processed) > 2000:
            # Article too long, truncate gracefully
            processed = processed[:1900] + "...\n\n*[Article truncated for length]*" + footer_text
        
        return processed
    
    def _generate_fallback_article(
        self,
        story: Dict[str, Any],
        persona: PersonaType
    ) -> str:
        """Generate a fallback article when AI generation fails."""
        
        headline = story.get("suggested_headline", story.get("headline", "Community Update"))
        summary = story.get("summary", "Community discussions continue across the server.")
        
        # Create a simple fallback based on persona
        persona_intros = {
            PersonaType.SASSY_REPORTER: "Okay babes, let me spill the tea ☕",
            PersonaType.INVESTIGATIVE_JOURNALIST: "Following extensive investigation,",
            PersonaType.GOSSIP_COLUMNIST: "The drama desk has been BUSY today! 💅",
            PersonaType.SPORTS_COMMENTATOR: "AND HERE WE GO with today's play-by-play! 🏟️",
            PersonaType.WEATHER_ANCHOR: "Today's server climate shows",
            PersonaType.CONSPIRACY_THEORIST: "Connect the dots, people! 🕵️"
        }
        
        intro = persona_intros.get(persona, "Here's what's happening in the community:")
        
        fallback_article = f"""
        ## {headline}
        
        {intro}
        
        {summary}
        
        Community engagement continues to be strong, with multiple discussions and interactions 
        happening across various channels. While the details are still developing, 
        it's clear that our server members are staying active and engaged.
        
        Stay tuned for more updates as stories develop!
        
        ---
        *Generated by The Snitch 🤖 | Fallback article due to technical difficulties*
        """
        
        return fallback_article.strip()
    
    async def generate_breaking_news(
        self,
        messages: List[Message],
        persona: PersonaType,
        context: Optional[str] = None
    ) -> str:
        """
        Generate a breaking news bulletin from recent messages.
        
        Args:
            messages: Recent messages to analyze
            persona: Bot persona for writing style
            context: Optional context about the situation
            
        Returns:
            Breaking news bulletin text
        """
        try:
            if not messages:
                return self._generate_fallback_breaking_news(persona)
            
            # Prepare message data for analysis
            message_data = self._prepare_breaking_news_data(messages)
            
            # Get breaking news prompt
            system_prompt = NewsletterPrompts.PERSONA_SYSTEMS.get(
                persona,
                NewsletterPrompts.PERSONA_SYSTEMS[PersonaType.SASSY_REPORTER]
            )
            
            breaking_prompt = f"""
            You are reporting BREAKING NEWS from recent Discord activity.
            
            Analyze these recent messages and create a single-paragraph breaking news bulletin:
            
            {message_data}
            
            Context: {context or "Recent channel activity"}
            
            Write a 2-3 sentence breaking news bulletin that:
            - Starts with "🚨 BREAKING:" or similar
            - Summarizes the most significant recent event/topic
            - Uses your {persona.replace('_', ' ')} voice
            - Includes relevant emojis
            - Makes it feel urgent and newsworthy
            
            Write only the bulletin, nothing else:
            """
            
            bulletin = await self.groq_client.conversation_completion(
                conversation=[{"role": "user", "content": breaking_prompt}],
                system_prompt=system_prompt,
                temperature=0.8,
                max_tokens=300
            )
            
            return bulletin.strip()
        
        except Exception as e:
            logger.error(f"Error generating breaking news: {e}")
            return self._generate_fallback_breaking_news(persona)
    
    def _prepare_breaking_news_data(self, messages: List[Message]) -> str:
        """Prepare message data for breaking news analysis."""
        
        # Sort by timestamp (most recent first) and engagement
        recent_messages = sorted(
            messages,
            key=lambda m: (m.timestamp, m.calculate_engagement_score()),
            reverse=True
        )[:10]  # Top 10 most recent and engaging
        
        data_parts = []
        for i, msg in enumerate(recent_messages, 1):
            msg_data = f"""
            Message {i} | {msg.timestamp.strftime('%H:%M')}
            Content: {msg.content[:100]}{'...' if len(msg.content) > 100 else ''}
            Engagement: {msg.total_reactions} reactions, {msg.reply_count} replies
            """
            data_parts.append(msg_data)
        
        return "\n".join(data_parts)
    
    def _generate_fallback_breaking_news(self, persona: PersonaType) -> str:
        """Generate fallback breaking news when analysis fails."""
        
        fallback_bulletins = {
            PersonaType.SASSY_REPORTER: "🚨 BREAKING: The tea is brewing but the details are still steeping! ☕ Stay tuned for more piping hot updates! 💅",
            PersonaType.INVESTIGATIVE_JOURNALIST: "🚨 BREAKING: Developing story in progress. Our newsroom is investigating recent community activity and will report findings as they become available.",
            PersonaType.GOSSIP_COLUMNIST: "🚨 BREAKING: Honey, something's happening and the drama sensors are tingling! 💅 Details are still coming in but trust me, you'll want to stay tuned! ✨",
            PersonaType.SPORTS_COMMENTATOR: "🚨 BREAKING: WE'VE GOT ACTION ON THE FIELD! 🏟️ The players are making moves and the crowd is going wild! Stay tuned for the play-by-play! 📣",
            PersonaType.WEATHER_ANCHOR: "🚨 BREAKING: Server weather patterns show increased activity in the forecast. ⛈️ Expect continued engagement with a chance of exciting developments.",
            PersonaType.CONSPIRACY_THEORIST: "🚨 BREAKING: The pieces are moving, people! 🕵️ Something's happening behind the scenes and all the signs are pointing to... well, something big! Stay woke! 👁️"
        }
        
        return fallback_bulletins.get(
            persona,
            "🚨 BREAKING: Community activity detected! Stay tuned for updates as the story develops. 📰"
        )