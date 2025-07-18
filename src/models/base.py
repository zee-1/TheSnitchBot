"""
Base model classes for The Snitch Discord Bot.
Provides common functionality for all data models.
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
import uuid


class BaseEntity(BaseModel):
    """Base class for all entities with common fields."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique identifier")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    
    def update_timestamp(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now(timezone.utc)
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }
        validate_assignment = True
        use_enum_values = True


class CosmosDBEntity(BaseEntity):
    """Base class for entities stored in Cosmos DB."""
    
    partition_key: str = Field(..., description="Cosmos DB partition key")
    _etag: Optional[str] = Field(None, alias="etag", description="Cosmos DB etag for optimistic concurrency")
    _ts: Optional[int] = Field(None, alias="ts", description="Cosmos DB timestamp")
    
    def to_cosmos_dict(self) -> Dict[str, Any]:
        """Convert to dictionary suitable for Cosmos DB storage."""
        data = self.dict(by_alias=True, exclude_none=True)
        # Ensure id is a string
        data["id"] = str(self.id)
        return data
    
    @classmethod
    def from_cosmos_dict(cls, data: Dict[str, Any]) -> "CosmosDBEntity":
        """Create instance from Cosmos DB dictionary."""
        # Handle timestamp conversion
        if "_ts" in data:
            data["ts"] = data.pop("_ts")
        if "_etag" in data:
            data["etag"] = data.pop("_etag")
        
        return cls(**data)


class MessageEntity(BaseModel):
    """Base class for Discord message-related entities."""
    
    message_id: str = Field(..., description="Discord message ID")
    channel_id: str = Field(..., description="Discord channel ID")
    server_id: str = Field(..., description="Discord server/guild ID")
    author_id: str = Field(..., description="Discord user ID")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(..., description="Message timestamp")
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class VectorEntity(BaseModel):
    """Base class for vector storage entities."""
    
    collection_name: str = Field(..., description="ChromaDB collection name")
    document_id: str = Field(..., description="Document identifier")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata for the document")
    
    class Config:
        """Pydantic configuration."""
        validate_assignment = True