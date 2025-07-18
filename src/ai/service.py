"""
Main AI service that orchestrates all AI functionality for The Snitch Discord Bot.
Combines Groq client, embedding service, and newsletter pipeline.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging

from src.ai.groq_client import GroqClient, get_groq_client
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
        self.groq_client: Optional[GroqClient] = None
        self.newsletter_pipeline: Optional[NewsletterPipeline] = None
        self.embedding_service: Optional[EmbeddingService] = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize all AI services."""
        if self._initialized:
            return
        
        try:
            # Initialize core services
            self.groq_client = await get_groq_client()
            self.newsletter_pipeline = await get_newsletter_pipeline(self.groq_client)
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
            analysis = await self.groq_client.analyze_content(
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
            "groq_client": "unknown",
            "newsletter_pipeline": "unknown",
            "embedding_service": "unknown",
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            await self._ensure_initialized()
            health_status["ai_service"] = "healthy"
            
            # Check Groq client
            if self.groq_client:
                try:
                    # Simple test request
                    await self.groq_client.conversation_completion([
                        {"role": "user", "content": "Test"}
                    ], max_tokens=5)
                    health_status["groq_client"] = "healthy"
                except:
                    health_status["groq_client"] = "unhealthy"
            
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


# Global AI service instance
_ai_service: Optional[AIService] = None


async def get_ai_service() -> AIService:
    """Get or create the global AI service."""
    global _ai_service
    
    if _ai_service is None:
        _ai_service = AIService()
        await _ai_service.initialize()
    
    return _ai_service