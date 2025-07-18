"""
Newsletter model for The Snitch Discord Bot.
Handles newsletter generation and delivery tracking.
"""

from datetime import datetime, date
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import Field, validator
from .base import CosmosDBEntity


class NewsletterStatus(str, Enum):
    """Newsletter generation and delivery status."""
    PENDING = "pending"
    GENERATING = "generating"
    GENERATED = "generated"
    DELIVERING = "delivering"
    DELIVERED = "delivered"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NewsletterType(str, Enum):
    """Types of newsletters."""
    DAILY = "daily"
    WEEKLY = "weekly"
    BREAKING = "breaking"
    SPECIAL = "special"


class StoryData(CosmosDBEntity):
    """Individual story within a newsletter."""
    
    # Story identification
    story_id: str = Field(..., description="Unique story identifier")
    headline: str = Field(..., description="Story headline")
    summary: str = Field(..., description="Brief story summary")
    full_content: str = Field(..., description="Full story content")
    
    # Source information
    source_messages: List[str] = Field(default_factory=list, description="Source message IDs")
    primary_channel_id: str = Field(..., description="Primary channel where story occurred")
    involved_users: List[str] = Field(default_factory=list, description="Users involved in story")
    
    # Story metrics
    controversy_score: float = Field(0.0, description="Story controversy score")
    engagement_score: float = Field(0.0, description="Story engagement score")
    relevance_score: float = Field(0.0, description="AI-calculated relevance score")
    
    # AI generation metadata
    generated_by_chain: str = Field("", description="Which AI chain generated this story")
    generation_prompt: str = Field("", description="Prompt used for generation")
    generation_timestamp: datetime = Field(default_factory=datetime.now, description="When story was generated")
    
    @property
    def partition_key(self) -> str:
        """Use story_id as partition key."""
        return self.story_id
    
    @validator("controversy_score", "engagement_score", "relevance_score")
    def validate_scores(cls, v):
        """Validate score ranges."""
        if not 0 <= v <= 1:
            raise ValueError("Scores must be between 0 and 1")
        return v


