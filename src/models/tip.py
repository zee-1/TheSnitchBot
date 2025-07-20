"""
Tip submission model for The Snitch Discord Bot.
Handles anonymous tip submissions and processing.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum
from pydantic import Field, field_validator, ConfigDict
from .base import CosmosDBEntity


class TipStatus(str, Enum):
    """Status of tip submissions."""
    PENDING = "pending"
    REVIEWED = "reviewed"
    INVESTIGATING = "investigating"
    PROCESSED = "processed"
    DISMISSED = "dismissed"


class TipPriority(str, Enum):
    """Priority levels for tips."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TipCategory(str, Enum):
    """Categories of tips."""
    GENERAL = "general"
    DRAMA = "drama"
    CONTROVERSY = "controversy"
    BREAKING_NEWS = "breaking_news"
    RUMOR = "rumor"
    INVESTIGATION = "investigation"


class Tip(CosmosDBEntity):
    """Anonymous tip submission from Discord users."""
    
    # Server and submission info
    server_id: str = Field(..., description="Discord server ID where tip was submitted")
    submitter_id: Optional[str] = Field(None, description="Discord user ID (if not anonymous)")
    submission_channel_id: Optional[str] = Field(None, description="Channel where tip was submitted")
    
    # Tip content
    content: str = Field(..., description="Tip content/message")
    category: TipCategory = Field(TipCategory.GENERAL, description="Tip category")
    priority: TipPriority = Field(TipPriority.MEDIUM, description="Tip priority level")
    
    # Processing status
    status: TipStatus = Field(TipStatus.PENDING, description="Processing status")
    assigned_to: Optional[str] = Field(None, description="User ID of assigned investigator")
    
    # Metadata
    is_anonymous: bool = Field(True, description="Whether tip was submitted anonymously")
    source_type: str = Field("discord_command", description="How tip was submitted")
    ip_hash: Optional[str] = Field(None, description="Hashed IP for abuse prevention")
    
    # Investigation tracking
    investigation_notes: str = Field("", description="Internal investigation notes")
    related_messages: list[str] = Field(default_factory=list, description="Related message IDs")
    evidence_links: list[str] = Field(default_factory=list, description="Links to evidence")
    
    # AI processing
    processed_by_ai: bool = Field(False, description="Whether AI has processed this tip")
    ai_relevance_score: float = Field(0.0, description="AI-calculated relevance score")
    ai_summary: str = Field("", description="AI-generated summary")
    suggested_actions: list[str] = Field(default_factory=list, description="AI-suggested actions")
    
    # Resolution
    resolved_at: Optional[datetime] = Field(None, description="When tip was resolved")
    resolution_notes: str = Field("", description="Resolution summary")
    resulted_in_newsletter: bool = Field(False, description="Whether tip led to newsletter story")
    
    def __init__(self, **data):
        """Initialize Tip with proper entity_type and partition_key."""
        if 'entity_type' not in data:
            data['entity_type'] = 'tip'
        if 'partition_key' not in data and 'server_id' in data:
            data['partition_key'] = data['server_id']
        super().__init__(**data)
    
    @field_validator("content")
    @classmethod
    def validate_content(cls, v):
        """Validate tip content."""
        if not v.strip():
            raise ValueError("Tip content cannot be empty")
        if len(v) > 2000:
            raise ValueError("Tip content cannot exceed 2000 characters")
        return v.strip()
    
    @field_validator("ai_relevance_score")
    @classmethod
    def validate_relevance_score(cls, v):
        """Validate AI relevance score range."""
        if not 0 <= v <= 1:
            raise ValueError("AI relevance score must be between 0 and 1")
        return v
    
    @property
    def partition_key(self) -> str:
        """Cosmos DB partition key is the server_id."""
        return self.server_id
    
    @property
    def age_hours(self) -> float:
        """Get age of tip in hours."""
        if not self.created_at:
            return 0
        delta = datetime.now(self.created_at.tzinfo) - self.created_at
        return delta.total_seconds() / 3600
    
    @property
    def is_recent(self) -> bool:
        """Check if tip is recent (within 24 hours)."""
        return self.age_hours <= 24
    
    @property
    def is_stale(self) -> bool:
        """Check if tip is stale (older than 7 days)."""
        return self.age_hours > (7 * 24)
    
    def assign_to_user(self, user_id: str) -> None:
        """Assign tip to a user for investigation."""
        self.assigned_to = user_id
        self.status = TipStatus.INVESTIGATING
        self.update_timestamp()
    
    def mark_reviewed(self, notes: str = "") -> None:
        """Mark tip as reviewed."""
        self.status = TipStatus.REVIEWED
        if notes:
            timestamp_str = datetime.now().isoformat()
            self.investigation_notes += f"\n[{timestamp_str}] {notes}"
        self.update_timestamp()
    
    def mark_processed(self, resolution: str, resulted_in_newsletter: bool = False) -> None:
        """Mark tip as processed with resolution."""
        self.status = TipStatus.PROCESSED
        self.resolved_at = datetime.now().isoformat()
        self.resolution_notes = resolution
        self.resulted_in_newsletter = resulted_in_newsletter
        self.update_timestamp()
    
    def dismiss_tip(self, reason: str) -> None:
        """Dismiss tip with reason."""
        self.status = TipStatus.DISMISSED
        self.resolved_at = datetime.now().isoformat()
        self.resolution_notes = f"Dismissed: {reason}"
        self.update_timestamp()
    
    def add_investigation_note(self, note: str, user_id: str = "system") -> None:
        """Add investigation note."""
        timestamp_str = datetime.now().isoformat()
        self.investigation_notes += f"\n[{timestamp_str}] {user_id}: {note}"
        self.update_timestamp()
    
    def add_related_message(self, message_id: str) -> None:
        """Add related message ID."""
        if message_id not in self.related_messages:
            self.related_messages.append(message_id)
            self.update_timestamp()
    
    def add_evidence_link(self, link: str) -> None:
        """Add evidence link."""
        if link not in self.evidence_links:
            self.evidence_links.append(link)
            self.update_timestamp()
    
    def update_ai_analysis(
        self, 
        relevance_score: float, 
        summary: str, 
        suggested_actions: list[str]
    ) -> None:
        """Update AI analysis results."""
        self.processed_by_ai = True
        self.ai_relevance_score = relevance_score
        self.ai_summary = summary
        self.suggested_actions = suggested_actions
        
        # Auto-prioritize based on AI score
        if relevance_score >= 0.8:
            self.priority = TipPriority.HIGH
        elif relevance_score >= 0.6:
            self.priority = TipPriority.MEDIUM
        else:
            self.priority = TipPriority.LOW
        
        self.update_timestamp()
    
    def calculate_priority_score(self) -> float:
        """Calculate overall priority score for triage."""
        score = 0.0
        
        # Base priority
        priority_scores = {
            TipPriority.LOW: 0.2,
            TipPriority.MEDIUM: 0.5,
            TipPriority.HIGH: 0.8,
            TipPriority.URGENT: 1.0
        }
        score += priority_scores.get(self.priority, 0.5)
        
        # AI relevance
        score += self.ai_relevance_score * 0.3
        
        # Recency (newer tips get higher score)
        if self.is_recent:
            score += 0.2
        elif self.is_stale:
            score -= 0.2
        
        # Category weighting
        category_weights = {
            TipCategory.BREAKING_NEWS: 0.3,
            TipCategory.CONTROVERSY: 0.2,
            TipCategory.DRAMA: 0.1,
            TipCategory.INVESTIGATION: 0.2,
            TipCategory.RUMOR: 0.0,
            TipCategory.GENERAL: 0.1
        }
        score += category_weights.get(self.category, 0.0)
        
        return min(score, 1.0)
    
    def to_dict_for_ai(self) -> Dict[str, Any]:
        """Convert to dictionary suitable for AI processing."""
        return {
            "id": self.id,
            "content": self.content,
            "category": self.category.value,
            "priority": self.priority.value,
            "age_hours": self.age_hours,
            "is_anonymous": self.is_anonymous,
            "related_messages_count": len(self.related_messages),
            "evidence_links_count": len(self.evidence_links),
            "server_id": self.server_id
        }
    
    @classmethod
    def create_from_command(
        cls,
        server_id: str,
        content: str,
        submitter_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        is_anonymous: bool = True
    ) -> "Tip":
        """Create tip from Discord command submission."""
        return cls(
            server_id=server_id,
            submitter_id=submitter_id,
            submission_channel_id=channel_id,
            content=content,
            is_anonymous=is_anonymous,
            source_type="discord_command"
        )
    
    @classmethod
    def create_from_dm(
        cls,
        server_id: str,
        content: str,
        submitter_id: str
    ) -> "Tip":
        """Create tip from DM submission."""
        return cls(
            server_id=server_id,
            submitter_id=submitter_id,
            content=content,
            is_anonymous=True,  # DMs are always anonymous
            source_type="direct_message"
        )