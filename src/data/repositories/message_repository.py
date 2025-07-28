"""
Message repository for The Snitch Discord Bot.
Handles CRUD operations for Discord messages in Azure Cosmos DB.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging

from src.data.repositories.base import BaseRepository
from src.data.cosmos_client import CosmosDBClient
from src.models.message import Message
from src.core.logging import get_logger

logger = get_logger(__name__)


class MessageRepository(BaseRepository[Message]):
    """Repository for managing Discord messages."""
    
    def __init__(self, cosmos_client: CosmosDBClient, container_name: str):
        super().__init__(cosmos_client, container_name, Message)
    
    async def get_by_message_id(self, message_id: str, server_id: str) -> Optional[Message]:
        """Get a message by its Discord message ID within a server."""
        try:
            return await self.get_by_id(message_id, server_id)
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
        try:
            query = """
            SELECT * FROM c 
            WHERE c.server_id = @server_id 
            AND c.entity_type = 'message'
            AND c.timestamp >= @start_time 
            AND c.timestamp <= @end_time
            AND (c.excluded_from_analysis = false OR NOT IS_DEFINED(c.excluded_from_analysis))
            ORDER BY c.timestamp DESC
            """
            parameters = [
                {"name": "@server_id", "value": server_id},
                {"name": "@start_time", "value": start_time.isoformat()},
                {"name": "@end_time", "value": end_time.isoformat()}
            ]
            
            return await self.query(
                query=query,
                parameters=parameters,
                partition_key=server_id,
                max_count=limit
            )
        except Exception as e:
            logger.error(f"Error getting messages for server {server_id} in time range: {e}")
            return []
    
    async def get_by_channel_and_time_range(
        self,
        channel_id: str,
        server_id: str,
        start_time: datetime,
        end_time: datetime,
        limit: Optional[int] = None
    ) -> List[Message]:
        """Get messages from a specific channel within a time range."""
        try:
            query = """
            SELECT * FROM c 
            WHERE c.server_id = @server_id 
            AND c.channel_id = @channel_id
            AND c.entity_type = 'message'
            AND c.timestamp >= @start_time 
            AND c.timestamp <= @end_time
            AND (c.excluded_from_analysis = false OR NOT IS_DEFINED(c.excluded_from_analysis))
            ORDER BY c.timestamp DESC
            """
            parameters = [
                {"name": "@server_id", "value": server_id},
                {"name": "@channel_id", "value": channel_id},
                {"name": "@start_time", "value": start_time.isoformat()},
                {"name": "@end_time", "value": end_time.isoformat()}
            ]
            
            return await self.query(
                query=query,
                parameters=parameters,
                partition_key=server_id,
                max_count=limit
            )
        except Exception as e:
            logger.error(f"Error getting messages for channel {channel_id}: {e}")
            return []
    
    async def get_recent_messages(
        self,
        server_id: str,
        hours: int = 24,
        limit: Optional[int] = None
    ) -> List[Message]:
        """Get recent messages from a server."""
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)
        
        return await self.get_by_server_and_time_range(
            server_id=server_id,
            start_time=start_time,
            end_time=end_time,
            limit=limit
        )
     
    async def get_recent_channel_messages(
        self,
        channel_id: str,
        server_id: str,
        count: int = 50
    ) -> List[Message]:
        """Get the most recent messages from a specific channel."""
        try:
            query = """
            SELECT * FROM c 
            WHERE c.server_id = @server_id 
            AND c.channel_id = @channel_id
            AND c.entity_type = 'message'
            AND (c.excluded_from_analysis = false OR NOT IS_DEFINED(c.excluded_from_analysis))
            ORDER BY c.timestamp DESC
            """
            parameters = [
                {"name": "@server_id", "value": server_id},
                {"name": "@channel_id", "value": channel_id}
            ]
            
            return await self.query(
                query=query,
                parameters=parameters,
                partition_key=server_id,
                max_count=count
            )
        except Exception as e:
            logger.error(f"Error getting recent messages for channel {channel_id}: {e}")
            return []
    
    async def get_high_engagement_messages(
        self,
        server_id: str,
        start_time: datetime,
        min_engagement_score: float = 0.5,
        limit: int = 50
    ) -> List[Message]:
        """Get high-engagement messages from a server."""
        try:
            # Calculate engagement score in the query based on reactions and replies
            query = """
            SELECT * FROM c 
            WHERE c.server_id = @server_id 
            AND c.entity_type = 'message'
            AND c.timestamp >= @start_time
            AND (c.excluded_from_analysis = false OR NOT IS_DEFINED(c.excluded_from_analysis))
            AND (c.total_reactions + c.reply_count * 2) >= @min_engagement
            ORDER BY (c.total_reactions + c.reply_count * 2) DESC
            """
            parameters = [
                {"name": "@server_id", "value": server_id},
                {"name": "@start_time", "value": start_time.isoformat()},
                {"name": "@min_engagement", "value": int(min_engagement_score * 10)}  # Scale for integer comparison
            ]
            
            return await self.query(
                query=query,
                parameters=parameters,
                partition_key=server_id,
                max_count=limit
            )
        except Exception as e:
            logger.error(f"Error getting high engagement messages for server {server_id}: {e}")
            return []
    
    async def get_by_author(
        self,
        author_id: str,
        server_id: str,
        limit: int = 50
    ) -> List[Message]:
        """Get messages by a specific author."""
        try:
            query = """
            SELECT * FROM c 
            WHERE c.server_id = @server_id 
            AND c.author_id = @author_id
            AND c.entity_type = 'message'
            AND (c.excluded_from_analysis = false OR NOT IS_DEFINED(c.excluded_from_analysis))
            ORDER BY c.timestamp DESC
            """
            parameters = [
                {"name": "@server_id", "value": server_id},
                {"name": "@author_id", "value": author_id}
            ]
            
            return await self.query(
                query=query,
                parameters=parameters,
                partition_key=server_id,
                max_count=limit
            )
        except Exception as e:
            logger.error(f"Error getting messages by author {author_id}: {e}")
            return []
    
    async def get_controversial_messages(
        self,
        server_id: str,
        start_time: datetime,
        min_controversy_score: float = 0.5,
        limit: int = 20
    ) -> List[Message]:
        """Get controversial messages from a server."""
        try:
            query = """
            SELECT * FROM c 
            WHERE c.server_id = @server_id 
            AND c.entity_type = 'message'
            AND c.timestamp >= @start_time
            AND c.controversy_score >= @min_controversy
            AND (c.excluded_from_analysis = false OR NOT IS_DEFINED(c.excluded_from_analysis))
            ORDER BY c.controversy_score DESC, c.timestamp DESC
            """
            parameters = [
                {"name": "@server_id", "value": server_id},
                {"name": "@start_time", "value": start_time.isoformat()},
                {"name": "@min_controversy", "value": min_controversy_score}
            ]
            
            return await self.query(
                query=query,
                parameters=parameters,
                partition_key=server_id,
                max_count=limit
            )
        except Exception as e:
            logger.error(f"Error getting controversial messages for server {server_id}: {e}")
            return []
    
    async def get_newsworthy_messages(
        self,
        server_id: str,
        start_time: datetime,
        limit: int = 100
    ) -> List[Message]:
        """Get messages that are potentially newsworthy based on multiple criteria."""
        try:
            query = """
            SELECT * FROM c 
            WHERE c.server_id = @server_id 
            AND c.entity_type = 'message'
            AND c.timestamp >= @start_time
            AND (c.excluded_from_analysis = false OR NOT IS_DEFINED(c.excluded_from_analysis))
            AND (
                c.controversy_score >= 0.3 
                OR c.total_reactions >= 3 
                OR c.reply_count >= 2
                OR c.word_count >= 20
            )
            ORDER BY (c.controversy_score * 2 + c.total_reactions + c.reply_count * 2) DESC
            """
            parameters = [
                {"name": "@server_id", "value": server_id},
                {"name": "@start_time", "value": start_time.isoformat()}
            ]
            
            return await self.query(
                query=query,
                parameters=parameters,
                partition_key=server_id,
                max_count=limit
            )
        except Exception as e:
            logger.error(f"Error getting newsworthy messages for server {server_id}: {e}")
            return []
    
    async def update_controversy_score(
        self,
        message_id: str,
        server_id: str,
        controversy_score: float
    ) -> bool:
        """Update the controversy score for a message."""
        try:
            message = await self.get_by_message_id(message_id, server_id)
            if not message:
                return False
            
            message.controversy_score = controversy_score
            message.update_timestamp()
            
            await self.update(message)
            return True
            
        except Exception as e:
            logger.error(f"Error updating controversy score for {message_id}: {e}")
            return False
    
    async def mark_excluded_from_analysis(
        self,
        message_id: str,
        server_id: str,
        excluded: bool = True
    ) -> bool:
        """Mark a message as excluded from analysis."""
        try:
            message = await self.get_by_message_id(message_id, server_id)
            if not message:
                return False
            
            message.excluded_from_analysis = excluded
            message.update_timestamp()
            
            await self.update(message)
            return True
            
        except Exception as e:
            logger.error(f"Error marking message {message_id} as excluded: {e}")
            return False
    
    async def mark_processed_for_newsletter(
        self,
        message_id: str,
        server_id: str,
        processed: bool = True
    ) -> bool:
        """Mark a message as processed for newsletter."""
        try:
            message = await self.get_by_message_id(message_id, server_id)
            if not message:
                return False
            
            message.processed_for_newsletter = processed
            message.update_timestamp()
            
            await self.update(message)
            return True
            
        except Exception as e:
            logger.error(f"Error marking message {message_id} as processed: {e}")
            return False
    
    async def add_message_from_discord(self, discord_message, server_id: str) -> Message:
        """Create and store a message from a Discord message object."""
        try:
            # Convert Discord message to our Message model
            message = Message.from_discord_message(discord_message, server_id)
            
            # Store in database
            return await self.create(message)
            
        except Exception as e:
            logger.error(f"Error adding message from Discord: {e}")
            raise
    
    async def update_message_reactions(
        self,
        message_id: str,
        server_id: str,
        reactions_data: List[Dict[str, Any]]
    ) -> bool:
        """Update message reactions."""
        try:
            message = await self.get_by_message_id(message_id, server_id)
            if not message:
                return False
            
            # Clear existing reactions and add new ones
            message.reactions = []
            for reaction_data in reactions_data:
                message.add_reaction(reaction_data["emoji"], reaction_data["user_id"])
            
            message.update_metrics()
            await self.update(message)
            return True
            
        except Exception as e:
            logger.error(f"Error updating reactions for message {message_id}: {e}")
            return False
    
    async def cleanup_old_messages(
        self,
        server_id: str,
        days_to_keep: int = 30
    ) -> int:
        """Clean up old messages to manage storage."""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            query = """
            SELECT * FROM c 
            WHERE c.server_id = @server_id 
            AND c.timestamp < @cutoff_date
            AND c.processed_for_newsletter = true
            """
            parameters = [
                {"name": "@server_id", "value": server_id},
                {"name": "@cutoff_date", "value": cutoff_date.isoformat()}
            ]
            
            old_messages = await self.query(
                query=query,
                parameters=parameters,
                partition_key=server_id
            )
            
            deleted_count = 0
            for message in old_messages:
                success = await self.delete(message.id, server_id)
                if success:
                    deleted_count += 1
            
            logger.info(f"Cleaned up {deleted_count} old messages for server {server_id}")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error cleaning up old messages for server {server_id}: {e}")
            return 0
    
    async def get_server_message_stats(self, server_id: str) -> Dict[str, Any]:
        """Get message statistics for a server."""
        try:
            # Total messages
            total_messages = await self.count(partition_key=server_id)
            
            # Recent messages (24h)
            recent_cutoff = datetime.now() - timedelta(hours=24)
            recent_messages = await self.count(
                partition_key=server_id,
                where_clause=f"c.timestamp >= '{recent_cutoff.isoformat()}'"
            )
            
            # High engagement messages
            high_engagement = await self.count(
                partition_key=server_id,
                where_clause="c.total_reactions >= 5 OR c.reply_count >= 3"
            )
            
            # Controversial messages
            controversial = await self.count(
                partition_key=server_id,
                where_clause="c.controversy_score >= 0.5"
            )
            
            return {
                "total_messages": total_messages,
                "recent_messages_24h": recent_messages,
                "high_engagement_messages": high_engagement,
                "controversial_messages": controversial,
                "server_id": server_id,
                "last_updated": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting message stats for server {server_id}: {e}")
            return {
                "total_messages": 0,
                "recent_messages_24h": 0,
                "high_engagement_messages": 0,
                "controversial_messages": 0,
                "server_id": server_id,
                "last_updated": datetime.now().isoformat(),
                "error": str(e)
            }
    
    async def search_messages(
        self,
        server_id: str,
        search_term: str,
        limit: int = 50
    ) -> List[Message]:
        """Search messages by content."""
        try:
            query = """
            SELECT * FROM c 
            WHERE c.server_id = @server_id
            AND c.entity_type = 'message'
            AND CONTAINS(UPPER(c.content), UPPER(@search_term))
            AND (c.excluded_from_analysis = false OR NOT IS_DEFINED(c.excluded_from_analysis))
            ORDER BY c.timestamp DESC
            """
            parameters = [
                {"name": "@server_id", "value": server_id},
                {"name": "@search_term", "value": search_term}
            ]
            
            return await self.query(
                query=query,
                parameters=parameters,
                partition_key=server_id,
                max_count=limit
            )
            
        except Exception as e:
            logger.error(f"Error searching messages in server {server_id}: {e}")
            return []
    
    async def get_messages_with_keywords(
        self,
        server_id: str,
        keywords: List[str],
        start_time: datetime,
        limit: int = 100
    ) -> List[Message]:
        """Get messages containing specific keywords."""
        try:
            # Build query conditions for keywords
            keyword_conditions = []
            parameters = [
                {"name": "@server_id", "value": server_id},
                {"name": "@start_time", "value": start_time.isoformat()}
            ]
            
            for i, keyword in enumerate(keywords):
                keyword_conditions.append(f"CONTAINS(UPPER(c.content), UPPER(@keyword{i}))")
                parameters.append({"name": f"@keyword{i}", "value": keyword})
            
            keyword_clause = " OR ".join(keyword_conditions)
            
            query = f"""
            SELECT * FROM c 
            WHERE c.server_id = @server_id
            AND c.entity_type = 'message'
            AND c.timestamp >= @start_time
            AND ({keyword_clause})
            AND (c.excluded_from_analysis = false OR NOT IS_DEFINED(c.excluded_from_analysis))
            ORDER BY c.timestamp DESC
            """
            
            return await self.query(
                query=query,
                parameters=parameters,
                partition_key=server_id,
                max_count=limit
            )
            
        except Exception as e:
            logger.error(f"Error getting messages with keywords for server {server_id}: {e}")
            return []