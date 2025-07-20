"""
Embedding and vector search service for The Snitch Discord Bot.
Handles message embeddings, similarity search, and semantic analysis.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import asyncio
import numpy as np

try:
    # Disable ChromaDB telemetry to avoid posthog errors
    import os
    os.environ['ANONYMIZED_TELEMETRY'] = 'False'
    
    import chromadb
    from chromadb.config import Settings
    from chromadb.utils import embedding_functions
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    chromadb = None

from src.models.message import Message
from src.models.server import ServerConfig
from src.core.exceptions import AIServiceError, ConfigurationError
from src.core.logging import get_logger, log_performance
from src.core.config import get_config

logger = get_logger(__name__)


class EmbeddingService:
    """Service for creating and searching message embeddings."""
    
    def __init__(self, collection_name: str = "message_embeddings"):
        self.collection_name = collection_name
        self.client = None
        self.collection = None
        self.embedding_function = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize ChromaDB client and collection."""
        if self._initialized:
            return
        
        if not CHROMADB_AVAILABLE:
            raise ConfigurationError("ChromaDB not available. Install with: pip install chromadb")
        
        try:
            config = get_config()
            
            # Initialize ChromaDB client
            self.client = chromadb.PersistentClient(
                path=config.CHROMA_DB_PATH,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # Set up embedding function
            self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"  # Fast, lightweight model
            )
            
            # Get or create collection
            try:
                self.collection = self.client.get_collection(
                    name=self.collection_name,
                    embedding_function=self.embedding_function
                )
                logger.info(f"Connected to existing ChromaDB collection: {self.collection_name}")
            except ValueError:
                # Collection doesn't exist, create it
                self.collection = self.client.create_collection(
                    name=self.collection_name,
                    embedding_function=self.embedding_function,
                    metadata={"description": "Discord message embeddings for The Snitch bot"}
                )
                logger.info(f"Created new ChromaDB collection: {self.collection_name}")
            
            self._initialized = True
            logger.info("EmbeddingService initialized successfully")
        
        except Exception as e:
            logger.error(f"Failed to initialize EmbeddingService: {e}")
            raise AIServiceError(f"Embedding service initialization failed: {e}")
    
    @log_performance("embed_messages")
    async def embed_messages(
        self,
        messages: List[Message],
        server_id: str,
        batch_size: int = 50
    ) -> int:
        """
        Create embeddings for a list of messages and store them.
        
        Args:
            messages: List of messages to embed
            server_id: Server ID for isolation
            batch_size: Number of messages to process in each batch
            
        Returns:
            Number of messages successfully embedded
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            embedded_count = 0
            
            # Process messages in batches
            for i in range(0, len(messages), batch_size):
                batch = messages[i:i + batch_size]
                
                # Prepare batch data
                ids = []
                documents = []
                metadatas = []
                
                for msg in batch:
                    # Create unique ID
                    doc_id = f"{server_id}_{msg.message_id}"
                    ids.append(doc_id)
                    
                    # Prepare document text (content + context)
                    doc_text = self._prepare_message_text(msg)
                    documents.append(doc_text)
                    
                    # Prepare metadata
                    metadata = {
                        "server_id": server_id,
                        "message_id": msg.message_id,
                        "channel_id": msg.channel_id,
                        "author_id": msg.author_id,
                        "timestamp": msg.timestamp_dt.timestamp(),
                        "engagement_score": msg.calculate_engagement_score(),
                        "controversy_score": msg.controversy_score,
                        "total_reactions": msg.total_reactions,
                        "reply_count": msg.reply_count,
                        "content_length": len(msg.content),
                        "has_attachments": len(msg.attachments) > 0,
                        "has_embeds": len(msg.embeds) > 0
                    }
                    metadatas.append(metadata)
                
                # Add batch to collection
                self.collection.add(
                    ids=ids,
                    documents=documents,
                    metadatas=metadatas
                )
                
                embedded_count += len(batch)
                
                # Small delay to prevent overwhelming the system
                if i + batch_size < len(messages):
                    await asyncio.sleep(0.1)
            
            logger.info(
                "Message embedding completed",
                server_id=server_id,
                total_messages=len(messages),
                embedded_count=embedded_count
            )
            
            return embedded_count
        
        except Exception as e:
            logger.error(f"Error embedding messages: {e}")
            raise AIServiceError(f"Message embedding failed: {e}")
    
    @log_performance("semantic_search")
    async def semantic_search(
        self,
        query_text: str,
        server_id: str,
        limit: int = 10,
        min_similarity: float = 0.3,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic search for similar messages.
        
        Args:
            query_text: Text to search for
            server_id: Server ID to search within
            limit: Maximum number of results
            min_similarity: Minimum similarity score (0-1)
            filters: Additional metadata filters
            
        Returns:
            List of similar messages with metadata and scores
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            # Build where clause for filtering
            where_clause = {"server_id": server_id}
            if filters:
                where_clause.update(filters)
            
            # Perform semantic search
            results = self.collection.query(
                query_texts=[query_text],
                n_results=limit,
                where=where_clause
            )
            
            # Process results
            search_results = []
            
            if results["documents"] and results["documents"][0]:
                for i, (doc, metadata, distance) in enumerate(zip(
                    results["documents"][0],
                    results["metadatas"][0],
                    results["distances"][0]
                )):
                    # Convert distance to similarity score (ChromaDB uses cosine distance)
                    similarity = 1 - distance
                    
                    # Filter by minimum similarity
                    if similarity >= min_similarity:
                        result = {
                            "message_id": metadata["message_id"],
                            "content": doc,
                            "similarity_score": similarity,
                            "metadata": metadata,
                            "rank": i + 1
                        }
                        search_results.append(result)
            
            logger.info(
                "Semantic search completed",
                query_length=len(query_text),
                server_id=server_id,
                results_found=len(search_results),
                limit=limit
            )
            
            return search_results
        
        except Exception as e:
            logger.error(f"Error in semantic search: {e}")
            raise AIServiceError(f"Semantic search failed: {e}")
    
    async def find_related_messages(
        self,
        message: Message,
        server_id: str,
        limit: int = 5,
        time_window_hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Find messages related to a given message using semantic similarity.
        
        Args:
            message: Reference message
            server_id: Server ID
            limit: Maximum number of related messages
            time_window_hours: Time window to search within
            
        Returns:
            List of related messages with similarity scores
        """
        try:
            # Create query from message content
            query_text = self._prepare_message_text(message)
            
            # Calculate time filter - ChromaDB doesn't support complex nested operators
            # We'll handle time filtering after the search
            msg_dt = message.timestamp_dt
            time_threshold = msg_dt.timestamp() - (time_window_hours * 3600)
            
            # Search for similar messages without time filter first
            related = await self.semantic_search(
                query_text=query_text,
                server_id=server_id,
                limit=limit + 20,  # Get more results to filter by time
                min_similarity=0.4
            )
            
            # Filter by time and exclude the original message
            related_messages = []
            for msg in related:
                # Skip the original message
                if msg["message_id"] == message.message_id:
                    continue
                
                # Check time window
                msg_timestamp = msg["metadata"].get("timestamp", 0)
                if msg_timestamp >= time_threshold:
                    related_messages.append(msg)
                
                # Stop when we have enough results
                if len(related_messages) >= limit:
                    break
            
            return related_messages
        
        except Exception as e:
            logger.error(f"Error finding related messages: {e}")
            return []
    
    async def get_trending_topics(
        self,
        server_id: str,
        time_window_hours: int = 24,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Identify trending topics using clustering of recent messages.
        
        Args:
            server_id: Server ID
            time_window_hours: Time window to analyze
            limit: Maximum number of topics
            
        Returns:
            List of trending topics with representative messages
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            # Get recent messages
            time_threshold = datetime.now().timestamp() - (time_window_hours * 3600)
            
            # Get all messages for the server and filter by time afterwards
            # ChromaDB doesn't support nested where operators
            recent_messages = self.collection.query(
                query_texts=[""],  # Empty query to get all
                n_results=500,  # Limit to recent messages
                where={"server_id": server_id}
            )
            
            if not recent_messages["documents"] or not recent_messages["documents"][0]:
                return []
            
            # Filter messages by time threshold
            filtered_messages = []
            for doc, metadata in zip(recent_messages["documents"][0], recent_messages["metadatas"][0]):
                if metadata.get("timestamp", 0) >= time_threshold:
                    filtered_messages.append((doc, metadata))
            
            if not filtered_messages:
                return []
            
            # Simple trending analysis based on engagement
            topics = []
            
            # Sort by engagement score
            filtered_messages.sort(
                key=lambda x: x[1]["engagement_score"],
                reverse=True
            )
            
            # Take top engaging messages as topic representatives
            for i, (content, metadata) in enumerate(filtered_messages[:limit]):
                topic = {
                    "topic_id": f"trending_{i+1}",
                    "representative_content": content[:100] + "..." if len(content) > 100 else content,
                    "engagement_score": metadata["engagement_score"],
                    "message_count": 1,  # Simplified - could implement proper clustering
                    "channel_id": metadata["channel_id"],
                    "timestamp": metadata["timestamp"]
                }
                topics.append(topic)
            
            logger.info(
                "Trending topics analysis completed",
                server_id=server_id,
                topics_found=len(topics),
                time_window_hours=time_window_hours
            )
            
            return topics
        
        except Exception as e:
            logger.error(f"Error getting trending topics: {e}")
            return []
    
    async def cleanup_old_embeddings(
        self,
        server_id: str,
        days_to_keep: int = 30
    ) -> int:
        """
        Clean up old embeddings to manage storage.
        
        Args:
            server_id: Server ID
            days_to_keep: Number of days of embeddings to keep
            
        Returns:
            Number of embeddings removed
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            # Calculate cutoff timestamp
            cutoff_time = datetime.now().timestamp() - (days_to_keep * 24 * 3600)
            
            # Get all embeddings for the server and filter by time afterwards
            # ChromaDB doesn't support nested where operators
            all_embeddings = self.collection.query(
                query_texts=[""],
                n_results=10000,  # Large number to get all
                where={"server_id": server_id}
            )
            
            if all_embeddings["ids"] and all_embeddings["ids"][0]:
                # Filter to find old embeddings
                old_ids = []
                for i, metadata in enumerate(all_embeddings["metadatas"][0]):
                    if metadata.get("timestamp", 0) < cutoff_time:
                        old_ids.append(all_embeddings["ids"][0][i])
                
                if old_ids:
                    # Delete old embeddings
                    self.collection.delete(ids=old_ids)
                    removed_count = len(old_ids)
                else:
                    removed_count = 0
                
                logger.info(
                    "Old embeddings cleaned up",
                    server_id=server_id,
                    removed_count=removed_count,
                    days_to_keep=days_to_keep
                )
                
                return removed_count
            
            return 0
        
        except Exception as e:
            logger.error(f"Error cleaning up embeddings: {e}")
            return 0
    
    def _prepare_message_text(self, message: Message) -> str:
        """Prepare message text for embedding."""
        
        # Start with main content
        text_parts = [message.content]
        
        # Add attachment info if present
        if message.attachments:
            attachment_info = f"[{len(message.attachments)} attachments]"
            text_parts.append(attachment_info)
        
        # Add embed info if present
        if message.embeds:
            embed_info = f"[{len(message.embeds)} embeds]"
            text_parts.append(embed_info)
        
        # Add engagement context
        if message.total_reactions > 0:
            engagement_info = f"[{message.total_reactions} reactions]"
            text_parts.append(engagement_info)
        
        if message.reply_count > 0:
            reply_info = f"[{message.reply_count} replies]"
            text_parts.append(reply_info)
        
        return " ".join(text_parts)
    
    async def get_collection_stats(self, server_id: str) -> Dict[str, Any]:
        """Get statistics about the embedding collection for a server."""
        if not self._initialized:
            await self.initialize()
        
        try:
            # Get server's embeddings
            results = self.collection.query(
                query_texts=[""],
                n_results=10000,
                where={"server_id": server_id}
            )
            
            if not results["metadatas"] or not results["metadatas"][0]:
                return {
                    "total_embeddings": 0,
                    "date_range": None,
                    "avg_engagement": 0,
                    "total_channels": 0
                }
            
            metadatas = results["metadatas"][0]
            
            # Calculate stats
            total_embeddings = len(metadatas)
            timestamps = [float(meta["timestamp"]) for meta in metadatas if "timestamp" in meta]
            engagement_scores = [meta["engagement_score"] for meta in metadatas if "engagement_score" in meta]
            channels = set(meta["channel_id"] for meta in metadatas if "channel_id" in meta)
            
            stats = {
                "total_embeddings": total_embeddings,
                "date_range": {
                    "earliest": min(timestamps) if timestamps else None,
                    "latest": max(timestamps) if timestamps else None
                },
                "avg_engagement": np.mean(engagement_scores) if engagement_scores else 0,
                "total_channels": len(channels)
            }
            
            return stats
        
        except Exception as e:
            logger.error(f"Error getting collection stats: {e}")
            return {}


# Global embedding service instance
_embedding_service: Optional[EmbeddingService] = None


async def get_embedding_service(collection_name: str = "message_embeddings") -> EmbeddingService:
    """Get or create the global embedding service."""
    global _embedding_service
    
    if _embedding_service is None:
        _embedding_service = EmbeddingService(collection_name)
        await _embedding_service.initialize()
    
    return _embedding_service