class Newsletter(CosmosDBEntity):
    """Newsletter document with stories and delivery information."""
    
    # Newsletter identification
    server_id: str = Field(..., description="Discord server ID")
    newsletter_date: date = Field(..., description="Date of newsletter")
    newsletter_type: NewsletterType = Field(NewsletterType.DAILY, description="Type of newsletter")
    
    # Content
    title: str = Field(..., description="Newsletter title")
    subtitle: Optional[str] = Field(None, description="Newsletter subtitle")
    introduction: str = Field("", description="Newsletter introduction")
    conclusion: str = Field("", description="Newsletter conclusion")
    
    # Stories
    featured_story: Optional[StoryData] = Field(None, description="Main featured story")
    additional_stories: List[StoryData] = Field(default_factory=list, description="Additional stories")
    brief_mentions: List[str] = Field(default_factory=list, description="Brief story mentions")
    
    # Generation metadata
    status: NewsletterStatus = Field(NewsletterStatus.PENDING, description="Newsletter status")
    persona_used: str = Field("", description="Bot persona used for generation")
    generation_started_at: Optional[datetime] = Field(None, description="Generation start time")
    generation_completed_at: Optional[datetime] = Field(None, description="Generation completion time")
    
    # Source data
    analyzed_messages_count: int = Field(0, description="Number of messages analyzed")
    time_period_start: datetime = Field(..., description="Start of analysis period")
    time_period_end: datetime = Field(..., description="End of analysis period")
    analyzed_channels: List[str] = Field(default_factory=list, description="Channels included in analysis")
    
    # Delivery information
    delivery_channel_id: Optional[str] = Field(None, description="Channel where newsletter was delivered")
    delivery_message_id: Optional[str] = Field(None, description="Discord message ID of delivered newsletter")
    delivered_at: Optional[datetime] = Field(None, description="Delivery timestamp")
    
    # Engagement tracking
    reactions_received: Dict[str, int] = Field(default_factory=dict, description="Reactions on newsletter message")
    replies_count: int = Field(0, description="Number of replies to newsletter")
    views_count: int = Field(0, description="Estimated views (if available)")
    
    # Error handling
    generation_errors: List[str] = Field(default_factory=list, description="Errors during generation")
    delivery_errors: List[str] = Field(default_factory=list, description="Errors during delivery")
    retry_count: int = Field(0, description="Number of retry attempts")
    
    @validator("newsletter_date")
    def validate_newsletter_date(cls, v):
        """Validate newsletter date is not in the future."""
        if v > date.today():
            raise ValueError("Newsletter date cannot be in the future")
        return v
    
    @property
    def partition_key(self) -> str:
        """Cosmos DB partition key is the server_id."""
        return self.server_id
    
    @property
    def generation_duration_seconds(self) -> Optional[float]:
        """Calculate generation duration in seconds."""
        if self.generation_started_at and self.generation_completed_at:
            delta = self.generation_completed_at - self.generation_started_at
            return delta.total_seconds()
        return None
    
    @property
    def total_stories_count(self) -> int:
        """Get total number of stories."""
        count = len(self.additional_stories) + len(self.brief_mentions)
        if self.featured_story:
            count += 1
        return count
    
    @property
    def is_successful(self) -> bool:
        """Check if newsletter was successfully generated and delivered."""
        return self.status == NewsletterStatus.DELIVERED and not self.generation_errors
    
    def start_generation(self, persona: str) -> None:
        """Mark newsletter generation as started."""
        self.status = NewsletterStatus.GENERATING
        self.persona_used = persona
        self.generation_started_at = datetime.now()
        self.update_timestamp()
    
    def complete_generation(self) -> None:
        """Mark newsletter generation as completed."""
        self.status = NewsletterStatus.GENERATED
        self.generation_completed_at = datetime.now()
        self.update_timestamp()
    
    def start_delivery(self, channel_id: str) -> None:
        """Mark newsletter delivery as started."""
        self.status = NewsletterStatus.DELIVERING
        self.delivery_channel_id = channel_id
        self.update_timestamp()
    
    def complete_delivery(self, message_id: str) -> None:
        """Mark newsletter delivery as completed."""
        self.status = NewsletterStatus.DELIVERED
        self.delivery_message_id = message_id
        self.delivered_at = datetime.now()
        self.update_timestamp()
    
    def mark_failed(self, error_message: str, is_generation_error: bool = True) -> None:
        """Mark newsletter as failed with error."""
        self.status = NewsletterStatus.FAILED
        if is_generation_error:
            self.generation_errors.append(f"[{datetime.now()}] {error_message}")
        else:
            self.delivery_errors.append(f"[{datetime.now()}] {error_message}")
        self.update_timestamp()
    
    def add_story(self, story: StoryData, is_featured: bool = False) -> None:
        """Add story to newsletter."""
        if is_featured:
            self.featured_story = story
        else:
            self.additional_stories.append(story)
        self.update_timestamp()
    
    def add_brief_mention(self, mention: str) -> None:
        """Add brief story mention."""
        if mention not in self.brief_mentions:
            self.brief_mentions.append(mention)
            self.update_timestamp()
    
    def update_engagement(self, reactions: Dict[str, int], replies_count: int) -> None:
        """Update engagement metrics."""
        self.reactions_received = reactions
        self.replies_count = replies_count
        self.update_timestamp()
    
    def calculate_success_score(self) -> float:
        """Calculate overall success score based on generation and engagement."""
        score = 0.0
        
        # Generation success
        if self.status == NewsletterStatus.DELIVERED:
            score += 0.4
        elif self.status == NewsletterStatus.GENERATED:
            score += 0.2
        
        # Content quality (number of stories found)
        if self.featured_story:
            score += 0.2
        if self.additional_stories:
            score += min(len(self.additional_stories) * 0.05, 0.2)
        
        # Engagement
        total_reactions = sum(self.reactions_received.values())
        if total_reactions > 0:
            score += min(total_reactions * 0.02, 0.2)
        if self.replies_count > 0:
            score += min(self.replies_count * 0.05, 0.1)
        
        # Penalty for errors
        if self.generation_errors:
            score -= 0.1
        if self.delivery_errors:
            score -= 0.1
        
        return max(min(score, 1.0), 0.0)
    
    def to_markdown(self) -> str:
        """Convert newsletter to markdown format for Discord."""
        lines = []
        
        # Title and subtitle
        lines.append(f"# {self.title}")
        if self.subtitle:
            lines.append(f"*{self.subtitle}*")
        lines.append("")
        
        # Date and intro
        lines.append(f"📅 {self.newsletter_date.strftime('%B %d, %Y')}")
        if self.introduction:
            lines.append(f"\n{self.introduction}")
        lines.append("")
        
        # Featured story
        if self.featured_story:
            lines.append("## 🔥 Top Story")
            lines.append(f"### {self.featured_story.headline}")
            lines.append(self.featured_story.full_content)
            lines.append("")
        
        # Additional stories
        if self.additional_stories:
            lines.append("## 📰 Other News")
            for story in self.additional_stories:
                lines.append(f"### {story.headline}")
                lines.append(story.summary)
                lines.append("")
        
        # Brief mentions
        if self.brief_mentions:
            lines.append("## 📝 Quick Mentions")
            for mention in self.brief_mentions:
                lines.append(f"• {mention}")
            lines.append("")
        
        # Conclusion
        if self.conclusion:
            lines.append(self.conclusion)
        
        # Footer
        lines.append("")
        lines.append("---")
        lines.append("*Generated by The Snitch 🤖*")
        
        return "\n".join(lines)
    
    @classmethod
    def create_daily_newsletter(
        cls,
        server_id: str,
        newsletter_date: date,
        time_period_start: datetime,
        time_period_end: datetime
    ) -> "Newsletter":
        """Create a new daily newsletter."""
        return cls(
            server_id=server_id,
            newsletter_date=newsletter_date,
            newsletter_type=NewsletterType.DAILY,
            title=f"Daily Dispatch - {newsletter_date.strftime('%B %d, %Y')}",
            time_period_start=time_period_start,
            time_period_end=time_period_end
        )