"""
Server repository for The Snitch Discord Bot.
Handles Discord server configuration CRUD operations.
"""

from typing import List, Optional
from datetime import datetime
import logging

from src.models.server import ServerConfig, PersonaType, ServerStatus
from src.data.repositories.base import BaseRepository
from src.data.cosmos_client import CosmosDBClient

logger = logging.getLogger(__name__)


class ServerRepository(BaseRepository[ServerConfig]):
    """Repository for Discord server configurations."""
    
    def __init__(self, cosmos_client: CosmosDBClient, container_name: str):
        super().__init__(cosmos_client, container_name, ServerConfig)
    
    async def get_by_server_id(self, server_id: str) -> Optional[ServerConfig]:
        """Get server configuration by Discord server ID."""
        return await self.get_by_id(server_id, server_id)
    
    async def get_by_server_id_partition(self, server_id: str) -> Optional[ServerConfig]:
        """Get server configuration by Discord server ID."""
        result = await self.get_by_partition(partition_key= server_id)
        return result
    

    async def create_server(
        self, 
        server_id: str, 
        server_name: str, 
        owner_id: str
    ) -> ServerConfig:
        """Create a new server configuration with defaults."""
        server_config = ServerConfig(
            server_id=server_id,
            server_name=server_name,
            owner_id=owner_id,
            status=ServerStatus.ACTIVE,
            persona=PersonaType.SASSY_REPORTER,
            newsletter_enabled=True,
            newsletter_time="09:00",  # 9 AM UTC
            admin_users=[owner_id]  # Owner is automatically an admin
        )
        
        return await self.create(server_config)
    
    async def update_server_config(self, server_config: ServerConfig) -> ServerConfig:
        """Update server configuration."""
        return await self.update(server_config)
    
    async def delete_server(self, server_id: str) -> bool:
        """Delete server configuration."""
        return await self.delete(server_id, server_id)
    
    async def get_active_servers(self) -> List[ServerConfig]:
        """Get all active servers."""
        query = "SELECT * FROM c WHERE c.status = @status"
        parameters = [{"name": "@status", "value": ServerStatus.ACTIVE.value}]
        
        return await self.query(query=query, parameters=parameters)
    
    async def get_servers_with_newsletter_enabled(self) -> List[ServerConfig]:
        """Get servers that have newsletter enabled."""
        query = "SELECT * FROM c WHERE c.newsletter_enabled = true AND c.status = @status"
        parameters = [{"name": "@status", "value": ServerStatus.ACTIVE.value}]
        
        return await self.query(query=query, parameters=parameters)
    
    async def get_servers_due_for_newsletter(self, current_time: str) -> List[ServerConfig]:
        """Get servers that are due for newsletter delivery."""
        # current_time is already a string in HH:MM format
        
        query = """
        SELECT * FROM c 
        WHERE c.newsletter_enabled = true 
        AND c.status = @status 
        AND c.newsletter_time = @time
        """
        parameters = [
            {"name": "@status", "value": ServerStatus.ACTIVE.value},
            {"name": "@time", "value": current_time}
        ]
        
        return await self.query(query=query, parameters=parameters)
    
    async def update_newsletter_channel(self, server_id: str, channel_id: str) -> bool:
        """Update newsletter delivery channel for a server."""
        try:
        
            server_config = await self.get_by_server_id_partition(server_id)
            logger.info(f"Updated newsletter channel for server {server_id}: {channel_id}")
            if not server_config:
                return False
            
            server_config.newsletter_channel_id = channel_id
            await self.update(server_config)
            
            return True
        except Exception as e:
            print("===="*8)
            print(e)
            logger.info(e)
            logger.error(f"Failed to update newsletter channel for server {server_id}: {e}")
            return False
    
    async def update_newsletter_time(self, server_id: str, newsletter_time: str) -> bool:
        """Update newsletter delivery time for a server."""
        try:
            server_config = await self.get_by_server_id_partition(server_id)
            if not server_config:
                return False
            
            server_config.newsletter_time = newsletter_time
            await self.update(server_config)
            
            logger.info(f"Updated newsletter time for server {server_id}: {newsletter_time}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update newsletter time for server {server_id}: {e}")
            return False
    
    async def update_persona(self, server_id: str, persona: PersonaType) -> bool:
        """Update bot persona for a server."""
        try:
            server_config = await self.get_by_server_id_partition(server_id)
            if not server_config:
                return False
            
            server_config.persona = persona
            await self.update(server_config)
            
            logger.info(f"Updated persona for server {server_id}: {persona.value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update persona for server {server_id}: {e}")
            return False
    
    async def add_admin(self, server_id: str, user_id: str) -> bool:
        """Add admin to server."""
        try:
            server_config = await self.get_by_server_id_partition(server_id)
            if not server_config:
                return False
            
            server_config.add_admin(user_id)
            await self.update(server_config)
            
            logger.info(f"Added admin {user_id} to server {server_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add admin {user_id} to server {server_id}: {e}")
            return False
    
    async def remove_admin(self, server_id: str, user_id: str) -> bool:
        """Remove admin from server."""
        try:
            server_config = await self.get_by_server_id_partition(server_id)
            if not server_config:
                return False
            
            server_config.remove_admin(user_id)
            await self.update(server_config)
            
            logger.info(f"Removed admin {user_id} from server {server_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove admin {user_id} from server {server_id}: {e}")
            return False
    
    async def add_moderator(self, server_id: str, user_id: str) -> bool:
        """Add moderator to server."""
        try:
            server_config = await self.get_by_server_id_partition(server_id)
            if not server_config:
                return False
            
            server_config.add_moderator(user_id)
            await self.update(server_config)
            
            logger.info(f"Added moderator {user_id} to server {server_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add moderator {user_id} to server {server_id}: {e}")
            return False
    
    async def remove_moderator(self, server_id: str, user_id: str) -> bool:
        """Remove moderator from server."""
        try:
            server_config = await self.get_by_server_id_partition(server_id)
            if not server_config:
                return False
            
            server_config.remove_moderator(user_id)
            await self.update(server_config)
            
            logger.info(f"Removed moderator {user_id} from server {server_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove moderator {user_id} from server {server_id}: {e}")
            return False
    
    async def toggle_feature(self, server_id: str, feature_name: str, enabled: bool) -> bool:
        """Toggle a feature for a server."""
        try:
            server_config = await self.get_by_server_id_partition(server_id)
            if not server_config:
                return False
            
            # Map feature names to attributes
            feature_map = {
                "newsletter": "newsletter_enabled",
                "breaking_news": "breaking_news_enabled",
                "fact_check": "fact_check_enabled",
                "leak": "leak_command_enabled",
                "tips": "tip_submission_enabled"
            }
            
            if feature_name not in feature_map:
                logger.warning(f"Unknown feature: {feature_name}")
                return False
            
            setattr(server_config, feature_map[feature_name], enabled)
            await self.update(server_config)
            
            logger.info(f"Toggled {feature_name} to {enabled} for server {server_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to toggle {feature_name} for server {server_id}: {e}")
            return False
    
    async def update_last_newsletter_sent(self, server_id: str, timestamp: datetime) -> bool:
        """Update the last newsletter sent timestamp."""
        try:
            server_config = await self.get_by_server_id(server_id)
            if not server_config:
                return False
            
            server_config.last_newsletter_sent = timestamp
            await self.update(server_config)
            
            logger.info(f"Updated last newsletter sent time for server {server_id}: {timestamp}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update last newsletter sent time for server {server_id}: {e}")
            return False
    
    async def get_servers_by_persona(self, persona: PersonaType) -> List[ServerConfig]:
        """Get servers using a specific persona."""
        query = "SELECT * FROM c WHERE c.persona = @persona AND c.status = @status"
        parameters = [
            {"name": "@persona", "value": persona.value},
            {"name": "@status", "value": ServerStatus.ACTIVE.value}
        ]
        
        return await self.query(query=query, parameters=parameters)
    
    async def get_server_stats(self) -> dict:
        """Get overall server statistics."""
        try:
            # Count by status
            active_count = await self.count(where_clause="c.status = 'active'")
            inactive_count = await self.count(where_clause="c.status = 'inactive'")
            suspended_count = await self.count(where_clause="c.status = 'suspended'")
            
            # Count by features
            newsletter_enabled = await self.count(where_clause="c.newsletter_enabled = true")
            
            # Count by persona
            persona_stats = {}
            for persona in PersonaType:
                count = await self.count(where_clause=f"c.persona = '{persona.value}'")
                persona_stats[persona.value] = count
            
            return {
                "total_servers": active_count + inactive_count + suspended_count,
                "active_servers": active_count,
                "inactive_servers": inactive_count,
                "suspended_servers": suspended_count,
                "newsletter_enabled": newsletter_enabled,
                "persona_distribution": persona_stats
            }
            
        except Exception as e:
            logger.error(f"Failed to get server stats: {e}")
            return {}
    
    async def search_servers(self, search_term: str, max_results: int = 50) -> List[ServerConfig]:
        """Search servers by name."""
        query = """
        SELECT * FROM c 
        WHERE CONTAINS(UPPER(c.server_name), UPPER(@search_term))
        AND c.status = @status
        """
        parameters = [
            {"name": "@search_term", "value": search_term},
            {"name": "@status", "value": ServerStatus.ACTIVE.value}
        ]
        
        return await self.query(
            query=query, 
            parameters=parameters, 
            max_count=max_results
        )
    
    async def cleanup_inactive_servers(self, days_inactive: int = 30) -> int:
        """Mark servers as inactive if they haven't had newsletter activity."""
        try:
            cutoff_date = datetime.now().replace(microsecond=0) - timedelta(days=days_inactive)
            
            query = """
            SELECT * FROM c 
            WHERE c.status = @status 
            AND (c.last_newsletter_sent < @cutoff_date OR NOT IS_DEFINED(c.last_newsletter_sent))
            """
            parameters = [
                {"name": "@status", "value": ServerStatus.ACTIVE.value},
                {"name": "@cutoff_date", "value": cutoff_date.isoformat()}
            ]
            
            inactive_servers = await self.query(query=query, parameters=parameters)
            
            updated_count = 0
            for server_config in inactive_servers:
                server_config.status = ServerStatus.INACTIVE
                await self.update(server_config)
                updated_count += 1
            
            logger.info(f"Marked {updated_count} servers as inactive")
            return updated_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup inactive servers: {e}")
            return 0


from datetime import timedelta