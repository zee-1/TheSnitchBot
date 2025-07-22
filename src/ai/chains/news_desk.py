"""
News Desk Chain - Chain A of the newsletter pipeline.
Identifies potential stories from Discord messages.
"""

from typing import List, Dict, Any

from .base_newsletter_chain import BaseNewsletterChain
from src.ai.llm_client import TaskType
from src.ai.prompts.newsletter import NewsletterPrompts
from src.models.message import Message
from src.models.server import PersonaType
from src.core.exceptions import AIServiceError
from src.core.logging import get_logger

logger = get_logger(__name__)


class NewsDeskChain(BaseNewsletterChain):
    """Chain A: Identifies newsworthy stories from messages."""

    task_type = TaskType.ANALYSIS  # Analysis of messages to identify stories

    async def identify_stories(
        self, messages: List[Message], persona: PersonaType, max_stories: int = 5
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

            # Get AI response with TaskType routing
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": analysis_prompt})

            response_data = await self._safe_ai_chat_completion(
                messages=messages, temperature=0.7, max_tokens=2048
            )
            response = response_data["choices"][0]["message"]["content"]

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
                persona=persona,
            )

            return enriched_stories[:max_stories]

        except Exception as e:
            logger.error(f"Error in news desk story identification: {e}")
            raise AIServiceError(f"News desk analysis failed: {e}")

    def _prepare_message_data(self, messages: List[Message]) -> str:
        """Prepare message data for AI analysis."""

        # Helper functions to handle both Message objects and dicts
        def get_total_reactions(m):
            return getattr(m, "total_reactions", m.get("total_reactions", 0))

        def get_reply_count(m):
            return getattr(m, "reply_count", m.get("reply_count", 0))

        def get_controversy_score(m):
            if hasattr(m, "controversy_score"):
                return m.controversy_score
            else:
                reactions = m.get("total_reactions", 0)
                replies = m.get("reply_count", 0)
                return min((reactions + replies) / 20.0, 1.0)

        # Sort messages by engagement score (reactions + replies + controversy)
        sorted_messages = sorted(
            messages,
            key=lambda m: (
                get_total_reactions(m)
                + get_reply_count(m)
                + (get_controversy_score(m) * 10)  # Weight controversy higher
            ),
            reverse=True,
        )

        # Take top messages and format for analysis
        analysis_data = []
        for i, msg in enumerate(sorted_messages[:50]):  # Limit to top 50 messages
            # Helper functions for message data extraction
            def get_content(m):
                return getattr(m, "content", m.get("content", "No content"))

            def get_author_id(m):
                author_id = getattr(m, "author_id", m.get("author_id", m.get("author", "unknown")))
                return str(author_id)[-4:] if author_id != "unknown" else "unkn"

            def get_timestamp(m):
                if hasattr(m, "timestamp_dt"):
                    return m.timestamp_dt.strftime("%Y-%m-%d %H:%M")
                elif m.get("timestamp"):
                    from datetime import datetime

                    try:
                        timestamp_str = m.get("timestamp")
                        if isinstance(timestamp_str, str):
                            dt = datetime.fromisoformat(timestamp_str)
                            return dt.strftime("%Y-%m-%d %H:%M")
                        return str(timestamp_str)[:16]  # Fallback truncate
                    except Exception:
                        return "Unknown time"
                else:
                    return "Unknown time"

            def get_engagement_score(m):
                if hasattr(m, "calculate_engagement_score"):
                    return m.calculate_engagement_score()
                else:
                    return (get_total_reactions(m) + get_reply_count(m)) / 10.0

            content = get_content(msg)

            # Create message summary
            msg_summary = {
                "id": f"MSG_{i+1}",
                "content": content[:200] + "..." if len(content) > 200 else content,
                "author": f"User_{get_author_id(msg)}",  # Anonymize with last 4 digits
                "timestamp": get_timestamp(msg),
                "reactions": get_total_reactions(msg),
                "replies": get_reply_count(msg),
                "controversy_score": round(get_controversy_score(msg), 2),
                "engagement_score": round(get_engagement_score(msg), 2),
            }

            # Add reaction details if present
            reactions = getattr(msg, "reactions", msg.get("reactions", []))
            if reactions:
                reaction_summary = []
                for reaction in reactions[:3]:  # Top 3 reactions
                    if hasattr(reaction, "emoji") and hasattr(reaction, "count"):
                        reaction_summary.append(f"{reaction.emoji}({reaction.count})")
                    elif isinstance(reaction, dict):
                        emoji = reaction.get("emoji", "❓")
                        count = reaction.get("count", 0)
                        reaction_summary.append(f"{emoji}({count})")
                if reaction_summary:
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

    def _parse_stories_response(
        self, response: str, messages: List[Message]
    ) -> List[Dict[str, Any]]:
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

                def get_engagement_score(m):
                    if hasattr(m, "calculate_engagement_score"):
                        return m.calculate_engagement_score()
                    else:
                        return (m.get("total_reactions", 0) + m.get("reply_count", 0)) / 10.0

                def get_total_reactions(m):
                    return getattr(m, "total_reactions", m.get("total_reactions", 0))

                top_message = max(messages, key=get_engagement_score)
                fallback_story = {
                    "headline": "Community Discussion",
                    "summary": (
                        f"Active discussion around recent messages with "
                        f"{get_total_reactions(top_message)} reactions"
                    ),
                    "newsworthiness": "High engagement",
                    "key_players": "Multiple community members",
                    "is_fallback": True,
                }
                stories.append(fallback_story)

        return stories

    async def _enrich_story_metadata(
        self, story: Dict[str, Any], messages: List[Message]
    ) -> Dict[str, Any]:
        """Add metadata and analysis to story candidates."""

        # Calculate story metrics
        story_score = self._calculate_story_score(story, messages)

        # Find related messages
        related_messages = self._find_related_messages(story, messages)

        # Helper functions for both Message objects and dicts
        def get_message_id(msg):
            return getattr(msg, "message_id", msg.get("message_id", msg.get("id", "unknown")))

        def get_author_id(msg):
            return getattr(msg, "author_id", msg.get("author_id", msg.get("author", "unknown")))

        def get_engagement_score(msg):
            if hasattr(msg, "calculate_engagement_score"):
                return msg.calculate_engagement_score()
            else:
                return (msg.get("total_reactions", 0) + msg.get("reply_count", 0)) / 10.0

        def get_controversy_score(msg):
            if hasattr(msg, "controversy_score"):
                return msg.controversy_score
            else:
                reactions = msg.get("total_reactions", 0)
                replies = msg.get("reply_count", 0)
                return min((reactions + replies) / 20.0, 1.0)

        # Add enrichment data
        enriched_story = {
            **story,
            "story_score": story_score,
            "related_message_count": len(related_messages),
            "related_message_ids": [get_message_id(msg) for msg in related_messages[:5]],
            "total_engagement": sum(get_engagement_score(msg) for msg in related_messages),
            "average_controversy": sum(get_controversy_score(msg) for msg in related_messages)
            / len(related_messages)
            if related_messages
            else 0,
            "time_span_hours": self._calculate_time_span(related_messages),
            "unique_participants": len(set(get_author_id(msg) for msg in related_messages)),
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
            # Engagement score - handle both Message objects and dicts
            def get_engagement_score(msg):
                if hasattr(msg, "calculate_engagement_score"):
                    return msg.calculate_engagement_score()
                else:
                    # Calculate basic engagement for dict messages
                    return (msg.get("total_reactions", 0) + msg.get("reply_count", 0)) / 10.0

            avg_engagement = sum(get_engagement_score(msg) for msg in related_messages) / len(
                related_messages
            )
            score += avg_engagement * 0.3

            # Controversy score - handle both Message objects and dicts
            def get_controversy_score(msg):
                if hasattr(msg, "controversy_score"):
                    return msg.controversy_score
                else:
                    # Basic controversy calculation for dict messages
                    reactions = msg.get("total_reactions", 0)
                    replies = msg.get("reply_count", 0)
                    return min((reactions + replies) / 20.0, 1.0)  # Cap at 1.0

            avg_controversy = sum(get_controversy_score(msg) for msg in related_messages) / len(
                related_messages
            )
            score += avg_controversy * 0.2

            # Participation score
            def get_author_id(msg):
                return getattr(msg, "author_id", msg.get("author_id", msg.get("author", "unknown")))

            unique_users = len(set(get_author_id(msg) for msg in related_messages))
            participation_score = min(unique_users / 10, 1.0)  # Normalize to max 10 users = 1.0
            score += participation_score * 0.2

        return min(score, 1.0)

    def _find_related_messages(
        self, story: Dict[str, Any], messages: List[Message]
    ) -> List[Message]:
        """Find messages related to a story based on keywords and timing."""

        related_messages = []

        # Extract keywords from story
        story_text = f"{story.get('headline', '')} {story.get('summary', '')}".lower()
        story_keywords = set(word.strip(".,!?") for word in story_text.split() if len(word) > 3)

        for message in messages:
            # Handle both Message objects and dict objects
            if hasattr(message, "content") and hasattr(message, "calculate_engagement_score"):
                message_text = message.content.lower()
                engagement_score = message.calculate_engagement_score()
            else:
                message_text = (
                    message.get("content", "").lower()
                    if hasattr(message, "get")
                    else getattr(message, "content", "").lower()
                )
                # Calculate basic engagement for dict messages
                engagement_score = (
                    (message.get("total_reactions", 0) + message.get("reply_count", 0)) / 10.0
                    if hasattr(message, "get")
                    else (
                        getattr(message, "total_reactions", 0) + getattr(message, "reply_count", 0)
                    )
                    / 10.0
                )

            message_keywords = set(
                word.strip(".,!?") for word in message_text.split() if len(word) > 3
            )

            # Check for keyword overlap
            keyword_overlap = len(story_keywords.intersection(message_keywords))
            overlap_ratio = keyword_overlap / len(story_keywords) if story_keywords else 0

            # Consider messages with good keyword overlap or high engagement
            if overlap_ratio > 0.2 or engagement_score > 0.5:
                related_messages.append(message)

        # Sort by engagement and return top messages
        related_messages.sort(
            key=lambda m: m.calculate_engagement_score()
            if hasattr(m, "calculate_engagement_score")
            else (m.get("total_reactions", 0) + m.get("reply_count", 0)) / 10.0,
            reverse=True,
        )
        return related_messages[:10]  # Top 10 related messages

    def _calculate_time_span(self, messages: List[Message]) -> float:
        """Calculate time span of related messages in hours."""

        if len(messages) < 2:
            return 0.0

        def get_timestamp(msg):
            if hasattr(msg, "timestamp_dt"):
                return msg.timestamp_dt
            elif hasattr(msg, "timestamp"):
                # Handle dict with timestamp string
                from datetime import datetime

                timestamp_str = msg.get("timestamp")
                if isinstance(timestamp_str, str):
                    try:
                        return datetime.fromisoformat(timestamp_str)
                    except Exception:
                        return datetime.now()
                return timestamp_str
            else:
                from datetime import datetime

                return datetime.now()

        timestamps = [get_timestamp(msg) for msg in messages]
        time_span = max(timestamps) - min(timestamps)
        return time_span.total_seconds() / 3600  # Convert to hours
