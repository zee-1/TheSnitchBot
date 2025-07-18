"""
Base repository pattern implementation for The Snitch Discord Bot.
Provides common CRUD operations for Cosmos DB entities.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TypeVar, Generic, Type
from datetime import datetime
import logging

from src.models.base import CosmosDBEntity
from src.data.cosmos_client import CosmosDBClient

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=CosmosDBEntity)


class BaseRepository(ABC, Generic[T]):
    """Base repository class for Cosmos DB operations."""
    
    def __init__(self, cosmos_client: CosmosDBClient, container_name: str, model_class: Type[T]):
        self.cosmos_client = cosmos_client
        self.container_name = container_name
        self.model_class = model_class
    
    async def create(self, entity: T) -> T:
        """Create a new entity in the database."""
        try:
            # Ensure timestamps are set
            if not entity.created_at:
                entity.created_at = datetime.now()
            
            # Convert to dict for Cosmos DB
            item_dict = entity.to_cosmos_dict()
            
            # Create in Cosmos DB
            result = await self.cosmos_client.create_item(
                container_name=self.container_name,
                item=item_dict,
                partition_key=entity.partition_key
            )
            
            # Convert back to model
            created_entity = self.model_class.from_cosmos_dict(result)
            logger.info(f"Created {self.model_class.__name__} with ID: {created_entity.id}")
            return created_entity
            
        except Exception as e:
            logger.error(f"Failed to create {self.model_class.__name__}: {e}")
            raise
    
    async def get_by_id(self, entity_id: str, partition_key: str) -> Optional[T]:
        """Get entity by ID and partition key."""
        try:
            result = await self.cosmos_client.read_item(
                container_name=self.container_name,
                item_id=entity_id,
                partition_key=partition_key
            )
            
            if result:
                entity = self.model_class.from_cosmos_dict(result)
                logger.debug(f"Retrieved {self.model_class.__name__} with ID: {entity_id}")
                return entity
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get {self.model_class.__name__} by ID {entity_id}: {e}")
            raise
    
    async def update(self, entity: T) -> T:
        """Update an existing entity."""
        try:
            # Update timestamp
            entity.update_timestamp()
            
            # Convert to dict for Cosmos DB
            item_dict = entity.to_cosmos_dict()
            
            # Update in Cosmos DB
            result = await self.cosmos_client.update_item(
                container_name=self.container_name,
                item=item_dict,
                partition_key=entity.partition_key
            )
            
            # Convert back to model
            updated_entity = self.model_class.from_cosmos_dict(result)
            logger.info(f"Updated {self.model_class.__name__} with ID: {updated_entity.id}")
            return updated_entity
            
        except Exception as e:
            logger.error(f"Failed to update {self.model_class.__name__}: {e}")
            raise
    
    async def delete(self, entity_id: str, partition_key: str) -> bool:
        """Delete an entity by ID and partition key."""
        try:
            success = await self.cosmos_client.delete_item(
                container_name=self.container_name,
                item_id=entity_id,
                partition_key=partition_key
            )
            
            if success:
                logger.info(f"Deleted {self.model_class.__name__} with ID: {entity_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to delete {self.model_class.__name__} with ID {entity_id}: {e}")
            raise
    
    async def list_by_partition(
        self, 
        partition_key: str, 
        max_count: Optional[int] = None
    ) -> List[T]:
        """List all entities in a partition."""
        try:
            results = await self.cosmos_client.get_items_by_partition(
                container_name=self.container_name,
                partition_key=partition_key,
                max_item_count=max_count
            )
            
            entities = [self.model_class.from_cosmos_dict(item) for item in results]
            logger.debug(f"Retrieved {len(entities)} {self.model_class.__name__} entities from partition {partition_key}")
            return entities
            
        except Exception as e:
            logger.error(f"Failed to list {self.model_class.__name__} by partition {partition_key}: {e}")
            raise
    
    async def query(
        self, 
        query: str, 
        parameters: Optional[List[Dict[str, Any]]] = None,
        partition_key: Optional[str] = None,
        max_count: Optional[int] = None
    ) -> List[T]:
        """Execute a custom query."""
        try:
            results = await self.cosmos_client.query_items(
                container_name=self.container_name,
                query=query,
                parameters=parameters,
                partition_key=partition_key,
                max_item_count=max_count
            )
            
            entities = [self.model_class.from_cosmos_dict(item) for item in results]
            logger.debug(f"Query returned {len(entities)} {self.model_class.__name__} entities")
            return entities
            
        except Exception as e:
            logger.error(f"Failed to execute query for {self.model_class.__name__}: {e}")
            raise
    
    async def count(self, partition_key: Optional[str] = None, where_clause: Optional[str] = None) -> int:
        """Count entities in container or partition."""
        try:
            count = await self.cosmos_client.count_items(
                container_name=self.container_name,
                partition_key=partition_key,
                where_clause=where_clause
            )
            
            logger.debug(f"Counted {count} {self.model_class.__name__} entities")
            return count
            
        except Exception as e:
            logger.error(f"Failed to count {self.model_class.__name__} entities: {e}")
            raise
    
    async def exists(self, entity_id: str, partition_key: str) -> bool:
        """Check if entity exists."""
        try:
            entity = await self.get_by_id(entity_id, partition_key)
            return entity is not None
            
        except Exception as e:
            logger.error(f"Failed to check existence of {self.model_class.__name__} with ID {entity_id}: {e}")
            return False
    
    async def batch_create(self, entities: List[T], partition_key: str) -> List[T]:
        """Create multiple entities in batch."""
        try:
            # Prepare items for batch creation
            items = []
            for entity in entities:
                if not entity.created_at:
                    entity.created_at = datetime.now()
                items.append(entity.to_cosmos_dict())
            
            # Batch create in Cosmos DB
            results = await self.cosmos_client.batch_create_items(
                container_name=self.container_name,
                items=items,
                partition_key=partition_key
            )
            
            # Convert back to models
            created_entities = [self.model_class.from_cosmos_dict(item) for item in results]
            logger.info(f"Batch created {len(created_entities)} {self.model_class.__name__} entities")
            return created_entities
            
        except Exception as e:
            logger.error(f"Failed to batch create {self.model_class.__name__} entities: {e}")
            raise
    
    async def find_by_field(
        self, 
        field_name: str, 
        field_value: Any,
        partition_key: Optional[str] = None,
        max_count: Optional[int] = None
    ) -> List[T]:
        """Find entities by a specific field value."""
        query = f"SELECT * FROM c WHERE c.{field_name} = @value"
        parameters = [{"name": "@value", "value": field_value}]
        
        return await self.query(
            query=query,
            parameters=parameters,
            partition_key=partition_key,
            max_count=max_count
        )
    
    async def find_by_date_range(
        self,
        date_field: str,
        start_date: datetime,
        end_date: datetime,
        partition_key: Optional[str] = None,
        max_count: Optional[int] = None
    ) -> List[T]:
        """Find entities within a date range."""
        query = f"SELECT * FROM c WHERE c.{date_field} >= @start_date AND c.{date_field} <= @end_date ORDER BY c.{date_field} DESC"
        parameters = [
            {"name": "@start_date", "value": start_date.isoformat()},
            {"name": "@end_date", "value": end_date.isoformat()}
        ]
        
        return await self.query(
            query=query,
            parameters=parameters,
            partition_key=partition_key,
            max_count=max_count
        )
    
    async def get_recent(
        self,
        partition_key: str,
        hours: int = 24,
        max_count: Optional[int] = None
    ) -> List[T]:
        """Get entities created within the last N hours."""
        cutoff_date = datetime.now().replace(microsecond=0) - timedelta(hours=hours)
        
        return await self.find_by_date_range(
            date_field="created_at",
            start_date=cutoff_date,
            end_date=datetime.now(),
            partition_key=partition_key,
            max_count=max_count
        )
    
    async def upsert(self, entity: T) -> T:
        """Create or update an entity (upsert operation)."""
        try:
            # Try to get existing entity
            existing = await self.get_by_id(entity.id, entity.partition_key)
            
            if existing:
                # Update existing
                entity.created_at = existing.created_at  # Preserve original creation time
                return await self.update(entity)
            else:
                # Create new
                return await self.create(entity)
                
        except Exception as e:
            logger.error(f"Failed to upsert {self.model_class.__name__}: {e}")
            raise
    
    async def soft_delete(self, entity_id: str, partition_key: str) -> bool:
        """Soft delete by setting a deleted flag (if model supports it)."""
        try:
            entity = await self.get_by_id(entity_id, partition_key)
            if not entity:
                return False
            
            # Check if model has deleted field
            if hasattr(entity, 'is_deleted'):
                entity.is_deleted = True
                entity.deleted_at = datetime.now()
                await self.update(entity)
                logger.info(f"Soft deleted {self.model_class.__name__} with ID: {entity_id}")
                return True
            else:
                # Fall back to hard delete
                return await self.delete(entity_id, partition_key)
                
        except Exception as e:
            logger.error(f"Failed to soft delete {self.model_class.__name__} with ID {entity_id}: {e}")
            raise


from datetime import timedelta