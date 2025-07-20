"""
Dependency injection container for The Snitch Discord Bot.
Manages application dependencies and provides singleton instances.
"""

import asyncio
from functools import lru_cache
from typing import Optional, Dict, Any
import logging

from src.core.config import Settings, get_settings
from src.data.cosmos_client import CosmosDBClient, get_cosmos_client
from src.data.repositories.server_repository import ServerRepository
from src.data.repositories.tip_repository import TipRepository
from src.data.repositories.newsletter_repository import NewsletterRepository
from src.data.repositories.message_repository import MessageRepository

logger = logging.getLogger(__name__)


class DependencyContainer:
    """Dependency injection container for managing application dependencies."""
    
    def __init__(self):
        self._instances: Dict[str, Any] = {}
        self._settings: Optional[Settings] = None
        self._cosmos_client: Optional[CosmosDBClient] = None
        self._initialized = False
    
    async def initialize(self, settings: Optional[Settings] = None) -> None:
        """Initialize the dependency container."""
        if self._initialized:
            return
        
        try:
            # Initialize settings
            self._settings = settings or get_settings()
            logger.info("Settings initialized")
            
            # Initialize Cosmos DB client
            self._cosmos_client = await get_cosmos_client(self._settings)
            logger.info("Cosmos DB client initialized")
            
            # Initialize repositories
            await self._initialize_repositories()
            
            self._initialized = True
            logger.info("Dependency container initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize dependency container: {e}")
            raise
    
    async def _initialize_repositories(self) -> None:
        """Initialize all repository instances."""
        if not self._cosmos_client:
            raise RuntimeError("Cosmos DB client not initialized")
        
        # Server repository - uses operational_data container
        self._instances['server_repository'] = ServerRepository(
            cosmos_client=self._cosmos_client,
            container_name=self._settings.cosmos_container_operational
        )
        
        # Tip repository - uses operational_data container
        self._instances['tip_repository'] = TipRepository(
            cosmos_client=self._cosmos_client,
            container_name=self._settings.cosmos_container_operational
        )
        
        # Newsletter repository - uses content_data container
        self._instances['newsletter_repository'] = NewsletterRepository(
            cosmos_client=self._cosmos_client,
            container_name=self._settings.cosmos_container_content
        )
        
        # Message repository - uses operational_data container
        self._instances['message_repository'] = MessageRepository(
            cosmos_client=self._cosmos_client,
            container_name=self._settings.cosmos_container_operational
        )
        
        logger.info("All repositories initialized")
    
    async def close(self) -> None:
        """Close all connections and cleanup resources."""
        if self._cosmos_client:
            await self._cosmos_client.close()
            self._cosmos_client = None
        
        self._instances.clear()
        self._initialized = False
        logger.info("Dependency container closed")
    
    def get_settings(self) -> Settings:
        """Get application settings."""
        if not self._settings:
            raise RuntimeError("Settings not initialized")
        return self._settings
    
    def get_cosmos_client(self) -> CosmosDBClient:
        """Get Cosmos DB client."""
        if not self._cosmos_client:
            raise RuntimeError("Cosmos DB client not initialized")
        return self._cosmos_client
    
    def get_server_repository(self) -> ServerRepository:
        """Get server repository."""
        return self._get_instance('server_repository', ServerRepository)
    
    def get_tip_repository(self) -> TipRepository:
        """Get tip repository."""
        return self._get_instance('tip_repository', TipRepository)
    
    def get_newsletter_repository(self) -> NewsletterRepository:
        """Get newsletter repository."""
        return self._get_instance('newsletter_repository', NewsletterRepository)
    
    def get_message_repository(self) -> MessageRepository:
        """Get message repository."""
        return self._get_instance('message_repository', MessageRepository)
    
    def _get_instance(self, key: str, expected_type: type) -> Any:
        """Get instance from container with type checking."""
        if not self._initialized:
            raise RuntimeError("Dependency container not initialized")
        
        instance = self._instances.get(key)
        if instance is None:
            raise RuntimeError(f"Instance '{key}' not found in container")
        
        if not isinstance(instance, expected_type):
            raise RuntimeError(f"Instance '{key}' is not of type {expected_type}")
        
        return instance
    
    async def health_check(self) -> Dict[str, bool]:
        """Perform health checks on all dependencies."""
        health_status = {}
        
        try:
            # Check Cosmos DB
            if self._cosmos_client:
                health_status['cosmos_db'] = await self._cosmos_client.health_check()
            else:
                health_status['cosmos_db'] = False
            
            # Check repositories (they depend on Cosmos DB)
            health_status['repositories'] = health_status['cosmos_db'] and self._initialized
            
            # Overall health
            health_status['overall'] = all(health_status.values())
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            health_status['overall'] = False
        
        return health_status


# Global dependency container instance
_container: Optional[DependencyContainer] = None


async def get_container() -> DependencyContainer:
    """Get or create the global dependency container."""
    global _container
    
    if _container is None:
        _container = DependencyContainer()
        await _container.initialize()
    
    return _container


async def close_container() -> None:
    """Close the global dependency container."""
    global _container
    
    if _container is not None:
        await _container.close()
        _container = None


# Convenience functions for getting dependencies
async def get_settings_dependency() -> Settings:
    """Get settings dependency."""
    container = await get_container()
    return container.get_settings()


async def get_cosmos_client_dependency() -> CosmosDBClient:
    """Get Cosmos DB client dependency."""
    container = await get_container()
    return container.get_cosmos_client()


