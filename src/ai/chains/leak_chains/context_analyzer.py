"""
Context Analyzer - CoT Step 1
Analyzes server context and target user patterns for leak generation.
"""

from typing import List, Dict, Any
from datetime import datetime, timedelta
import re
from collections import Counter

from .base import BaseLeakChain, ContextAnalysis
from src.models.server import ServerConfig, PersonaType
from src.core.logging import get_logger

logger = get_logger(__name__)


class ContextAnalyzer(BaseLeakChain):
    """Analyzes server and user context for leak generation."""
    
    async def process(self, *args, **kwargs) -> ContextAnalysis:
        """Process method required by BaseLeakChain interface."""
        # Delegate to analyze_context method
        return await self.analyze_context(*args, **kwargs)
    
    async def analyze_context(
        self,
        target_user_id: str,
        target_name: str,
        recent_messages: List[Any],
        server_config: ServerConfig
    ) -> ContextAnalysis:
        """
        Analyze context for leak generation.
        
        Args:
            target_user_id: ID of the target user
            target_name: Display name of target user
            recent_messages: Recent Discord messages
            server_config: Server configuration
            
        Returns:
            ContextAnalysis with structured insights
        """
        try:
            self.logger.info(f"Starting context analysis for {target_name}")
            
            # Extract target user's messages and patterns
            target_messages = self._extract_target_messages(recent_messages, target_user_id)
            
            # Analyze communication style
            communication_style = self._analyze_communication_style(target_messages)
            
            # Extract active topics from server
            active_topics = self._extract_active_topics(recent_messages)
            
            # Assess server culture
            server_culture = self._assess_server_culture(recent_messages, server_config.persona)
            
            # Find user interests and patterns
            user_interests = self._identify_user_interests(target_messages)
            
            # Analyze recent interactions
            recent_interactions = self._analyze_user_interactions(recent_messages, target_user_id, target_name)
            
            # Calculate relevance factors using AI reasoning
            relevance_factors = await self._calculate_relevance_factors(
                target_name=target_name,
                communication_style=communication_style,
                user_interests=user_interests,
                active_topics=active_topics,
                server_culture=server_culture,
                persona=server_config.persona
            )
            
            # Generate reasoning summary
            reasoning = self._generate_reasoning_summary(
                target_name=target_name,
                communication_style=communication_style,
                active_topics=active_topics,
                user_interests=user_interests,
                relevance_factors=relevance_factors
            )
            
            context_analysis = ContextAnalysis(
                user_communication_style=communication_style,
                active_topics=active_topics,
                server_culture_assessment=server_culture,
                relevance_factors=relevance_factors,
                user_interests=user_interests,
                recent_interactions=recent_interactions,
                reasoning=reasoning
            )
            
            self.logger.info(f"Context analysis completed for {target_name}")
            return context_analysis
            
        except Exception as e:
            self.logger.error(f"Context analysis failed: {e}")
            # Return minimal analysis on failure
            return self._get_fallback_analysis(target_name, server_config.persona)
    
    def _extract_target_messages(self, recent_messages: List[Any], target_user_id: str) -> List[str]:
        """Extract messages from the target user."""
        target_messages = []
        for msg in recent_messages[-50:]:  # Last 50 messages
            if str(msg.author.id) == target_user_id and len(msg.content.strip()) > 5:
                target_messages.append(msg.content)
        return target_messages[-10:]  # Keep last 10 for analysis
    
    def _analyze_communication_style(self, target_messages: List[str]) -> Dict[str, Any]:
        """Analyze user's communication patterns."""
        if not target_messages:
            return {"style": "minimal", "confidence": 0.1}
        
        total_chars = sum(len(msg) for msg in target_messages)
        avg_length = total_chars / len(target_messages) if target_messages else 0
        
        # Count communication indicators
        emoji_count = sum(len(re.findall(r'[😀-🿿]|:[a-z_]+:', msg)) for msg in target_messages)
        caps_count = sum(len(re.findall(r'[A-Z]{2,}', msg)) for msg in target_messages)
        question_count = sum(msg.count('?') for msg in target_messages)
        exclamation_count = sum(msg.count('!') for msg in target_messages)
        
        # Classify style
        style_indicators = {
            "expressive": emoji_count > 5 or exclamation_count > 3,
            "inquisitive": question_count > 2,
            "casual": avg_length < 50 and emoji_count > 2,
            "formal": avg_length > 100 and caps_count < 2,
            "energetic": caps_count > 3 or exclamation_count > 5
        }
        
        primary_style = max(style_indicators.items(), key=lambda x: x[1])[0] if any(style_indicators.values()) else "neutral"
        
        return {
            "style": primary_style,
            "avg_message_length": avg_length,
            "emoji_usage": emoji_count / len(target_messages) if target_messages else 0,
            "expressiveness": (exclamation_count + question_count) / len(target_messages) if target_messages else 0,
            "confidence": min(len(target_messages) / 10, 1.0)  # Higher confidence with more messages
        }
    
    def _extract_active_topics(self, recent_messages: List[Any]) -> List[str]:
        """Extract trending topics from recent server activity."""
        all_content = []
        for msg in recent_messages[-30:]:  # Last 30 messages
            if not msg.author.bot and len(msg.content.strip()) > 10:
                all_content.append(msg.content.lower())
        
        if not all_content:
            return ["general chat", "community"]
        
        # Common topic keywords
        topic_keywords = {
            "gaming": ["game", "play", "win", "lose", "level", "boss", "pvp", "raid", "stream", "twitch"],
            "anime": ["anime", "manga", "episode", "season", "character", "waifu", "otaku"],
            "music": ["song", "album", "listen", "band", "artist", "concert", "music", "lyrics"],
            "food": ["eat", "food", "cook", "recipe", "restaurant", "hungry", "delicious", "meal"],
            "work": ["work", "job", "boss", "office", "meeting", "project", "deadline", "salary"],
            "school": ["school", "class", "teacher", "exam", "study", "homework", "grade", "university"],
            "movies": ["movie", "film", "watch", "cinema", "actor", "director", "scene", "netflix"],
            "tech": ["computer", "phone", "app", "software", "code", "program", "update", "bug"],
            "memes": ["meme", "lol", "lmao", "funny", "joke", "kek", "poggers", "based", "cringe"]
        }
        
        topic_scores = {}
        content_text = " ".join(all_content)
        
        for topic, keywords in topic_keywords.items():
            score = sum(content_text.count(keyword) for keyword in keywords)
            if score > 0:
                topic_scores[topic] = score
        
        # Sort by frequency and return top topics
        sorted_topics = sorted(topic_scores.items(), key=lambda x: x[1], reverse=True)
        active_topics = [topic for topic, score in sorted_topics[:5]] if sorted_topics else ["general chat"]
        
        return active_topics
    
    def _assess_server_culture(self, recent_messages: List[Any], persona: PersonaType) -> Dict[str, Any]:
        """Assess the server's communication culture."""
        if not recent_messages:
            return {"culture_type": "neutral", "confidence": 0.1}
        
        message_contents = [msg.content.lower() for msg in recent_messages[-20:] if not msg.author.bot]
        all_text = " ".join(message_contents)
        
        culture_indicators = {
            "friendly": ["thanks", "welcome", "nice", "good", "great", "awesome", "love"],
            "competitive": ["win", "beat", "best", "top", "rank", "compete", "challenge"],
            "casual": ["lol", "lmao", "haha", "chill", "cool", "nice", "yeah"],
            "technical": ["code", "build", "system", "config", "debug", "install", "setup"],
            "creative": ["art", "draw", "create", "design", "make", "build", "craft"],
            "meme-heavy": ["meme", "kek", "poggers", "based", "cringe", "sus", "bruh"]
        }
        
        culture_scores = {}
        for culture, keywords in culture_indicators.items():
            score = sum(all_text.count(keyword) for keyword in keywords)
            if score > 0:
                culture_scores[culture] = score
        
        primary_culture = max(culture_scores.items(), key=lambda x: x[1])[0] if culture_scores else "neutral"
        
        return {
            "culture_type": primary_culture,
            "persona_alignment": persona.value if hasattr(persona, 'value') else str(persona),
            "activity_level": "high" if len(message_contents) > 15 else "moderate" if len(message_contents) > 5 else "low",
            "confidence": min(len(message_contents) / 20, 1.0)
        }
    
    def _identify_user_interests(self, target_messages: List[str]) -> List[str]:
        """Identify user's interests from their messages."""
        if not target_messages:
            return ["general topics"]
        
        content = " ".join(target_messages).lower()
        
        interest_keywords = {
            "gaming": ["game", "play", "steam", "xbox", "playstation", "nintendo", "pc"],
            "anime": ["anime", "manga", "episode", "character", "season"],
            "music": ["music", "song", "band", "album", "listen", "spotify"],
            "technology": ["tech", "computer", "phone", "app", "software", "code"],
            "food": ["food", "cook", "eat", "recipe", "restaurant"],
            "fitness": ["gym", "workout", "exercise", "run", "lift", "fitness"],
            "movies": ["movie", "film", "watch", "netflix", "cinema"],
            "art": ["art", "draw", "paint", "design", "create"],
            "books": ["book", "read", "novel", "story", "author"],
            "travel": ["travel", "trip", "vacation", "visit", "country"]
        }
        
        interests = []
        for interest, keywords in interest_keywords.items():
            if any(keyword in content for keyword in keywords):
                interests.append(interest)
        
        return interests if interests else ["general topics"]
    
    def _analyze_user_interactions(self, recent_messages: List[Any], target_user_id: str, target_name: str) -> List[Dict[str, Any]]:
        """Analyze user's recent interactions with others."""
        interactions = []
        
        for msg in recent_messages[-20:]:
            if str(msg.author.id) == target_user_id:
                # Check for mentions of other users
                mentioned_users = []
                if hasattr(msg, 'mentions'):
                    mentioned_users = [user.display_name for user in msg.mentions if not user.bot]
                
                if mentioned_users or len(msg.content) > 20:
                    interactions.append({
                        "content_preview": msg.content[:50] + "..." if len(msg.content) > 50 else msg.content,
                        "mentioned_users": mentioned_users,
                        "message_length": len(msg.content),
                        "channel_id": str(msg.channel.id)
                    })
        
        return interactions[-5:]  # Keep last 5 interactions
    
    async def _calculate_relevance_factors(
        self,
        target_name: str,
        communication_style: Dict[str, Any],
        user_interests: List[str],
        active_topics: List[str],
        server_culture: Dict[str, Any],
        persona: PersonaType
    ) -> Dict[str, float]:
        """Use AI to calculate relevance factors for content generation."""
        
        prompt = f"""Analyze the following context to determine relevance factors for generating humorous leak content about {target_name}.

USER CONTEXT:
- Communication Style: {communication_style['style']} (confidence: {communication_style['confidence']:.2f})
- Average Message Length: {communication_style['avg_message_length']:.1f} characters
- Expressiveness: {communication_style['expressiveness']:.2f}
- User Interests: {', '.join(user_interests)}

SERVER CONTEXT:
- Active Topics: {', '.join(active_topics)}
- Server Culture: {server_culture['culture_type']}
- Activity Level: {server_culture['activity_level']}
- Bot Persona: {persona.value if hasattr(persona, 'value') else str(persona)}

Please provide relevance scores (0.0 to 1.0) for different content types:

GAMING_RELEVANCE: [0.0-1.0] - How relevant are gaming references?
SOCIAL_RELEVANCE: [0.0-1.0] - How relevant are social interaction themes?
HOBBY_RELEVANCE: [0.0-1.0] - How relevant are hobby/interest references?
MEME_RELEVANCE: [0.0-1.0] - How relevant is meme culture content?
PERSONALITY_RELEVANCE: [0.0-1.0] - How relevant are personality-based jokes?

Provide brief reasoning for each score."""
        
        try:
            response = await self._safe_ai_completion(
                prompt=prompt,
                temperature=0.3,
                max_tokens=300,
                fallback_response="GAMING_RELEVANCE: 0.5\nSOCIAL_RELEVANCE: 0.6\nHOBBY_RELEVANCE: 0.5\nMEME_RELEVANCE: 0.4\nPERSONALITY_RELEVANCE: 0.7"
            )
            
            relevance_factors = {
                "gaming": self._extract_score_from_response(response, "GAMING_RELEVANCE"),
                "social": self._extract_score_from_response(response, "SOCIAL_RELEVANCE"), 
                "hobby": self._extract_score_from_response(response, "HOBBY_RELEVANCE"),
                "meme": self._extract_score_from_response(response, "MEME_RELEVANCE"),
                "personality": self._extract_score_from_response(response, "PERSONALITY_RELEVANCE")
            }
            
            return relevance_factors
            
        except Exception as e:
            self.logger.warning(f"AI relevance calculation failed: {e}")
            # Fallback relevance based on interests
            fallback_factors = {"gaming": 0.5, "social": 0.6, "hobby": 0.5, "meme": 0.4, "personality": 0.7}
            
            # Adjust based on detected interests
            if "gaming" in user_interests:
                fallback_factors["gaming"] = 0.8
            if "memes" in active_topics or server_culture["culture_type"] == "meme-heavy":
                fallback_factors["meme"] = 0.8
            if communication_style["style"] in ["expressive", "energetic"]:
                fallback_factors["personality"] = 0.8
                
            return fallback_factors
    
    def _generate_reasoning_summary(
        self,
        target_name: str,
        communication_style: Dict[str, Any],
        active_topics: List[str],
        user_interests: List[str],
        relevance_factors: Dict[str, float]
    ) -> str:
        """Generate a summary of the reasoning process."""
        
        style_desc = f"{communication_style['style']} communicator with {communication_style['confidence']:.0%} confidence"
        interests_desc = ', '.join(user_interests[:3])
        topics_desc = ', '.join(active_topics[:3])
        
        top_relevance = max(relevance_factors.items(), key=lambda x: x[1])
        
        reasoning = f"""Context Analysis for {target_name}:

User Profile: {style_desc}
Primary Interests: {interests_desc}
Server Activity: {topics_desc}

Highest Relevance Factor: {top_relevance[0]} ({top_relevance[1]:.2f})
Content Strategy: Focus on {top_relevance[0]}-related humor with server culture integration."""
        
        return reasoning
    
    def _get_fallback_analysis(self, target_name: str, persona: PersonaType) -> ContextAnalysis:
        """Generate minimal fallback analysis."""
        return ContextAnalysis(
            user_communication_style={"style": "neutral", "confidence": 0.3},
            active_topics=["general chat"],
            server_culture_assessment={"culture_type": "neutral", "persona_alignment": persona.value if hasattr(persona, 'value') else str(persona)},
            relevance_factors={"gaming": 0.5, "social": 0.6, "hobby": 0.4, "meme": 0.4, "personality": 0.7},
            user_interests=["general topics"],
            recent_interactions=[],
            reasoning=f"Minimal context available for {target_name}. Using general content strategy."
        )