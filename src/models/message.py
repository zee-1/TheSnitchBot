"""
Message model for The Snitch Discord Bot.
Handles Discord message data and metadata.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import Field, field_validator, ConfigDict
from .base import CosmosDBEntity, VectorEntity


class MessageType(str, Enum):
    """Discord message types."""
    DEFAULT = "default"
    REPLY = "reply"
    THREAD_STARTER = "thread_starter"
    THREAD_MESSAGE = "thread_message"
    SYSTEM = "system"


class ReactionData(CosmosDBEntity):
    """Represents a reaction on a Discord message."""
    
    # Discord message fields
    message_id: str = Field(..., description="Discord message ID")
    channel_id: str = Field(..., description="Discord channel ID")
    server_id: str = Field(..., description="Discord server/guild ID")
    author_id: str = Field(..., description="Discord user ID")
    content: str = Field(..., description="Reaction content")
    timestamp: str = Field(..., description="Reaction timestamp (ISO format)")
    
    # Reaction specific fields
    emoji: str = Field(..., description="Emoji used for reaction")
    count: int = Field(..., description="Number of reactions")
    users: List[str] = Field(default_factory=list, description="List of user IDs who reacted")
    
    def __init__(self, **data):
        """Initialize ReactionData with proper entity_type and partition_key."""
        if 'entity_type' not in data:
            data['entity_type'] = 'reaction'
        if 'partition_key' not in data and 'server_id' in data:
            data['partition_key'] = data['server_id']
        super().__init__(**data)
    
    @field_validator("count")
    @classmethod
    def validate_count(cls, v):
        """Ensure count is non-negative."""
        if v < 0:
            raise ValueError("Reaction count must be non-negative")
        return v


class Message(CosmosDBEntity):
    """Discord message with additional metadata for processing."""
    
    # Discord message fields
    message_id: str = Field(..., description="Discord message ID")
    channel_id: str = Field(..., description="Discord channel ID")
    server_id: str = Field(..., description="Discord server/guild ID")
    author_id: str = Field(..., description="Discord user ID")
    content: str = Field(..., description="Message content")
    timestamp: str = Field(..., description="Message timestamp (ISO format)")
    
    # Message type and threading
    message_type: MessageType = Field(MessageType.DEFAULT, description="Type of Discord message")
    thread_id: Optional[str] = Field(None, description="Thread ID if message is in thread")
    parent_message_id: Optional[str] = Field(None, description="Parent message ID for replies")
    
    # Content analysis
    word_count: int = Field(0, description="Number of words in message")
    character_count: int = Field(0, description="Number of characters in message")
    mentions: List[str] = Field(default_factory=list, description="List of mentioned user IDs")
    channel_mentions: List[str] = Field(default_factory=list, description="List of mentioned channel IDs")
    role_mentions: List[str] = Field(default_factory=list, description="List of mentioned role IDs")
    
    # Engagement metrics
    reactions: List[ReactionData] = Field(default_factory=list, description="Message reactions")
    reply_count: int = Field(0, description="Number of replies to this message")
    total_reactions: int = Field(0, description="Total reaction count")
    
    # AI analysis metadata
    controversy_score: float = Field(0.0, description="Calculated controversy score (0-1)")
    sentiment_score: float = Field(0.0, description="Sentiment analysis score (-1 to 1)")
    toxicity_score: float = Field(0.0, description="Toxicity detection score (0-1)")
    
    # Processing flags
    processed_for_newsletter: bool = Field(False, description="Whether processed for newsletter")
    flagged_for_review: bool = Field(False, description="Whether flagged for human review")
    excluded_from_analysis: bool = Field(False, description="Whether to exclude from analysis")
    
    # Embeddings and vector data
    embedding_id: Optional[str] = Field(None, description="ChromaDB embedding document ID")
    
    def __init__(self, **data):
        """Initialize Message with proper entity_type and partition_key."""
        if 'entity_type' not in data:
            data['entity_type'] = 'message'
        if 'partition_key' not in data and 'server_id' in data:
            data['partition_key'] = data['server_id']
        super().__init__(**data)
    
    @field_validator("content")
    @classmethod
    def validate_content(cls, v):
        """Validate message content."""
        if len(v) > 4000:  # Discord's max message length is 2000, but we allow some buffer
            raise ValueError("Message content too long")
        return v
    
    @field_validator("controversy_score", "sentiment_score", "toxicity_score")
    @classmethod
    def validate_scores(cls, v):
        """Validate score ranges."""
        if not -1 <= v <= 1:
            raise ValueError("Score must be between -1 and 1")
        return v
    
    def calculate_engagement_score(self) -> float:
        """Calculate overall engagement score based on reactions and replies."""
        if self.total_reactions == 0 and self.reply_count == 0:
            return 0.0
        
        # Weight reactions and replies
        reaction_weight = 0.6
        reply_weight = 0.4
        
        # Normalize scores (cap at reasonable maximums)
        max_reactions = 50
        max_replies = 20
        
        reaction_score = min(self.total_reactions / max_reactions, 1.0)
        reply_score = min(self.reply_count / max_replies, 1.0)
        
        return (reaction_score * reaction_weight) + (reply_score * reply_weight)
    
    def calculate_controversy_score(self) -> float:
        """Calculate controversy score based on various factors."""
        score = 0.0
        
        # Reply velocity (many replies quickly = controversial)
        if self.reply_count > 5:
            score += 0.3
        
        # Mixed reactions (both positive and negative)
        positive_reactions = sum(
            r.count for r in self.reactions 
            if r.emoji in ['👍', '❤️', '😍', '🥰', '👏', '🔥']
        )
        negative_reactions = sum(
            r.count for r in self.reactions 
            if r.emoji in ['👎', '😠', '🤬', '😤', '💀', '🙄']
        )
        
        if positive_reactions > 0 and negative_reactions > 0:
            score += 0.4
        
        # Keyword analysis (controversial terms)
        controversial_keywords = [
            'wrong', 'disagree', 'actually', 'prove', 'false', 'lie',
            'stupid', 'dumb', 'ridiculous', 'nonsense', 'bullshit'
        ]
        
        content_lower = self.content.lower()
        keyword_matches = sum(1 for keyword in controversial_keywords if keyword in content_lower)
        score += min(keyword_matches * 0.1, 0.3)
        
        return min(score, 1.0)
    
    def update_metrics(self) -> None:
        """Update calculated metrics."""
        self.word_count = len(self.content.split())
        self.character_count = len(self.content)
        self.total_reactions = sum(r.count for r in self.reactions)
        self.controversy_score = self.calculate_controversy_score()
    
    def add_reaction(self, emoji: str, user_id: str) -> None:
        """Add a reaction to the message."""
        for reaction in self.reactions:
            if reaction.emoji == emoji:
                if user_id not in reaction.users:
                    reaction.users.append(user_id)
                    reaction.count += 1
                return
        
        # Create new reaction
        new_reaction = ReactionData(
            message_id=self.message_id,
            channel_id=self.channel_id,
            server_id=self.server_id,
            author_id=user_id,
            content=emoji,
            timestamp=datetime.now().isoformat(),
            emoji=emoji,
            count=1,
            users=[user_id]
        )
        self.reactions.append(new_reaction)
        self.update_metrics()
    
    def remove_reaction(self, emoji: str, user_id: str) -> None:
        """Remove a reaction from the message."""
        for reaction in self.reactions:
            if reaction.emoji == emoji and user_id in reaction.users:
                reaction.users.remove(user_id)
                reaction.count -= 1
                if reaction.count <= 0:
                    self.reactions.remove(reaction)
                break
        self.update_metrics()
    
    def is_newsworthy(self) -> bool:
        """Determine if message is potentially newsworthy."""
        engagement_threshold = 0.3
        controversy_threshold = 0.4
        
        return (
            self.calculate_engagement_score() >= engagement_threshold or
            self.controversy_score >= controversy_threshold
        ) and not self.excluded_from_analysis
    
    def to_vector_entity(self, collection_name: str) -> VectorEntity:
        """Convert to vector entity for ChromaDB storage."""
        metadata = {
            "message_id": self.message_id,
            "channel_id": self.channel_id,
            "server_id": self.server_id,
            "author_id": self.author_id,
            "timestamp": self.timestamp.isoformat(),
            "controversy_score": self.controversy_score,
            "engagement_score": self.calculate_engagement_score(),
            "word_count": self.word_count,
            "total_reactions": self.total_reactions,
            "reply_count": self.reply_count,
            "message_type": self.message_type.value
        }
        
        return VectorEntity(
            collection_name=collection_name,
            document_id=self.message_id,
            metadata=metadata
        )
    
    @classmethod
    def from_discord_message(cls, discord_message, server_id: str) -> "Message":
        """Create Message instance from discord.py Message object."""
        # Extract mentions
        mentions = [str(user.id) for user in discord_message.mentions]
        channel_mentions = [str(channel.id) for channel in discord_message.channel_mentions]
        role_mentions = [str(role.id) for role in discord_message.role_mentions]
        
        # Convert reactions
        reactions = []
        for reaction in discord_message.reactions:
            # Note: This needs to be called in an async context
            # reaction_users = [str(user.id) async for user in reaction.users()]
            reaction_users = []  # Placeholder - should be populated in async context
            reactions.append(ReactionData(
                message_id=str(discord_message.id),
                channel_id=str(discord_message.channel.id),
                server_id=server_id,
                author_id=str(discord_message.author.id),
                content=str(reaction.emoji),
                timestamp=discord_message.created_at.isoformat(),
                emoji=str(reaction.emoji),
                count=reaction.count,
                users=reaction_users
            ))
        
        # Determine message type
        message_type = MessageType.DEFAULT
        if discord_message.reference and discord_message.reference.message_id:
            message_type = MessageType.REPLY
        elif hasattr(discord_message.channel, 'parent') and discord_message.channel.parent:
            message_type = MessageType.THREAD_MESSAGE
        
        message = cls(
            message_id=str(discord_message.id),
            channel_id=str(discord_message.channel.id),
            server_id=server_id,
            author_id=str(discord_message.author.id),
            content=discord_message.content,
            timestamp=discord_message.created_at.isoformat(),
            message_type=message_type,
            thread_id=str(discord_message.channel.id) if message_type == MessageType.THREAD_MESSAGE else None,
            parent_message_id=str(discord_message.reference.message_id) if discord_message.reference else None,
            mentions=mentions,
            channel_mentions=channel_mentions,
            role_mentions=role_mentions,
            reactions=reactions
        )
        
        message.update_metrics()
        return message