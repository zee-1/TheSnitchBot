"""
Main AI service that orchestrates all AI functionality for The Snitch Discord Bot.
Combines Groq client, embedding service, and newsletter pipeline.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging

from src.ai.llm_client import LLMClient, get_llm_client
from src.ai.pipeline import NewsletterPipeline, get_newsletter_pipeline
from src.ai.embedding_service import EmbeddingService, get_embedding_service
from src.models.message import Message
from src.models.server import ServerConfig, PersonaType
from src.models.newsletter import Newsletter
from src.core.exceptions import AIServiceError
from src.core.logging import get_logger, log_performance

logger = get_logger(__name__)


class AIService:
    """
    Main AI service that coordinates all AI functionality.
    
    Provides high-level interfaces for:
    - Newsletter generation with semantic enhancement
    - Message analysis and controversy detection
    - Content similarity and trending topics
    - Breaking news and fact-checking
    """
    
    def __init__(self):
        self.llm_client: Optional[LLMClient] = None
        self.newsletter_pipeline: Optional[NewsletterPipeline] = None
        self.embedding_service: Optional[EmbeddingService] = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize all AI services."""
        if self._initialized:
            return
        
        try:
            # Initialize core services
            self.llm_client = await get_llm_client()
            self.newsletter_pipeline = await get_newsletter_pipeline(self.llm_client)
            self.embedding_service = await get_embedding_service()
            
            self._initialized = True
            logger.info("AIService initialized successfully")
        
        except Exception as e:
            logger.error(f"Failed to initialize AIService: {e}")
            raise AIServiceError(f"AI service initialization failed: {e}")
    
    @log_performance("enhanced_newsletter_generation")
    async def generate_enhanced_newsletter(
        self,
        messages: List[Message],
        server_config: ServerConfig,
        newsletter: Newsletter,
        use_semantic_enhancement: bool = True
    ) -> Newsletter:
        """
        Generate newsletter with optional semantic enhancement.
        
        Args:
            messages: Recent messages to analyze
            server_config: Server configuration
            newsletter: Newsletter object to populate
            use_semantic_enhancement: Whether to use embedding-based enhancements
            
        Returns:
            Completed newsletter with generated content
        """
        await self._ensure_initialized()
        
        try:
            # Embed recent messages for semantic analysis
            if use_semantic_enhancement and messages:
                await self.embedding_service.embed_messages(
                    messages=messages,
                    server_id=server_config.server_id,
                    batch_size=25
                )
                
                # Get trending topics to add context
                trending_topics = await self.embedding_service.get_trending_topics(
                    server_id=server_config.server_id,
                    time_window_hours=24,
                    limit=3
                )
                
                # Add trending topics to additional context
                additional_context = {
                    "trending_topics": trending_topics,
                    "semantic_analysis_enabled": True
                }
            else:
                additional_context = {"semantic_analysis_enabled": False}
            
            # Generate newsletter using the pipeline
            completed_newsletter = await self.newsletter_pipeline.generate_newsletter(
                messages=messages,
                server_config=server_config,
                newsletter=newsletter,
                additional_context=additional_context
            )
            
            logger.info(
                "Enhanced newsletter generation completed",
                server_id=server_config.server_id,
                newsletter_id=newsletter.id,
                semantic_enhancement=use_semantic_enhancement,
                trending_topics_count=len(additional_context.get("trending_topics", []))
            )
            
            return completed_newsletter
        
        except Exception as e:
            logger.error(f"Enhanced newsletter generation failed: {e}")
            raise AIServiceError(f"Newsletter generation failed: {e}")
    
    async def analyze_message_controversy(
        self,
        message: Message,
        context_messages: Optional[List[Message]] = None
    ) -> Dict[str, Any]:
        """
        Analyze a message for controversy potential.
        
        Args:
            message: Message to analyze
            context_messages: Optional context messages for better analysis
            
        Returns:
            Controversy analysis results
        """
        await self._ensure_initialized()
        
        try:
            # Prepare analysis context
            content_to_analyze = message.content
            
            # Add context from related messages if available
            if context_messages:
                context_snippets = [
                    msg.content[:100] for msg in context_messages[-3:]
                ]
                content_to_analyze += f"\n\nContext: {' | '.join(context_snippets)}"
            
            # Use Groq client for controversy analysis
            analysis = await self.llm_client.analyze_content(
                content=content_to_analyze,
                analysis_type="controversy",
                context="Discord server message analysis"
            )
            
            # Enhance with semantic similarity if embedding service is available
            if hasattr(message, 'server_id'):
                related_messages = await self.embedding_service.find_related_messages(
                    message=message,
                    server_id=message.server_id,
                    limit=3
                )
                
                analysis["related_messages_count"] = len(related_messages)
                analysis["semantic_context"] = related_messages
            
            return analysis
        
        except Exception as e:
            logger.error(f"Controversy analysis failed: {e}")
            return {
                "controversy_score": 0.0,
                "confidence": 0.0,
                "error": str(e)
            }
    
    async def generate_smart_breaking_news(
        self,
        messages: List[Message],
        persona: PersonaType,
        server_id: str,
        channel_context: Optional[str] = None
    ) -> str:
        """
        Generate breaking news with semantic enhancement.
        
        Args:
            messages: Recent messages to analyze
            persona: Bot persona for writing style
            server_id: Server ID for context
            channel_context: Optional channel context
            
        Returns:
            Breaking news bulletin text
        """
        await self._ensure_initialized()
        
        try:
            # Embed messages for semantic analysis
            if messages:
                await self.embedding_service.embed_messages(
                    messages=messages,
                    server_id=server_id,
                    batch_size=10
                )
            
            # Get trending topics for context
            trending_topics = await self.embedding_service.get_trending_topics(
                server_id=server_id,
                time_window_hours=2,  # Shorter window for breaking news
                limit=2
            )
            
            # Enhance channel context with trending info
            enhanced_context = channel_context or "Recent channel activity"
            if trending_topics:
                topic_summaries = [topic["representative_content"] for topic in trending_topics]
                enhanced_context += f" | Current trends: {', '.join(topic_summaries)}"
            
            # Generate breaking news
            bulletin = await self.newsletter_pipeline.generate_breaking_news(
                messages=messages,
                persona=persona,
                channel_context=enhanced_context
            )
            
            return bulletin
        
        except Exception as e:
            logger.error(f"Smart breaking news generation failed: {e}")
            # Fallback to basic generation
            return await self.newsletter_pipeline.generate_breaking_news(
                messages=messages,
                persona=persona,
                channel_context=channel_context
            )
    
    async def find_similar_content(
        self,
        query_text: str,
        server_id: str,
        limit: int = 5,
        time_window_hours: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Find content similar to the query using semantic search.
        
        Args:
            query_text: Text to search for
            server_id: Server ID to search within
            limit: Maximum number of results
            time_window_hours: Optional time window to search within
            
        Returns:
            List of similar messages with metadata
        """
        await self._ensure_initialized()
        
        try:
            # Prepare filters
            filters = {}
            if time_window_hours:
                cutoff_time = datetime.now().timestamp() - (time_window_hours * 3600)
                filters["timestamp"] = {"$gte": cutoff_time}
            
            # Perform semantic search
            results = await self.embedding_service.semantic_search(
                query_text=query_text,
                server_id=server_id,
                limit=limit,
                min_similarity=0.3,
                filters=filters
            )
            
            return results
        
        except Exception as e:
            logger.error(f"Similar content search failed: {e}")
            return []
    
    async def get_server_insights(
        self,
        server_id: str,
        time_window_hours: int = 24
    ) -> Dict[str, Any]:
        """
        Get comprehensive insights about server activity.
        
        Args:
            server_id: Server ID
            time_window_hours: Time window to analyze
            
        Returns:
            Server insights dictionary
        """
        await self._ensure_initialized()
        
        try:
            # Get embedding collection stats
            embedding_stats = await self.embedding_service.get_collection_stats(server_id)
            
            # Get trending topics
            trending_topics = await self.embedding_service.get_trending_topics(
                server_id=server_id,
                time_window_hours=time_window_hours,
                limit=5
            )
            
            insights = {
                "server_id": server_id,
                "analysis_window_hours": time_window_hours,
                "embedding_stats": embedding_stats,
                "trending_topics": trending_topics,
                "analysis_timestamp": datetime.now().isoformat()
            }
            
            return insights
        
        except Exception as e:
            logger.error(f"Server insights generation failed: {e}")
            return {
                "server_id": server_id,
                "error": str(e),
                "analysis_timestamp": datetime.now().isoformat()
            }
    
    async def generate_community_pulse(
        self,
        messages: List[Message],
        metrics: Dict[str, Any],
        server_config: ServerConfig,
        timeframe: str,
        style: str = "dashboard",
        focus: str = "overall"
    ) -> Dict[str, Any]:
        """
        Generate community pulse analysis with social insights.
        
        Args:
            messages: Recent messages to analyze
            metrics: Pre-calculated metrics
            server_config: Server configuration
            timeframe: Time period analyzed
            style: Presentation style
            focus: Focus area for analysis
            
        Returns:
            Community pulse analysis results
        """
        await self._ensure_initialized()
        
        try:
            # Build context for AI analysis
            context = self._build_pulse_context(messages, metrics, timeframe, focus)
            
            # Generate AI insights based on focus
            insights = await self._generate_pulse_insights(
                context=context,
                server_config=server_config,
                style=style,
                focus=focus
            )
            
            # Add semantic analysis if available
            if messages:
                try:
                    # Get trending topics for additional context
                    trending_topics = await self.embedding_service.get_trending_topics(
                        server_id=server_config.server_id,
                        time_window_hours=self._parse_timeframe_hours(timeframe),
                        limit=3
                    )
                    insights["trending_topics"] = trending_topics
                except Exception as e:
                    logger.warning(f"Failed to get trending topics: {e}")
                    insights["trending_topics"] = []
            
            # Package results
            analysis_result = {
                "summary": insights.get("summary", "Community pulse analysis complete"),
                "insights": insights.get("insights", "No specific insights available"),
                "story": insights.get("story", "Your community story"),
                "mood_analysis": insights.get("mood_analysis", "Mood analysis pending"),
                "social_patterns": insights.get("social_patterns", []),
                "recommendations": insights.get("recommendations", []),
                "trending_topics": insights.get("trending_topics", []),
                "style": style,
                "focus": focus,
                "timeframe": timeframe,
                "generated_at": datetime.now().isoformat()
            }
            
            logger.info(
                "Community pulse analysis completed",
                server_id=server_config.server_id,
                timeframe=timeframe,
                style=style,
                focus=focus,
                message_count=len(messages)
            )
            
            return analysis_result
        
        except Exception as e:
            logger.error(f"Community pulse generation failed: {e}")
            return {
                "summary": "Community pulse analysis encountered an error",
                "insights": f"Analysis failed: {str(e)}",
                "story": "The community story could not be generated at this time",
                "error": str(e),
                "generated_at": datetime.now().isoformat()
            }
    
    def _build_pulse_context(self, messages: List[Message], metrics: Dict[str, Any], timeframe: str, focus: str) -> str:
        """Build context string for AI analysis."""
        # Extract key information for AI processing
        message_samples = []
        if messages:
            # Get diverse message samples
            sorted_messages = sorted(messages, key=lambda x: x.total_reactions + x.reply_count * 2, reverse=True)
            top_messages = sorted_messages[:5]  # Top engaging messages
            recent_messages = sorted(messages, key=lambda x: x.timestamp, reverse=True)[:3]  # Most recent
            
            for msg in top_messages + recent_messages:
                if msg not in message_samples:
                    message_samples.append(f"User {msg.author_id}: {msg.content[:100]}")
        
        context = f"""
Community Pulse Analysis Context:
Timeframe: {timeframe}
Focus: {focus}
Total Messages: {metrics['total_messages']}
Active Users: {metrics['unique_users']}
Engagement Rate: {metrics['engagement_rate']:.2f}
Mood Score: {metrics['mood_score']:.0f}%
Conversations: {metrics['conversation_chains']}

Sample Messages:
{chr(10).join(message_samples[:8])}

Analysis Focus: {focus}
"""
        return context
    
    async def _generate_pulse_insights(
        self,
        context: str,
        server_config: ServerConfig,
        style: str,
        focus: str
    ) -> Dict[str, Any]:
        """Generate AI insights for community pulse."""
        try:
            # Create prompt based on style and focus
            prompt = self._create_pulse_prompt(context, server_config.persona, style, focus)
            
            # Generate insights using Groq
            response_text = await self.llm_client.conversation_completion([
                {"role": "system", "content": "You are a community analyst generating insights about Discord server social dynamics."},
                {"role": "user", "content": prompt}
            ], max_tokens=1500)
            
            # Response is already the text content from conversation_completion
            if not response_text:
                response_text = "Analysis not available"
            
            # Extract structured information from response
            insights = self._parse_pulse_response(response_text, style, focus)
            
            return insights
        
        except Exception as e:
            logger.error(f"AI insight generation failed: {e}")
            return {
                "summary": "Community pulse summary not available",
                "insights": f"Insight generation failed: {str(e)}",
                "story": "Community story generation failed"
            }
    
    def _create_pulse_prompt(self, context: str, persona: PersonaType, style: str, focus: str) -> str:
        """Create AI prompt for pulse analysis."""
        persona_style = {
            PersonaType.SASSY_REPORTER: "sassy and entertaining",
            PersonaType.INVESTIGATIVE_JOURNALIST: "professional and analytical",
            PersonaType.GOSSIP_COLUMNIST: "gossipy and dramatic",
            PersonaType.SPORTS_COMMENTATOR: "energetic and competitive",
            PersonaType.WEATHER_ANCHOR: "descriptive and forecasting",
            PersonaType.CONSPIRACY_THEORIST: "suspicious and theorizing"
        }.get(persona, "balanced and informative")
        
        style_instructions = {
            "dashboard": "Create a structured, metric-focused analysis",
            "story": "Write a narrative story about the community",
            "weather": "Present as a weather-style report",
            "gaming": "Use gaming terminology and stats",
            "network": "Focus on social connections and patterns"
        }.get(style, "Create a balanced analysis")
        
        focus_instructions = {
            "overall": "Provide comprehensive community overview",
            "social": "Focus on user relationships and interactions",
            "topics": "Highlight trending topics and discussions",
            "mood": "Analyze community mood and sentiment",
            "activity": "Focus on activity patterns and engagement",
            "patterns": "Identify hidden social patterns"
        }.get(focus, "Provide general insights")
        
        return f"""
Analyze this Discord community data with a {persona_style} tone:

{context}

Instructions:
- {style_instructions}
- {focus_instructions}
- Keep insights engaging and actionable
- Highlight positive community aspects
- Identify interesting social patterns
- Suggest ways to improve engagement

Provide your analysis in this format:
SUMMARY: [Brief 1-2 sentence overview]
INSIGHTS: [Key insights and observations]
STORY: [Narrative description if style is story]
PATTERNS: [Social patterns discovered]
RECOMMENDATIONS: [Actionable suggestions]
"""
    
    def _parse_pulse_response(self, response_text: str, style: str, focus: str) -> Dict[str, Any]:
        """Parse AI response into structured insights."""
        insights = {
            "summary": "Community analysis complete",
            "insights": "Key insights generated",
            "story": "Community story",
            "patterns": [],
            "recommendations": []
        }
        
        try:
            # Extract sections from response
            lines = response_text.split('\n')
            current_section = None
            
            for line in lines:
                line = line.strip()
                if line.startswith("SUMMARY:"):
                    current_section = "summary"
                    insights["summary"] = line.replace("SUMMARY:", "").strip()
                elif line.startswith("INSIGHTS:"):
                    current_section = "insights"
                    insights["insights"] = line.replace("INSIGHTS:", "").strip()
                elif line.startswith("STORY:"):
                    current_section = "story"
                    insights["story"] = line.replace("STORY:", "").strip()
                elif line.startswith("PATTERNS:"):
                    current_section = "patterns"
                elif line.startswith("RECOMMENDATIONS:"):
                    current_section = "recommendations"
                elif line and current_section:
                    # Append to current section
                    if current_section in ["summary", "insights", "story"]:
                        insights[current_section] += " " + line
                    elif current_section in ["patterns", "recommendations"]:
                        if line.startswith("-") or line.startswith("•"):
                            insights[current_section].append(line[1:].strip())
                        else:
                            insights[current_section].append(line)
        
        except Exception as e:
            logger.warning(f"Failed to parse pulse response: {e}")
        
        return insights
    
    def _parse_timeframe_hours(self, timeframe: str) -> int:
        """Convert timeframe string to hours."""
        timeframe_map = {
            "1h": 1,
            "6h": 6, 
            "24h": 24,
            "7d": 168,
            "30d": 720
        }
        return timeframe_map.get(timeframe, 24)
    
    async def cleanup_server_data(
        self,
        server_id: str,
        days_to_keep: int = 30
    ) -> Dict[str, int]:
        """
        Clean up old server data to manage storage.
        
        Args:
            server_id: Server ID
            days_to_keep: Number of days to keep
            
        Returns:
            Cleanup statistics
        """
        await self._ensure_initialized()
        
        try:
            # Clean up embeddings
            embeddings_removed = await self.embedding_service.cleanup_old_embeddings(
                server_id=server_id,
                days_to_keep=days_to_keep
            )
            
            cleanup_stats = {
                "embeddings_removed": embeddings_removed,
                "days_kept": days_to_keep,
                "cleanup_timestamp": datetime.now().isoformat()
            }
            
            logger.info(
                "Server data cleanup completed",
                server_id=server_id,
                **cleanup_stats
            )
            
            return cleanup_stats
        
        except Exception as e:
            logger.error(f"Server data cleanup failed: {e}")
            return {"error": str(e)}
    
    async def health_check(self) -> Dict[str, Any]:
        """Check the health of all AI services."""
        health_status = {
            "ai_service": "unknown",
            "llm_client": "unknown",
            "newsletter_pipeline": "unknown",
            "embedding_service": "unknown",
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            await self._ensure_initialized()
            health_status["ai_service"] = "healthy"
            
            # Check Groq client
            if self.llm_client:
                try:
                    # Simple test request
                    await self.llm_client.conversation_completion([
                        {"role": "user", "content": "Test"}
                    ], max_tokens=5)
                    health_status["llm_client"] = "healthy"
                except:
                    health_status["llm_client"] = "unhealthy"
            
            # Check newsletter pipeline
            if self.newsletter_pipeline:
                health_status["newsletter_pipeline"] = "healthy"
            
            # Check embedding service
            if self.embedding_service and self.embedding_service._initialized:
                try:
                    # Test collection access
                    await self.embedding_service.get_collection_stats("health_check")
                    health_status["embedding_service"] = "healthy"
                except:
                    health_status["embedding_service"] = "unhealthy"
        
        except Exception as e:
            health_status["ai_service"] = "unhealthy"
            health_status["error"] = str(e)
        
        return health_status
    
    async def _ensure_initialized(self) -> None:
        """Ensure the service is initialized."""
        if not self._initialized:
            await self.initialize()

    async def generate_leaks(self,target_users,target_messages):
        pass

# Global AI service instance
_ai_service: Optional[AIService] = None


async def get_ai_service() -> AIService:
    """Get or create the global AI service."""
    global _ai_service
    
    if _ai_service is None:
        _ai_service = AIService()
        await _ai_service.initialize()
    
    return _ai_service