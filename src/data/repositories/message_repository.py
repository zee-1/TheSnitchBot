"""
Message repository for The Snitch Discord Bot.
Handles CRUD operations for Discord messages in Azure Cosmos DB.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging

from src.data.repositories.base import BaseRepository
from src.models.message import Message
from src.core.exceptions import RepositoryError
from src.core.logging import get_logger

logger = get_logger(__name__)


class MessageRepository(BaseRepository[Message]):
    """Repository for managing Discord messages."""
    
    def __init__(self, cosmos_client, container_name: str):
        super().__init__(cosmos_client, container_name, Message)
    
    async def get_by_message_id(self, message_id: str) -> Optional[Message]:
        """Get a message by its Discord message ID."""
        try:
            # Use the base repository's get_by_id method
            # For messages, we'll use message_id as both id and partition key
            return await self.get_by_id(message_id, message_id)
            
        except Exception as e:
            logger.error(f"Error getting message by ID {message_id}: {e}")
            return None
    
    async def get_by_server_and_time_range(
        self,
        server_id: str,
        start_time: datetime,
        end_time: datetime,
        limit: Optional[int] = None
    ) -> List[Message]:
        """Get messages from a server within a time range."""
        # Mock implementation for now - will implement with proper querying later
        logger.info(f"Mock query for server {server_id} from {start_time} to {end_time}")
        return []
    
    async def get_by_channel_and_time_range(
        self,
        channel_id: str,
        start_time: datetime,
        end_time: datetime,
        limit: Optional[int] = None
    ) -> List[Message]:
        """Get messages from a specific channel within a time range."""
        # Mock implementation
        return []
    
    async def get_high_engagement_messages(
        self,
        server_id: str,
        start_time: datetime,
        min_engagement_score: float = 0.5,
        limit: int = 50
    ) -> List[Message]:
        """Get high-engagement messages from a server."""
        # Mock implementation
        return []
    
    async def get_by_author(
        self,
        author_id: str,
        server_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Message]:
        """Get messages by a specific author."""
        # Mock implementation
        return []
    
    async def get_controversial_messages(
        self,
        server_id: str,
        start_time: datetime,
        min_controversy_score: float = 0.5,
        limit: int = 20
    ) -> List[Message]:
        """Get controversial messages from a server."""
        # Mock implementation
        return []
    
    async def update_controversy_score(
        self,
        message_id: str,
        controversy_score: float
    ) -> bool:
        """Update the controversy score for a message."""
        try:
            message = await self.get_by_message_id(message_id)
            if not message:
                return False
            
            message.controversy_score = controversy_score
            message.updated_at = datetime.now()
            
            await self.update(message)
            return True
            
        except Exception as e:
            logger.error(f"Error updating controversy score for {message_id}: {e}")
            return False
    
    async def mark_excluded_from_analysis(
        self,
        message_id: str,
        excluded: bool = True
    ) -> bool:
        """Mark a message as excluded from analysis."""
        try:
            message = await self.get_by_message_id(message_id)
            if not message:
                return False
            
            message.excluded_from_analysis = excluded
            message.updated_at = datetime.now()
            
            await self.update(message)
            return True
            
        except Exception as e:
            logger.error(f"Error marking message {message_id} as excluded: {e}")
            return False
    
    async def cleanup_old_messages(
        self,
        server_id: str,
        days_to_keep: int = 30
    ) -> int:
        """Clean up old messages to manage storage."""
        # Mock implementation
        logger.info(f"Mock cleanup for server {server_id}, keeping {days_to_keep} days")
        return 0
    
    async def get_server_message_stats(self, server_id: str) -> Dict[str, Any]:
        """Get message statistics for a server."""
        # Mock implementation
        return {
            "total_messages": 0,
            "recent_messages_24h": 0,
            "server_id": server_id,
            "last_updated": datetime.now().isoformat()
        }