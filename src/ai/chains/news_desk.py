"""
News Desk Chain - Chain A of the newsletter pipeline.
Identifies potential stories from Discord messages.
"""

from typing import List, Dict, Any, Optional
import json
import logging

from src.ai.llm_client import LLMClient
from src.ai.prompts.newsletter import NewsletterPrompts
from src.models.message import Message
from src.models.server import PersonaType
from src.core.exceptions import AIServiceError, AIResponseParsingError
from src.core.logging import get_logger

logger = get_logger(__name__)


class NewsDeskChain:
    """Chain A: Identifies newsworthy stories from messages."""
    
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
    
    async def identify_stories(
        self,
        messages: List[Message],
        persona: PersonaType,
        max_stories: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Analyze messages and identify potential newsworthy stories.
        
        Args:
            messages: List of messages to analyze
            persona: Bot persona for appropriate analysis style
            max_stories: Maximum number of stories to identify
            
        Returns:
            List of story candidates with metadata
        """
        try:
            if not messages:
                logger.warning("No messages provided for story identification")
                return []
            
            # Prepare message data for analysis
            message_data = self._prepare_message_data(messages)
            
            # Get appropriate prompt
            system_prompt = NewsletterPrompts.get_news_desk_prompt(persona)
            
            # Create analysis prompt
            analysis_prompt = f"""
            Analyze the following Discord messages and identify {max_stories} potential news stories.
            
            MESSAGE DATA:
            {message_data}
            
            Remember to focus on:
            - High engagement (messages with many replies/reactions)
            - Controversial or debate-inducing content
            - Funny or memorable moments
            - Community events or announcements
            - Unexpected developments
            
            Provide exactly {max_stories} story candidates.
            """
            
            # Get AI response
            response = await self.llm_client.conversation_completion(
                conversation=[{"role": "user", "content": analysis_prompt}],
                system_prompt=system_prompt,
                temperature=0.7,
                max_tokens=1000
            )
            
            # Parse stories from response
            stories = self._parse_stories_response(response, messages)
            
            # Add metadata to stories
            enriched_stories = []
            for story in stories:
                enriched_story = await self._enrich_story_metadata(story, messages)
                enriched_stories.append(enriched_story)
            
            logger.info(
                "News desk analysis completed",
                message_count=len(messages),
                stories_identified=len(enriched_stories),
                persona=persona
            )
            
            return enriched_stories[:max_stories]
        
        except Exception as e:
            logger.error(f"Error in news desk story identification: {e}")
            raise AIServiceError(f"News desk analysis failed: {e}")
    
    def _prepare_message_data(self, messages: List[Message]) -> str:
        """Prepare message data for AI analysis."""
        
        # Sort messages by engagement score (reactions + replies + controversy)
        sorted_messages = sorted(
            messages,
            key=lambda m: (
                m.total_reactions + 
                m.reply_count + 
                (m.controversy_score * 10)  # Weight controversy higher
            ),
            reverse=True
        )
        
        # Take top messages and format for analysis
        analysis_data = []
        for i, msg in enumerate(sorted_messages[:50]):  # Limit to top 50 messages
            
            # Create message summary
            msg_summary = {
                "id": f"MSG_{i+1}",
                "content": msg.content[:200] + "..." if len(msg.content) > 200 else msg.content,
                "author": f"User_{msg.author_id[-4:]}",  # Anonymize with last 4 digits
                "timestamp": msg.timestamp_dt.strftime("%Y-%m-%d %H:%M"),
                "reactions": msg.total_reactions,
                "replies": msg.reply_count,
                "controversy_score": round(msg.controversy_score, 2),
                "engagement_score": round(msg.calculate_engagement_score(), 2)
            }
            
            # Add reaction details if present
            if msg.reactions:
                reaction_summary = []
                for reaction in msg.reactions[:3]:  # Top 3 reactions
                    reaction_summary.append(f"{reaction.emoji}({reaction.count})")
                msg_summary["top_reactions"] = ", ".join(reaction_summary)
            
            analysis_data.append(msg_summary)
        
        # Format as readable text for the AI
        formatted_data = []
        for msg in analysis_data:
            msg_text = f"""
            {msg['id']} | {msg['timestamp']} | {msg['author']}
            Content: {msg['content']}
            Engagement: {msg['reactions']} reactions, {msg['replies']} replies
            Controversy: {msg['controversy_score']}/1.0 | Engagement: {msg['engagement_score']}/1.0
            """
            
            if "top_reactions" in msg:
                msg_text += f"Top Reactions: {msg['top_reactions']}\n"
            
            msg_text += "---"
            formatted_data.append(msg_text)
        
        return "\n".join(formatted_data)
    
    def _parse_stories_response(self, response: str, messages: List[Message]) -> List[Dict[str, Any]]:
        """Parse AI response to extract story candidates."""
        
        stories = []
        
        try:
            # Split response into story sections
            story_sections = response.split("**STORY")
            
            for section in story_sections[1:]:  # Skip first empty section
                story_data = {}
                
                lines = section.strip().split("\n")
                
                for line in lines:
                    line = line.strip()
                    
                    if line.startswith("Headline:"):
                        story_data["headline"] = line.replace("Headline:", "").strip()
                    elif line.startswith("Newsworthiness:"):
                        story_data["newsworthiness"] = line.replace("Newsworthiness:", "").strip()
                    elif line.startswith("Key Players:"):
                        story_data["key_players"] = line.replace("Key Players:", "").strip()
                    elif line.startswith("Summary:"):
                        story_data["summary"] = line.replace("Summary:", "").strip()
                
                # Only add stories with required fields
                if all(key in story_data for key in ["headline", "summary"]):
                    stories.append(story_data)
        
        except Exception as e:
            logger.warning(f"Error parsing stories response: {e}")
            
            # Fallback: create a simple story from highest engagement message
            if messages:
                top_message = max(messages, key=lambda m: m.calculate_engagement_score())
                fallback_story = {
                    "headline": "Community Discussion",
                    "summary": f"Active discussion around recent messages with {top_message.total_reactions} reactions",
                    "newsworthiness": "High engagement",
                    "key_players": "Multiple community members",
                    "is_fallback": True
                }
                stories.append(fallback_story)
        
        return stories
    
    async def _enrich_story_metadata(self, story: Dict[str, Any], messages: List[Message]) -> Dict[str, Any]:
        """Add metadata and analysis to story candidates."""
        
        # Calculate story metrics
        story_score = self._calculate_story_score(story, messages)
        
        # Find related messages
        related_messages = self._find_related_messages(story, messages)
        
        # Add enrichment data
        enriched_story = {
            **story,
            "story_score": story_score,
            "related_message_count": len(related_messages),
            "related_message_ids": [msg.message_id for msg in related_messages[:5]],
            "total_engagement": sum(msg.calculate_engagement_score() for msg in related_messages),
            "average_controversy": sum(msg.controversy_score for msg in related_messages) / len(related_messages) if related_messages else 0,
            "time_span_hours": self._calculate_time_span(related_messages),
            "unique_participants": len(set(msg.author_id for msg in related_messages))
        }
        
        return enriched_story
    
    def _calculate_story_score(self, story: Dict[str, Any], messages: List[Message]) -> float:
        """Calculate overall story score for ranking."""
        
        score = 0.0
        
        # Base score from AI assessment
        if "newsworthiness" in story:
            newsworthiness = story["newsworthiness"].lower()
            if any(word in newsworthiness for word in ["high", "very", "extremely"]):
                score += 0.3
            elif any(word in newsworthiness for word in ["medium", "moderate"]):
                score += 0.2
            else:
                score += 0.1
        
        # Find related messages and calculate engagement
        related_messages = self._find_related_messages(story, messages)
        
        if related_messages:
            # Engagement score
            avg_engagement = sum(msg.calculate_engagement_score() for msg in related_messages) / len(related_messages)
            score += avg_engagement * 0.3
            
            # Controversy score
            avg_controversy = sum(msg.controversy_score for msg in related_messages) / len(related_messages)
            score += avg_controversy * 0.2
            
            # Participation score
            unique_users = len(set(msg.author_id for msg in related_messages))
            participation_score = min(unique_users / 10, 1.0)  # Normalize to max 10 users = 1.0
            score += participation_score * 0.2
        
        return min(score, 1.0)
    
    def _find_related_messages(self, story: Dict[str, Any], messages: List[Message]) -> List[Message]:
        """Find messages related to a story based on keywords and timing."""
        
        related_messages = []
        
        # Extract keywords from story
        story_text = f"{story.get('headline', '')} {story.get('summary', '')}".lower()
        story_keywords = set(word.strip('.,!?') for word in story_text.split() if len(word) > 3)
        
        for message in messages:
            message_text = message.content.lower()
            message_keywords = set(word.strip('.,!?') for word in message_text.split() if len(word) > 3)
            
            # Check for keyword overlap
            keyword_overlap = len(story_keywords.intersection(message_keywords))
            overlap_ratio = keyword_overlap / len(story_keywords) if story_keywords else 0
            
            # Consider messages with good keyword overlap or high engagement
            if overlap_ratio > 0.2 or message.calculate_engagement_score() > 0.5:
                related_messages.append(message)
        
        # Sort by engagement and return top messages
        related_messages.sort(key=lambda m: m.calculate_engagement_score(), reverse=True)
        return related_messages[:10]  # Top 10 related messages
    
    def _calculate_time_span(self, messages: List[Message]) -> float:
        """Calculate time span of related messages in hours."""
        
        if len(messages) < 2:
            return 0.0
        
        timestamps = [msg.timestamp_dt for msg in messages]
        time_span = max(timestamps) - min(timestamps)
        return time_span.total_seconds() / 3600  # Convert to hours