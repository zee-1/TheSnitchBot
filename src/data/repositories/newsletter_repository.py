"""
Newsletter repository for The Snitch Discord Bot.
Handles newsletter generation and delivery tracking CRUD operations.
"""

from typing import List, Optional
from datetime import datetime, date, timedelta
import logging

from src.models.newsletter import Newsletter, NewsletterStatus, NewsletterType, StoryData
from src.data.repositories.base import BaseRepository
from src.data.cosmos_client import CosmosDBClient

logger = logging.getLogger(__name__)


class NewsletterRepository(BaseRepository[Newsletter]):
    """Repository for newsletter operations."""
    
    def __init__(self, cosmos_client: CosmosDBClient, container_name: str):
        super().__init__(cosmos_client, container_name, Newsletter)
    
    async def create_daily_newsletter(
        self,
        server_id: str,
        newsletter_date: date,
        time_period_start: datetime,
        time_period_end: datetime
    ) -> Newsletter:
        """Create a new daily newsletter."""
        newsletter = Newsletter.create_daily_newsletter(
            server_id=server_id,
            newsletter_date=newsletter_date,
            time_period_start=time_period_start,
            time_period_end=time_period_end
        )
        
        return await self.create(newsletter)
    
    async def get_newsletter_by_id(self, newsletter_id: str, server_id: str) -> Optional[Newsletter]:
        """Get newsletter by ID within a server."""
        return await self.get_by_id(newsletter_id, server_id)
    
    async def get_newsletter_by_date(self, server_id: str, newsletter_date: date) -> Optional[Newsletter]:
        """Get newsletter for a specific date."""
        query = "SELECT * FROM c WHERE c.server_id = @server_id AND c.newsletter_date = @date"
        parameters = [
            {"name": "@server_id", "value": server_id},
            {"name": "@date", "value": newsletter_date.isoformat()}
        ]
        
        results = await self.query(
            query=query,
            parameters=parameters,
            partition_key=server_id,
            max_count=1
        )
        
        return results[0] if results else None
    
    async def get_newsletters_by_server(
        self, 
        server_id: str,
        status: Optional[NewsletterStatus] = None,
        newsletter_type: Optional[NewsletterType] = None,
        max_count: Optional[int] = None
    ) -> List[Newsletter]:
        """Get newsletters for a server with optional filters."""
        conditions = ["c.server_id = @server_id"]
        parameters = [{"name": "@server_id", "value": server_id}]
        
        if status:
            conditions.append("c.status = @status")
            parameters.append({"name": "@status", "value": status.value})
        
        if newsletter_type:
            conditions.append("c.newsletter_type = @type")
            parameters.append({"name": "@type", "value": newsletter_type.value})
        
        query = f"SELECT * FROM c WHERE {' AND '.join(conditions)} ORDER BY c.newsletter_date DESC"
        
        return await self.query(
            query=query,
            parameters=parameters,
            partition_key=server_id,
            max_count=max_count
        )
    
    async def get_recent_newsletters(
        self, 
        server_id: str, 
        days: int = 30,
        max_count: Optional[int] = None
    ) -> List[Newsletter]:
        """Get newsletters from the last N days."""
        cutoff_date = date.today() - timedelta(days=days)
        
        query = """
        SELECT * FROM c 
        WHERE c.server_id = @server_id 
        AND c.newsletter_date >= @cutoff_date
        ORDER BY c.newsletter_date DESC
        """
        parameters = [
            {"name": "@server_id", "value": server_id},
            {"name": "@cutoff_date", "value": cutoff_date.isoformat()}
        ]
        
        return await self.query(
            query=query,
            parameters=parameters,
            partition_key=server_id,
            max_count=max_count
        )
    
    async def get_successful_newsletters(self, server_id: str, max_count: Optional[int] = None) -> List[Newsletter]:
        """Get successfully delivered newsletters."""
        return await self.get_newsletters_by_server(
            server_id=server_id,
            status=NewsletterStatus.DELIVERED,
            max_count=max_count
        )
    
    async def get_failed_newsletters(self, server_id: str, max_count: Optional[int] = None) -> List[Newsletter]:
        """Get failed newsletters."""
        return await self.get_newsletters_by_server(
            server_id=server_id,
            status=NewsletterStatus.FAILED,
            max_count=max_count
        )
    
    async def start_newsletter_generation(
        self, 
        newsletter_id: str, 
        server_id: str, 
        persona: str
    ) -> bool:
        """Mark newsletter generation as started."""
        try:
            newsletter = await self.get_newsletter_by_id(newsletter_id, server_id)
            if not newsletter:
                return False
            
            newsletter.start_generation(persona)
            await self.update(newsletter)
            
            logger.info(f"Started generation for newsletter {newsletter_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start generation for newsletter {newsletter_id}: {e}")
            return False
    
    async def complete_newsletter_generation(self, newsletter_id: str, server_id: str) -> bool:
        """Mark newsletter generation as completed."""
        try:
            newsletter = await self.get_newsletter_by_id(newsletter_id, server_id)
            if not newsletter:
                return False
            
            newsletter.complete_generation()
            await self.update(newsletter)
            
            logger.info(f"Completed generation for newsletter {newsletter_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to complete generation for newsletter {newsletter_id}: {e}")
            return False
    
    async def start_newsletter_delivery(
        self, 
        newsletter_id: str, 
        server_id: str, 
        channel_id: str
    ) -> bool:
        """Mark newsletter delivery as started."""
        try:
            newsletter = await self.get_newsletter_by_id(newsletter_id, server_id)
            if not newsletter:
                return False
            
            newsletter.start_delivery(channel_id)
            await self.update(newsletter)
            
            logger.info(f"Started delivery for newsletter {newsletter_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start delivery for newsletter {newsletter_id}: {e}")
            return False
    
    async def complete_newsletter_delivery(
        self, 
        newsletter_id: str, 
        server_id: str, 
        message_id: str
    ) -> bool:
        """Mark newsletter delivery as completed."""
        try:
            newsletter = await self.get_newsletter_by_id(newsletter_id, server_id)
            if not newsletter:
                return False
            
            newsletter.complete_delivery(message_id)
            await self.update(newsletter)
            
            logger.info(f"Completed delivery for newsletter {newsletter_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to complete delivery for newsletter {newsletter_id}: {e}")
            return False
    
    async def mark_newsletter_failed(
        self, 
        newsletter_id: str, 
        server_id: str, 
        error_message: str,
        is_generation_error: bool = True
    ) -> bool:
        """Mark newsletter as failed with error."""
        try:
            newsletter = await self.get_newsletter_by_id(newsletter_id, server_id)
            if not newsletter:
                return False
            
            newsletter.mark_failed(error_message, is_generation_error)
            await self.update(newsletter)
            
            logger.error(f"Marked newsletter {newsletter_id} as failed: {error_message}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to mark newsletter {newsletter_id} as failed: {e}")
            return False
    
    async def add_story_to_newsletter(
        self, 
        newsletter_id: str, 
        server_id: str, 
        story: StoryData,
        is_featured: bool = False
    ) -> bool:
        """Add story to newsletter."""
        try:
            newsletter = await self.get_newsletter_by_id(newsletter_id, server_id)
            if not newsletter:
                return False
            
            newsletter.add_story(story, is_featured)
            await self.update(newsletter)
            
            logger.info(f"Added story to newsletter {newsletter_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add story to newsletter {newsletter_id}: {e}")
            return False
    
    async def update_newsletter_engagement(
        self,
        newsletter_id: str,
        server_id: str,
        reactions: dict,
        replies_count: int
    ) -> bool:
        """Update newsletter engagement metrics."""
        try:
            newsletter = await self.get_newsletter_by_id(newsletter_id, server_id)
            if not newsletter:
                return False
            
            newsletter.update_engagement(reactions, replies_count)
            await self.update(newsletter)
            
            logger.info(f"Updated engagement for newsletter {newsletter_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update engagement for newsletter {newsletter_id}: {e}")
            return False
    
    async def get_newsletter_statistics(self, server_id: str, days: int = 30) -> dict:
        """Get newsletter statistics for a server."""
        try:
            cutoff_date = date.today() - timedelta(days=days)
            
            # Total newsletters in period
            total_newsletters = await self.count(
                partition_key=server_id,
                where_clause=f"c.newsletter_date >= '{cutoff_date.isoformat()}'"
            )
            
            # Successful deliveries
            delivered_newsletters = await self.count(
                partition_key=server_id,
                where_clause=f"c.newsletter_date >= '{cutoff_date.isoformat()}' AND c.status = 'delivered'"
            )
            
            # Failed newsletters
            failed_newsletters = await self.count(
                partition_key=server_id,
                where_clause=f"c.newsletter_date >= '{cutoff_date.isoformat()}' AND c.status = 'failed'"
            )
            
            # Get recent newsletters for engagement stats
            recent_newsletters = await self.get_recent_newsletters(server_id, days)
            
            # Calculate engagement metrics
            total_reactions = 0
            total_replies = 0
            newsletters_with_engagement = 0
            
            for newsletter in recent_newsletters:
                if newsletter.status == NewsletterStatus.DELIVERED:
                    reactions_count = sum(newsletter.reactions_received.values())
                    total_reactions += reactions_count
                    total_replies += newsletter.replies_count
                    
                    if reactions_count > 0 or newsletter.replies_count > 0:
                        newsletters_with_engagement += 1
            
            # Calculate averages
            avg_reactions = total_reactions / delivered_newsletters if delivered_newsletters > 0 else 0
            avg_replies = total_replies / delivered_newsletters if delivered_newsletters > 0 else 0
            engagement_rate = newsletters_with_engagement / delivered_newsletters * 100 if delivered_newsletters > 0 else 0
            success_rate = delivered_newsletters / total_newsletters * 100 if total_newsletters > 0 else 0
            
            return {
                "period_days": days,
                "total_newsletters": total_newsletters,
                "delivered_newsletters": delivered_newsletters,
                "failed_newsletters": failed_newsletters,
                "success_rate": round(success_rate, 2),
                "total_reactions": total_reactions,
                "total_replies": total_replies,
                "avg_reactions_per_newsletter": round(avg_reactions, 2),
                "avg_replies_per_newsletter": round(avg_replies, 2),
                "engagement_rate": round(engagement_rate, 2)
            }
            
        except Exception as e:
            logger.error(f"Failed to get newsletter statistics for server {server_id}: {e}")
            return {}
    
    async def get_newsletters_by_date_range(
        self,
        server_id: str,
        start_date: date,
        end_date: date
    ) -> List[Newsletter]:
        """Get newsletters within a date range."""
        query = """
        SELECT * FROM c 
        WHERE c.server_id = @server_id 
        AND c.newsletter_date >= @start_date 
        AND c.newsletter_date <= @end_date
        ORDER BY c.newsletter_date DESC
        """
        parameters = [
            {"name": "@server_id", "value": server_id},
            {"name": "@start_date", "value": start_date.isoformat()},
            {"name": "@end_date", "value": end_date.isoformat()}
        ]
        
        return await self.query(
            query=query,
            parameters=parameters,
            partition_key=server_id
        )
    
    async def cleanup_old_newsletters(self, server_id: str, days_old: int = 180) -> int:
        """Clean up old newsletters (keep metadata, remove content)."""
        try:
            cutoff_date = date.today() - timedelta(days=days_old)
            
            query = """
            SELECT * FROM c 
            WHERE c.server_id = @server_id 
            AND c.newsletter_date < @cutoff_date
            """
            parameters = [
                {"name": "@server_id", "value": server_id},
                {"name": "@cutoff_date", "value": cutoff_date.isoformat()}
            ]
            
            old_newsletters = await self.query(
                query=query,
                parameters=parameters,
                partition_key=server_id
            )
            
            cleaned_count = 0
            for newsletter in old_newsletters:
                # Clear content but keep metadata for statistics
                newsletter.introduction = ""
                newsletter.conclusion = ""
                newsletter.featured_story = None
                newsletter.additional_stories = []
                newsletter.brief_mentions = []
                
                await self.update(newsletter)
                cleaned_count += 1
            
            logger.info(f"Cleaned content from {cleaned_count} old newsletters for server {server_id}")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old newsletters for server {server_id}: {e}")
            return 0
    
    async def get_top_performing_newsletters(
        self, 
        server_id: str, 
        days: int = 30,
        max_count: int = 10
    ) -> List[Newsletter]:
        """Get top performing newsletters by engagement."""
        recent_newsletters = await self.get_recent_newsletters(server_id, days)
        
        # Filter delivered newsletters and sort by engagement
        delivered_newsletters = [
            n for n in recent_newsletters 
            if n.status == NewsletterStatus.DELIVERED
        ]
        
        # Sort by total engagement (reactions + replies)
        delivered_newsletters.sort(
            key=lambda n: sum(n.reactions_received.values()) + n.replies_count,
            reverse=True
        )
        
        return delivered_newsletters[:max_count]
    
    async def check_newsletter_exists_for_date(self, server_id: str, newsletter_date: date) -> bool:
        """Check if newsletter already exists for a specific date."""
        existing_newsletter = await self.get_newsletter_by_date(server_id, newsletter_date)
        return existing_newsletter is not None
    
    async def get_pending_newsletters(self, max_count: Optional[int] = None) -> List[Newsletter]:
        """Get newsletters that are pending generation across all servers."""
        query = "SELECT * FROM c WHERE c.status = @status ORDER BY c.created_at ASC"
        parameters = [{"name": "@status", "value": NewsletterStatus.PENDING.value}]
        
        return await self.query(
            query=query,
            parameters=parameters,
            max_count=max_count
        )
    
    async def get_stuck_newsletters(self, hours_stuck: int = 2) -> List[Newsletter]:
        """Get newsletters that have been generating for too long."""
        cutoff_time = datetime.now() - timedelta(hours=hours_stuck)
        
        query = """
        SELECT * FROM c 
        WHERE c.status = @status 
        AND c.generation_started_at < @cutoff_time
        """
        parameters = [
            {"name": "@status", "value": NewsletterStatus.GENERATING.value},
            {"name": "@cutoff_time", "value": cutoff_time.isoformat()}
        ]
        
        return await self.query(query=query, parameters=parameters)