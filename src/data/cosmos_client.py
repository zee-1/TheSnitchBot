"""
Azure Cosmos DB client for The Snitch Discord Bot.
Handles database connections and operations.
"""

import asyncio
from typing import Any, Dict, List, Optional, Union
from azure.cosmos.aio import CosmosClient
from azure.cosmos import PartitionKey, exceptions
import logging
from src.core.config import Settings

logger = logging.getLogger(__name__)


class CosmosDBClient:
    """Azure Cosmos DB client wrapper."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client: Optional[CosmosClient] = None
        self.database = None
        self.containers: Dict[str, Any] = {}
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize the Cosmos DB client and database."""
        if self._initialized:
            return
        
        try:
            # Create client from connection string
            self.client = CosmosClient.from_connection_string(
                self.settings.cosmos_connection_string
            )
            
            # Get or create database
            self.database = await self.client.create_database_if_not_exists(
                id=self.settings.cosmos_database_name
            )
            
            # Initialize containers
            await self._initialize_containers()
            
            self._initialized = True
            logger.info("Cosmos DB client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Cosmos DB client: {e}")
            raise
    
    async def _initialize_containers(self) -> None:
        """Initialize required containers for 2-container approach."""
        container_configs = [
            {
                "id": self.settings.cosmos_container_operational,
                "partition_key": PartitionKey(path="/partition_key"),
                "default_ttl": None
            },
            {
                "id": self.settings.cosmos_container_content,
                "partition_key": PartitionKey(path="/partition_key"),
                "default_ttl": None
            }
        ]
        
        for config in container_configs:
            try:
                container = await self.database.create_container_if_not_exists(
                    id=config["id"],
                    partition_key=config["partition_key"],
                    offer_throughput=500  # 500 RU/s each for 2-container setup
                )
                self.containers[config["id"]] = container
                logger.info(f"Container '{config['id']}' initialized")
                
            except Exception as e:
                logger.error(f"Failed to initialize container '{config['id']}': {e}")
                raise
    
    async def close(self) -> None:
        """Close the Cosmos DB client."""
        if self.client:
            await self.client.close()
            self._initialized = False
            logger.info("Cosmos DB client closed")
    
    def get_container_for_entity_type(self, entity_type: str) -> str:
        """Get the appropriate container name for an entity type."""
        if entity_type == 'newsletter':
            return self.settings.cosmos_container_content
        else:  # servers, tips, messages, reactions go to operational
            return self.settings.cosmos_container_operational
    
    async def create_item(
        self, 
        container_name: str, 
        item: Dict[str, Any], 
        partition_key: str
    ) -> Dict[str, Any]:
        """Create a new item in the specified container."""
        if not self._initialized:
            await self.initialize()
        
        try:
            container = self.containers[container_name]
            # Ensure partition key is in the item data
            if 'partition_key' not in item:
                item['partition_key'] = partition_key
            
            response = await container.create_item(body=item)
            logger.debug(f"Created item in {container_name}: {item.get('id')}")
            return response
            
        except exceptions.CosmosResourceExistsError:
            logger.warning(f"Item already exists in {container_name}: {item.get('id')}")
            raise
        except Exception as e:
            logger.error(f"Failed to create item in {container_name}: {e}")
            raise
    
    async def read_item(
        self, 
        container_name: str, 
        item_id: str, 
        partition_key: str
    ) -> Optional[Dict[str, Any]]:
        """Read an item by ID from the specified container."""
        if not self._initialized:
            await self.initialize()
        
        try:
            container = self.containers[container_name]
            response = await container.read_item(
                item=item_id,
                partition_key=partition_key
            )
            logger.debug(f"Read item from {container_name}: {item_id}")
            return response
            
        except exceptions.CosmosResourceNotFoundError:
            logger.debug(f"Item not found in {container_name}: {item_id}")
            return None
        except Exception as e:
            logger.error(f"Failed to read item from {container_name}: {e}")
            raise
    
    async def update_item(
        self, 
        container_name: str, 
        item: Dict[str, Any], 
        partition_key: str
    ) -> Dict[str, Any]:
        """Update an existing item in the specified container."""
        if not self._initialized:
            await self.initialize()
        
        try:
            container = self.containers[container_name]
            # Ensure partition key is in the item data
            if 'partition_key' not in item:
                item['partition_key'] = partition_key
                
            response = await container.upsert_item(body=item)
            logger.debug(f"Updated item in {container_name}: {item.get('id')}")
            return response
            
        except Exception as e:
            logger.error(f"Failed to update item in {container_name}: {e}")
            raise
    
    async def delete_item(
        self, 
        container_name: str, 
        item_id: str, 
        partition_key: str
    ) -> bool:
        """Delete an item from the specified container."""
        if not self._initialized:
            await self.initialize()
        
        try:
            container = self.containers[container_name]
            await container.delete_item(
                item=item_id,
                partition_key=partition_key
            )
            logger.debug(f"Deleted item from {container_name}: {item_id}")
            return True
            
        except exceptions.CosmosResourceNotFoundError:
            logger.debug(f"Item not found for deletion in {container_name}: {item_id}")
            return False
        except Exception as e:
            logger.error(f"Failed to delete item from {container_name}: {e}")
            raise
    
    async def query_items(
        self, 
        container_name: str, 
        query: str, 
        parameters: Optional[List[Dict[str, Any]]] = None,
        partition_key: Optional[str] = None,
        max_item_count: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Query items from the specified container."""
        if not self._initialized:
            await self.initialize()
        
        try:
            container = self.containers[container_name]
            
            query_spec = {
                "query": query,
                "parameters": parameters or []
            }
            
            if partition_key:
                items = container.query_items(
                    query=query_spec,
                    partition_key=partition_key,
                    max_item_count=max_item_count
                )
            else:
                # Cross-partition queries are now enabled by default when no partition_key is provided
                items = container.query_items(
                    query=query_spec,
                    max_item_count=max_item_count
                )
            
            results = []
            async for item in items:
                results.append(item)
            
            logger.debug(f"Queried {len(results)} items from {container_name}")
            return results
            
        except Exception as e:
            logger.error(f"Failed to query items from {container_name}: {e}")
            raise
    
    async def get_items_by_partition(
        self, 
        container_name: str, 
        partition_key: str,
        max_item_count: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get all items in a partition."""
        query = "SELECT * FROM c"
        return await self.query_items(
            container_name=container_name,
            query=query,
            partition_key=partition_key,
            max_item_count=max_item_count
        )
    
    async def count_items(
        self, 
        container_name: str, 
        partition_key: Optional[str] = None,
        where_clause: Optional[str] = None
    ) -> int:
        """Count items in container or partition."""
        query = "SELECT VALUE COUNT(1) FROM c"
        if where_clause:
            query += f" WHERE {where_clause}"
        
        results = await self.query_items(
            container_name=container_name,
            query=query,
            partition_key=partition_key
        )
        
        return results[0] if results else 0
    
    async def batch_create_items(
        self, 
        container_name: str, 
        items: List[Dict[str, Any]], 
        partition_key: str
    ) -> List[Dict[str, Any]]:
        """Create multiple items in batch."""
        if not self._initialized:
            await self.initialize()
        
        results = []
        for item in items:
            try:
                result = await self.create_item(
                    container_name=container_name,
                    item=item,
                    partition_key=partition_key
                )
                results.append(result)
            except exceptions.CosmosResourceExistsError:
                # Item already exists, try to update
                result = await self.update_item(
                    container_name=container_name,
                    item=item,
                    partition_key=partition_key
                )
                results.append(result)
        
        logger.info(f"Batch created/updated {len(results)} items in {container_name}")
        return results
    
    async def health_check(self) -> bool:
        """Check if Cosmos DB is accessible."""
        try:
            if not self._initialized:
                await self.initialize()
            
            # Try to read database info
            db_properties = await self.database.read()
            return bool(db_properties)
            
        except Exception as e:
            logger.error(f"Cosmos DB health check failed: {e}")
            return False


# Global instance
_cosmos_client: Optional[CosmosDBClient] = None


async def get_cosmos_client(settings: Optional[Settings] = None) -> CosmosDBClient:
    """Get or create the global Cosmos DB client."""
    global _cosmos_client
    
    if _cosmos_client is None:
        if settings is None:
            from src.core.config import get_settings
            settings = get_settings()
        
        _cosmos_client = CosmosDBClient(settings)
        await _cosmos_client.initialize()
    
    return _cosmos_client


async def close_cosmos_client() -> None:
    """Close the global Cosmos DB client."""
    global _cosmos_client
    
    if _cosmos_client is not None:
        await _cosmos_client.close()
        _cosmos_client = None