async def get_server_repository_dependency() -> ServerRepository:
    """Get server repository dependency."""
    container = await get_container()
    return container.get_server_repository()


async def get_tip_repository_dependency() -> TipRepository:
    """Get tip repository dependency."""
    container = await get_container()
    return container.get_tip_repository()


async def get_newsletter_repository_dependency() -> NewsletterRepository:
    """Get newsletter repository dependency."""
    container = await get_container()
    return container.get_newsletter_repository()


async def get_message_repository_dependency() -> MessageRepository:
    """Get message repository dependency."""
    container = await get_container()
    return container.get_message_repository()


# Context manager for dependency container
class DependencyContext:
    """Context manager for dependency container lifecycle."""
    
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings
        self.container: Optional[DependencyContainer] = None
    
    async def __aenter__(self) -> DependencyContainer:
        """Enter the context and initialize dependencies."""
        self.container = DependencyContainer()
        await self.container.initialize(self.settings)
        return self.container
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the context and cleanup dependencies."""
        if self.container:
            await self.container.close()


# Decorator for functions that need dependencies
def with_dependencies(func):
    """Decorator to inject dependencies into async functions."""
    async def wrapper(*args, **kwargs):
        container = await get_container()
        kwargs['container'] = container
        return await func(*args, **kwargs)
    
    return wrapper


# Service locator pattern implementation
class ServiceLocator:
    """Service locator for accessing dependencies."""
    
    def __init__(self, container: DependencyContainer):
        self._container = container
    
    @property
    def settings(self) -> Settings:
        """Get application settings."""
        return self._container.get_settings()
    
    @property
    def cosmos_client(self) -> CosmosDBClient:
        """Get Cosmos DB client."""
        return self._container.get_cosmos_client()
    
    @property
    def server_repository(self) -> ServerRepository:
        """Get server repository."""
        return self._container.get_server_repository()
    
    @property
    def tip_repository(self) -> TipRepository:
        """Get tip repository."""
        return self._container.get_tip_repository()
    
    @property
    def newsletter_repository(self) -> NewsletterRepository:
        """Get newsletter repository."""
        return self._container.get_newsletter_repository()
    
    @property
    def message_repository(self) -> MessageRepository:
        """Get message repository."""
        return self._container.get_message_repository()


async def get_service_locator() -> ServiceLocator:
    """Get service locator with initialized dependencies."""
    container = await get_container()
    return ServiceLocator(container)


# Factory functions for testing
async def create_test_container(settings: Settings) -> DependencyContainer:
    """Create a dependency container for testing."""
    container = DependencyContainer()
    await container.initialize(settings)
    return container


async def create_mock_container() -> DependencyContainer:
    """Create a mock dependency container for testing."""
    from unittest.mock import Mock, AsyncMock
    
    container = DependencyContainer()
    
    # Mock settings
    mock_settings = Mock(spec=Settings)
    mock_settings.cosmos_container_operational = "test_operational"
    mock_settings.cosmos_container_content = "test_content"
    container._settings = mock_settings
    
    # Mock Cosmos client
    mock_cosmos_client = AsyncMock(spec=CosmosDBClient)
    mock_cosmos_client.health_check.return_value = True
    container._cosmos_client = mock_cosmos_client
    
    # Mock repositories
    container._instances = {
        'server_repository': Mock(spec=ServerRepository),
        'tip_repository': Mock(spec=TipRepository),
        'newsletter_repository': Mock(spec=NewsletterRepository),
        'message_repository': Mock(spec=MessageRepository)
    }
    
    container._initialized = True
    return container


# Utility function for dependency validation
def validate_dependencies(container: DependencyContainer) -> Dict[str, bool]:
    """Validate that all required dependencies are available."""
    validation_results = {}
    
    try:
        # Validate settings
        settings = container.get_settings()
        validation_results['settings'] = settings is not None
        
        # Validate Cosmos client
        cosmos_client = container.get_cosmos_client()
        validation_results['cosmos_client'] = cosmos_client is not None
        
        # Validate repositories
        server_repo = container.get_server_repository()
        validation_results['server_repository'] = server_repo is not None
        
        tip_repo = container.get_tip_repository()
        validation_results['tip_repository'] = tip_repo is not None
        
        newsletter_repo = container.get_newsletter_repository()
        validation_results['newsletter_repository'] = newsletter_repo is not None
        
        message_repo = container.get_message_repository()
        validation_results['message_repository'] = message_repo is not None
        
        # Overall validation
        validation_results['all_valid'] = all(validation_results.values())
        
    except Exception as e:
        logger.error(f"Dependency validation failed: {e}")
        validation_results['error'] = str(e)
        validation_results['all_valid'] = False
    
    return validation_results


# Configuration for dependency injection in Azure Functions
class AzureFunctionDependencies:
    """Dependency management specifically for Azure Functions."""
    
    _container: Optional[DependencyContainer] = None
    _lock = asyncio.Lock()
    
    @classmethod
    async def get_container(cls) -> DependencyContainer:
        """Get container with proper concurrency handling for Azure Functions."""
        if cls._container is None:
            async with cls._lock:
                if cls._container is None:
                    cls._container = DependencyContainer()
                    await cls._container.initialize()
        
        return cls._container
    
    @classmethod
    async def cleanup(cls) -> None:
        """Cleanup container (typically called during function app shutdown)."""
        if cls._container is not None:
            async with cls._lock:
                if cls._container is not None:
                    await cls._container.close()
                    cls._container = None