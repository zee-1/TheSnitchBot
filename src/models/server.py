"""
Server configuration model for The Snitch Discord Bot.
Handles Discord server settings and preferences.
"""

from datetime import datetime, time
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import Field, field_validator, ConfigDict
from .base import CosmosDBEntity


class PersonaType(str, Enum):
    """Available bot personas."""
    SASSY_REPORTER = "sassy_reporter"
    INVESTIGATIVE_JOURNALIST = "investigative_journalist"
    GOSSIP_COLUMNIST = "gossip_columnist"
    SPORTS_COMMENTATOR = "sports_commentator"
    WEATHER_ANCHOR = "weather_anchor"
    CONSPIRACY_THEORIST = "conspiracy_theorist"


class ServerStatus(str, Enum):
    """Server activation status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class ServerConfig(CosmosDBEntity):
    """Discord server configuration and settings."""
    
    # Discord server information
    server_id: str = Field(..., description="Discord server/guild ID")
    server_name: str = Field(..., description="Discord server name")
    owner_id: str = Field(..., description="Discord server owner ID")
    
    # Bot configuration
    status: ServerStatus = Field(ServerStatus.ACTIVE, description="Server activation status")
    persona: PersonaType = Field(PersonaType.SASSY_REPORTER, description="Bot personality")
    
    # Newsletter settings
    newsletter_enabled: bool = Field(True, description="Whether newsletter is enabled")
    newsletter_channel_id: Optional[str] = Field(None, description="Channel for newsletter delivery")
    newsletter_time: str = Field("09:00", description="Time to send newsletter (HH:MM format)")
    newsletter_timezone: str = Field("UTC", description="Timezone for newsletter scheduling")
    last_newsletter_sent: Optional[str] = Field(None, description="Last newsletter timestamp (ISO format)")
    
    # Channel settings
    source_channel_id: Optional[str] = Field(None, description="Channel bot reads from for context and content analysis")
    output_channel_id: Optional[str] = Field(None, description="Channel for command outputs (breaking news, leaks, etc)")
    bot_updates_channel_id: Optional[str] = Field(None, description="Channel for bot status updates and notifications")
    
    # Content settings
    max_messages_analysis: int = Field(1000, description="Max messages to analyze for newsletter")
    controversy_threshold: float = Field(0.5, description="Threshold for controversy scoring")
    
    # Admin settings
    admin_users: List[str] = Field(default_factory=list, description="List of admin user IDs")
    moderator_users: List[str] = Field(default_factory=list, description="List of moderator user IDs")
    
    # Feature flags
    breaking_news_enabled: bool = Field(True, description="Enable breaking news command")
    fact_check_enabled: bool = Field(True, description="Enable fact check command")
    leak_command_enabled: bool = Field(True, description="Enable leak command")
    tip_submission_enabled: bool = Field(True, description="Enable tip submission")
    
    # Chain of Thoughts settings for leak command
    leak_cot_enabled: bool = Field(True, description="Enable Chain of Thoughts for leak command")
    leak_cot_timeout_seconds: int = Field(30, description="CoT processing timeout in seconds")
    leak_max_context_messages: int = Field(50, description="Max messages for CoT context analysis")
    leak_min_user_activity: int = Field(2, description="Minimum user activity threshold for targeting")
    leak_exclude_recent_targets_hours: int = Field(2, description="Hours to exclude recently targeted users")
    
    # Rate limiting
    commands_per_minute: int = Field(10, description="Commands per minute per user")
    newsletter_cooldown_hours: int = Field(24, description="Hours between newsletters")
    
    # Custom settings
    custom_prompts: Dict[str, str] = Field(default_factory=dict, description="Custom prompt overrides")
    blacklisted_words: List[str] = Field(default_factory=list, description="Words to filter from content")
    whitelisted_channels: List[str] = Field(default_factory=list, description="Channels to monitor")
    
    def __init__(self, **data):
        """Initialize ServerConfig with proper entity_type and partition_key."""
        if 'entity_type' not in data:
            data['entity_type'] = 'server'
        if 'partition_key' not in data and 'server_id' in data:
            data['partition_key'] = data['server_id']
        super().__init__(**data)
    
    @field_validator("server_id")
    @classmethod
    def validate_server_id(cls, v):
        """Validate Discord server ID format."""
        if not v.isdigit():
            raise ValueError("Server ID must be a valid Discord snowflake")
        return v
    
    @field_validator("owner_id")
    @classmethod
    def validate_owner_id(cls, v):
        """Validate Discord user ID format."""
        if not v.isdigit():
            raise ValueError("Owner ID must be a valid Discord snowflake")
        return v
    
    @field_validator("newsletter_channel_id", "source_channel_id", "output_channel_id", "bot_updates_channel_id")
    @classmethod
    def validate_channel_ids(cls, v):
        """Validate Discord channel ID format."""
        if v is not None and not v.isdigit():
            raise ValueError("Channel ID must be a valid Discord snowflake")
        return v
    
    @field_validator("admin_users", "moderator_users", "whitelisted_channels")
    @classmethod
    def validate_discord_ids(cls, v):
        """Validate list of Discord IDs."""
        for item in v:
            if not item.isdigit():
                raise ValueError("All Discord IDs must be valid snowflakes")
        return v
    
    @field_validator("controversy_threshold")
    @classmethod
    def validate_controversy_threshold(cls, v):
        """Validate controversy threshold is between 0 and 1."""
        if not 0 <= v <= 1:
            raise ValueError("Controversy threshold must be between 0 and 1")
        return v
    
    @property
    def partition_key(self) -> str:
        """Cosmos DB partition key is the server_id."""
        return self.server_id
    
    def is_admin(self, user_id: str) -> bool:
        """Check if user is an admin."""
        return user_id in self.admin_users or user_id == self.owner_id
    
    def is_moderator(self, user_id: str) -> bool:
        """Check if user is a moderator or admin."""
        return user_id in self.moderator_users or self.is_admin(user_id)
    
    def can_use_command(self, command: str) -> bool:
        """Check if a command is enabled for this server."""
        command_map = {
            "breaking_news": self.breaking_news_enabled,
            "fact_check": self.fact_check_enabled,
            "leak": self.leak_command_enabled,
            "submit_tip": self.tip_submission_enabled,
        }
        return command_map.get(command, True)
    
    def is_channel_whitelisted(self, channel_id: str) -> bool:
        """Check if channel is whitelisted (empty list means all channels)."""
        if not self.whitelisted_channels:
            return True
        return channel_id in self.whitelisted_channels
    
    def get_source_channel(self) -> Optional[str]:
        """Get the configured source channel for reading context."""
        return self.source_channel_id
    
    def get_output_channel(self) -> Optional[str]:
        """Get the configured output channel for command responses."""
        return self.output_channel_id
    
    def get_bot_updates_channel(self) -> Optional[str]:
        """Get the configured bot updates channel."""
        return self.bot_updates_channel_id
    
    def set_source_channel(self, channel_id: Optional[str]) -> None:
        """Set the source channel for reading context."""
        self.source_channel_id = channel_id
        self.update_timestamp()
    
    def set_output_channel(self, channel_id: Optional[str]) -> None:
        """Set the output channel for command responses."""
        self.output_channel_id = channel_id
        self.update_timestamp()
    
    def set_bot_updates_channel(self, channel_id: Optional[str]) -> None:
        """Set the bot updates channel."""
        self.bot_updates_channel_id = channel_id
        self.update_timestamp()
    
    def add_admin(self, user_id: str) -> None:
        """Add user to admin list."""
        if user_id not in self.admin_users:
            self.admin_users.append(user_id)
            self.update_timestamp()
    
    def remove_admin(self, user_id: str) -> None:
        """Remove user from admin list."""
        if user_id in self.admin_users:
            self.admin_users.remove(user_id)
            self.update_timestamp()
    
    def add_moderator(self, user_id: str) -> None:
        """Add user to moderator list."""
        if user_id not in self.moderator_users:
            self.moderator_users.append(user_id)
            self.update_timestamp()
    
    def remove_moderator(self, user_id: str) -> None:
        """Remove user from moderator list."""
        if user_id in self.moderator_users:
            self.moderator_users.remove(user_id)
            self.update_timestamp()
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_encoders={
            time: lambda v: v.strftime("%H:%M") if v else None,
            datetime: lambda v: v.isoformat() if v else None
        }
    )