"""
Tip repository for The Snitch Discord Bot.
Handles anonymous tip submission CRUD operations.
"""

from typing import List, Optional
from datetime import datetime, timedelta
import logging

from src.models.tip import Tip, TipStatus, TipPriority, TipCategory
from src.data.repositories.base import BaseRepository
from src.data.cosmos_client import CosmosDBClient

logger = logging.getLogger(__name__)


class TipRepository(BaseRepository[Tip]):
    """Repository for tip submissions."""
    
    def __init__(self, cosmos_client: CosmosDBClient, container_name: str):
        super().__init__(cosmos_client, container_name, Tip)
    
    async def create_tip(
        self,
        server_id: str,
        content: str,
        submitter_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        category: TipCategory = TipCategory.GENERAL,
        is_anonymous: bool = True
    ) -> Tip:
        """Create a new tip submission."""
        tip = Tip(
            server_id=server_id,
            submitter_id=submitter_id,
            submission_channel_id=channel_id,
            content=content,
            category=category,
            is_anonymous=is_anonymous,
            status=TipStatus.PENDING,
            priority=TipPriority.MEDIUM
        )
        
        return await self.create(tip)
    
    async def get_tip_by_id(self, tip_id: str, server_id: str) -> Optional[Tip]:
        """Get tip by ID within a server."""
        return await self.get_by_id(tip_id, server_id)
    
    async def get_tips_by_server(
        self, 
        server_id: str, 
        status: Optional[TipStatus] = None,
        max_count: Optional[int] = None
    ) -> List[Tip]:
        """Get tips for a specific server, optionally filtered by status."""
        if status:
            query = "SELECT * FROM c WHERE c.server_id = @server_id AND c.status = @status ORDER BY c.created_at DESC"
            parameters = [
                {"name": "@server_id", "value": server_id},
                {"name": "@status", "value": status.value}
            ]
        else:
            query = "SELECT * FROM c WHERE c.server_id = @server_id ORDER BY c.created_at DESC"
            parameters = [{"name": "@server_id", "value": server_id}]
        
        return await self.query(
            query=query,
            parameters=parameters,
            partition_key=server_id,
            max_count=max_count
        )
    
    async def get_pending_tips(self, server_id: str, max_count: Optional[int] = None) -> List[Tip]:
        """Get pending tips for a server."""
        return await self.get_tips_by_server(server_id, TipStatus.PENDING, max_count)
    
    async def get_high_priority_tips(self, server_id: str) -> List[Tip]:
        """Get high priority tips for a server."""
        query = """
        SELECT * FROM c 
        WHERE c.server_id = @server_id 
        AND c.priority IN (@high, @urgent)
        AND c.status IN (@pending, @investigating)
        ORDER BY c.priority DESC, c.created_at ASC
        """
        parameters = [
            {"name": "@server_id", "value": server_id},
            {"name": "@high", "value": TipPriority.HIGH.value},
            {"name": "@urgent", "value": TipPriority.URGENT.value},
            {"name": "@pending", "value": TipStatus.PENDING.value},
            {"name": "@investigating", "value": TipStatus.INVESTIGATING.value}
        ]
        
        return await self.query(
            query=query,
            parameters=parameters,
            partition_key=server_id
        )
    
    async def get_tips_by_category(
        self, 
        server_id: str, 
        category: TipCategory,
        max_count: Optional[int] = None
    ) -> List[Tip]:
        """Get tips by category for a server."""
        query = "SELECT * FROM c WHERE c.server_id = @server_id AND c.category = @category ORDER BY c.created_at DESC"
        parameters = [
            {"name": "@server_id", "value": server_id},
            {"name": "@category", "value": category.value}
        ]
        
        return await self.query(
            query=query,
            parameters=parameters,
            partition_key=server_id,
            max_count=max_count
        )
    
    async def get_recent_tips(
        self, 
        server_id: str, 
        hours: int = 24,
        max_count: Optional[int] = None
    ) -> List[Tip]:
        """Get tips submitted within the last N hours."""
        return await self.get_recent(
            partition_key=server_id,
            hours=hours,
            max_count=max_count
        )
    
    async def assign_tip(self, tip_id: str, server_id: str, assigned_to: str) -> bool:
        """Assign tip to a user for investigation."""
        try:
            tip = await self.get_tip_by_id(tip_id, server_id)
            if not tip:
                return False
            
            tip.assign_to_user(assigned_to)
            await self.update(tip)
            
            logger.info(f"Assigned tip {tip_id} to user {assigned_to}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to assign tip {tip_id}: {e}")
            return False
    
    async def update_tip_status(
        self, 
        tip_id: str, 
        server_id: str, 
        status: TipStatus,
        notes: str = ""
    ) -> bool:
        """Update tip status."""
        try:
            tip = await self.get_tip_by_id(tip_id, server_id)
            if not tip:
                return False
            
            tip.status = status
            if notes:
                tip.add_investigation_note(notes)
            
            await self.update(tip)
            
            logger.info(f"Updated tip {tip_id} status to {status.value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update tip {tip_id} status: {e}")
            return False
    
    async def mark_tip_processed(
        self, 
        tip_id: str, 
        server_id: str, 
        resolution: str,
        resulted_in_newsletter: bool = False
    ) -> bool:
        """Mark tip as processed with resolution."""
        try:
            tip = await self.get_tip_by_id(tip_id, server_id)
            if not tip:
                return False
            
            tip.mark_processed(resolution, resulted_in_newsletter)
            await self.update(tip)
            
            logger.info(f"Marked tip {tip_id} as processed")
            return True
            
        except Exception as e:
            logger.error(f"Failed to mark tip {tip_id} as processed: {e}")
            return False
    
    async def dismiss_tip(self, tip_id: str, server_id: str, reason: str) -> bool:
        """Dismiss tip with reason."""
        try:
            tip = await self.get_tip_by_id(tip_id, server_id)
            if not tip:
                return False
            
            tip.dismiss_tip(reason)
            await self.update(tip)
            
            logger.info(f"Dismissed tip {tip_id}: {reason}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to dismiss tip {tip_id}: {e}")
            return False
    
    async def add_investigation_note(
        self, 
        tip_id: str, 
        server_id: str, 
        note: str,
        user_id: str = "system"
    ) -> bool:
        """Add investigation note to tip."""
        try:
            tip = await self.get_tip_by_id(tip_id, server_id)
            if not tip:
                return False
            
            tip.add_investigation_note(note, user_id)
            await self.update(tip)
            
            logger.info(f"Added investigation note to tip {tip_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add investigation note to tip {tip_id}: {e}")
            return False
    
    async def update_ai_analysis(
        self,
        tip_id: str,
        server_id: str,
        relevance_score: float,
        summary: str,
        suggested_actions: List[str]
    ) -> bool:
        """Update AI analysis results for tip."""
        try:
            tip = await self.get_tip_by_id(tip_id, server_id)
            if not tip:
                return False
            
            tip.update_ai_analysis(relevance_score, summary, suggested_actions)
            await self.update(tip)
            
            logger.info(f"Updated AI analysis for tip {tip_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update AI analysis for tip {tip_id}: {e}")
            return False
    
    async def get_tips_for_ai_processing(self, server_id: str, max_count: int = 10) -> List[Tip]:
        """Get tips that need AI processing."""
        query = """
        SELECT * FROM c 
        WHERE c.server_id = @server_id 
        AND c.processed_by_ai = false
        AND c.status = @status
        ORDER BY c.created_at ASC
        """
        parameters = [
            {"name": "@server_id", "value": server_id},
            {"name": "@status", "value": TipStatus.PENDING.value}
        ]
        
        return await self.query(
            query=query,
            parameters=parameters,
            partition_key=server_id,
            max_count=max_count
        )
    
    async def get_tips_by_submitter(
        self, 
        server_id: str, 
        submitter_id: str,
        max_count: Optional[int] = None
    ) -> List[Tip]:
        """Get tips submitted by a specific user (non-anonymous only)."""
        query = """
        SELECT * FROM c 
        WHERE c.server_id = @server_id 
        AND c.submitter_id = @submitter_id
        AND c.is_anonymous = false
        ORDER BY c.created_at DESC
        """
        parameters = [
            {"name": "@server_id", "value": server_id},
            {"name": "@submitter_id", "value": submitter_id}
        ]
        
        return await self.query(
            query=query,
            parameters=parameters,
            partition_key=server_id,
            max_count=max_count
        )
    
    async def get_tip_statistics(self, server_id: str) -> dict:
        """Get tip statistics for a server."""
        try:
            # Count by status
            total_tips = await self.count(partition_key=server_id)
            pending_tips = await self.count(
                partition_key=server_id,
                where_clause="c.status = 'pending'"
            )
            processed_tips = await self.count(
                partition_key=server_id,
                where_clause="c.status = 'processed'"
            )
            dismissed_tips = await self.count(
                partition_key=server_id,
                where_clause="c.status = 'dismissed'"
            )
            
            # Count by priority
            high_priority = await self.count(
                partition_key=server_id,
                where_clause="c.priority IN ('high', 'urgent')"
            )
            
            # Count by category
            category_stats = {}
            for category in TipCategory:
                count = await self.count(
                    partition_key=server_id,
                    where_clause=f"c.category = '{category.value}'"
                )
                category_stats[category.value] = count
            
            # Count tips that resulted in newsletters
            newsletter_tips = await self.count(
                partition_key=server_id,
                where_clause="c.resulted_in_newsletter = true"
            )
            
            return {
                "total_tips": total_tips,
                "pending_tips": pending_tips,
                "processed_tips": processed_tips,
                "dismissed_tips": dismissed_tips,
                "high_priority_tips": high_priority,
                "newsletter_tips": newsletter_tips,
                "category_distribution": category_stats,
                "success_rate": (newsletter_tips / total_tips * 100) if total_tips > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Failed to get tip statistics for server {server_id}: {e}")
            return {}
    
    async def cleanup_old_tips(self, server_id: str, days_old: int = 90) -> int:
        """Clean up old dismissed or processed tips."""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_old)
            
            query = """
            SELECT * FROM c 
            WHERE c.server_id = @server_id 
            AND c.status IN (@dismissed, @processed)
            AND c.created_at < @cutoff_date
            """
            parameters = [
                {"name": "@server_id", "value": server_id},
                {"name": "@dismissed", "value": TipStatus.DISMISSED.value},
                {"name": "@processed", "value": TipStatus.PROCESSED.value},
                {"name": "@cutoff_date", "value": cutoff_date.isoformat()}
            ]
            
            old_tips = await self.query(
                query=query,
                parameters=parameters,
                partition_key=server_id
            )
            
            deleted_count = 0
            for tip in old_tips:
                success = await self.delete(tip.id, server_id)
                if success:
                    deleted_count += 1
            
            logger.info(f"Cleaned up {deleted_count} old tips for server {server_id}")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old tips for server {server_id}: {e}")
            return 0
    
    async def search_tips(
        self, 
        server_id: str, 
        search_term: str,
        max_results: int = 50
    ) -> List[Tip]:
        """Search tips by content."""
        query = """
        SELECT * FROM c 
        WHERE c.server_id = @server_id
        AND CONTAINS(UPPER(c.content), UPPER(@search_term))
        ORDER BY c.created_at DESC
        """
        parameters = [
            {"name": "@server_id", "value": server_id},
            {"name": "@search_term", "value": search_term}
        ]
        
        return await self.query(
            query=query,
            parameters=parameters,
            partition_key=server_id,
            max_count=max_results
        )
    
    async def get_stale_tips(self, server_id: str, days_stale: int = 7) -> List[Tip]:
        """Get tips that have been pending for too long."""
        cutoff_date = datetime.now() - timedelta(days=days_stale)
        
        query = """
        SELECT * FROM c 
        WHERE c.server_id = @server_id 
        AND c.status IN (@pending, @investigating)
        AND c.created_at < @cutoff_date
        ORDER BY c.created_at ASC
        """
        parameters = [
            {"name": "@server_id", "value": server_id},
            {"name": "@pending", "value": TipStatus.PENDING.value},
            {"name": "@investigating", "value": TipStatus.INVESTIGATING.value},
            {"name": "@cutoff_date", "value": cutoff_date.isoformat()}
        ]
        
        return await self.query(
            query=query,
            parameters=parameters,
            partition_key=server_id
        )