"""
User preferences model for The Snitch Discord Bot.
Manages privacy settings and opt-out preferences for community analysis features.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum

from src.models.base import BaseModel, CosmosDBEntity


class PrivacyLevel(Enum):
    """Privacy levels for user participation."""
    FULL_PARTICIPATION = "full"  # User fully participates in all analyses
    LIMITED_PARTICIPATION = "limited"  # Excluded from detailed social analysis
    ANONYMOUS_ONLY = "anonymous"  # Only included in anonymous aggregations
    COMPLETE_OPT_OUT = "opt_out"  # Completely excluded from all analyses


class FeatureOptOut(Enum):
    """Specific features users can opt out of."""
    COMMUNITY_PULSE = "community_pulse"
    SOCIAL_ANALYSIS = "social_analysis"
    MOOD_TRACKING = "mood_tracking"
    RELATIONSHIP_ANALYSIS = "relationship_analysis"
    TRENDING_TOPICS = "trending_topics"
    NEWSLETTER_MENTIONS = "newsletter_mentions"
    GOSSIP_ANALYSIS = "gossip_analysis"


class UserPreferences(CosmosDBEntity):
    """User preferences for privacy and participation."""
    
    def __init__(
        self,
        user_id: str,
        server_id: str,
        privacy_level: PrivacyLevel = PrivacyLevel.FULL_PARTICIPATION,
        feature_opt_outs: Optional[List[FeatureOptOut]] = None,
        anonymous_in_analysis: bool = False,
        exclude_from_social_mapping: bool = False,
        **kwargs
    ):
        # Set required CosmosDBEntity fields
        kwargs['partition_key'] = server_id
        kwargs['entity_type'] = 'user_preferences'
        
        super().__init__(**kwargs)
        self.user_id = user_id
        self.server_id = server_id
        self.privacy_level = privacy_level
        self.feature_opt_outs = feature_opt_outs or []
        self.anonymous_in_analysis = anonymous_in_analysis
        self.exclude_from_social_mapping = exclude_from_social_mapping
        self.last_updated = datetime.now()
    
    
    def is_opted_out_of(self, feature: FeatureOptOut) -> bool:
        """Check if user is opted out of a specific feature."""
        if self.privacy_level == PrivacyLevel.COMPLETE_OPT_OUT:
            return True
        
        return feature in self.feature_opt_outs
    
    def can_participate_in_analysis(self) -> bool:
        """Check if user can participate in any analysis."""
        return self.privacy_level != PrivacyLevel.COMPLETE_OPT_OUT
    
    def can_be_mentioned_by_name(self) -> bool:
        """Check if user can be mentioned by name in analysis."""
        return self.privacy_level in [
            PrivacyLevel.FULL_PARTICIPATION,
            PrivacyLevel.LIMITED_PARTICIPATION
        ] and not self.anonymous_in_analysis
    
    def can_participate_in_social_analysis(self) -> bool:
        """Check if user can participate in social relationship analysis."""
        return (
            not self.is_opted_out_of(FeatureOptOut.SOCIAL_ANALYSIS) and
            not self.exclude_from_social_mapping and
            self.privacy_level != PrivacyLevel.COMPLETE_OPT_OUT
        )
    
    def can_participate_in_community_pulse(self) -> bool:
        """Check if user can participate in community pulse analysis."""
        return (
            not self.is_opted_out_of(FeatureOptOut.COMMUNITY_PULSE) and
            self.can_participate_in_analysis()
        )
    
    def opt_out_of_feature(self, feature: FeatureOptOut) -> None:
        """Opt out of a specific feature."""
        if feature not in self.feature_opt_outs:
            self.feature_opt_outs.append(feature)
            self.last_updated = datetime.now()
    
    def opt_in_to_feature(self, feature: FeatureOptOut) -> None:
        """Opt back into a specific feature."""
        if feature in self.feature_opt_outs:
            self.feature_opt_outs.remove(feature)
            self.last_updated = datetime.now()
    
    def set_privacy_level(self, level: PrivacyLevel) -> None:
        """Set overall privacy level."""
        self.privacy_level = level
        self.last_updated = datetime.now()
        
        # Auto-configure based on privacy level
        if level == PrivacyLevel.COMPLETE_OPT_OUT:
            self.feature_opt_outs = list(FeatureOptOut)
        elif level == PrivacyLevel.ANONYMOUS_ONLY:
            self.anonymous_in_analysis = True
            self.exclude_from_social_mapping = True
        elif level == PrivacyLevel.LIMITED_PARTICIPATION:
            self.exclude_from_social_mapping = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "server_id": self.server_id,
            "privacy_level": self.privacy_level.value,
            "feature_opt_outs": [opt.value for opt in self.feature_opt_outs],
            "anonymous_in_analysis": self.anonymous_in_analysis,
            "exclude_from_social_mapping": self.exclude_from_social_mapping,
            "last_updated": self.last_updated.isoformat(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if hasattr(self, 'updated_at') else self.last_updated.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserPreferences":
        """Create instance from dictionary."""
        # Parse enums
        privacy_level = PrivacyLevel(data.get("privacy_level", "full"))
        feature_opt_outs = [
            FeatureOptOut(opt) for opt in data.get("feature_opt_outs", [])
        ]
        
        # Parse timestamps
        last_updated = data.get("last_updated")
        if isinstance(last_updated, str):
            last_updated = datetime.fromisoformat(last_updated)
        
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        
        return cls(
            user_id=data["user_id"],
            server_id=data["server_id"],
            privacy_level=privacy_level,
            feature_opt_outs=feature_opt_outs,
            anonymous_in_analysis=data.get("anonymous_in_analysis", False),
            exclude_from_social_mapping=data.get("exclude_from_social_mapping", False),
            id=data.get("id"),
            created_at=created_at,
            last_updated=last_updated or datetime.now()
        )
    
    def get_privacy_summary(self) -> str:
        """Get human-readable privacy summary."""
        if self.privacy_level == PrivacyLevel.COMPLETE_OPT_OUT:
            return "🔒 Complete opt-out - No participation in any analysis"
        elif self.privacy_level == PrivacyLevel.ANONYMOUS_ONLY:
            return "👤 Anonymous only - Included in statistics but never mentioned by name"
        elif self.privacy_level == PrivacyLevel.LIMITED_PARTICIPATION:
            return "⚠️ Limited participation - Excluded from detailed social analysis"
        else:
            opt_outs = len(self.feature_opt_outs)
            if opt_outs == 0:
                return "✅ Full participation - All features enabled"
            else:
                return f"⚖️ Selective participation - {opt_outs} features disabled"


class PrivacyManager:
    """Manager for user privacy preferences and compliance."""
    
    def __init__(self, user_prefs_repo):
        self.user_prefs_repo = user_prefs_repo
    
    async def get_user_preferences(self, user_id: str, server_id: str) -> UserPreferences:
        """Get user preferences, creating default if none exist."""
        try:
            prefs = await self.user_prefs_repo.get_by_user_and_server(user_id, server_id)
            if prefs:
                return prefs
        except Exception:
            pass
        
        # Create default preferences
        return UserPreferences(
            user_id=user_id,
            server_id=server_id,
            privacy_level=PrivacyLevel.FULL_PARTICIPATION
        )
    
    async def can_user_participate(
        self, 
        user_id: str, 
        server_id: str, 
        feature: FeatureOptOut
    ) -> bool:
        """Check if user can participate in a specific feature."""
        prefs = await self.get_user_preferences(user_id, server_id)
        return not prefs.is_opted_out_of(feature)
    
    async def filter_messages_by_privacy(
        self, 
        messages: List[Any], 
        server_id: str,
        feature: FeatureOptOut
    ) -> List[Any]:
        """Filter messages based on user privacy preferences."""
        filtered_messages = []
        
        for message in messages:
            try:
                # Try different ways to get user_id from message
                user_id = getattr(message, 'author_id', None)
                if not user_id:
                    user_id = getattr(message, 'user_id', None)
                
                if user_id and await self.can_user_participate(str(user_id), server_id, feature):
                    filtered_messages.append(message)
            except Exception as e:
                # Log and skip problematic messages rather than failing entirely
                logger.warning(f"Error filtering message for privacy: {e}")
                continue
        
        return filtered_messages
    
    async def anonymize_user_references(
        self, 
        content: str, 
        server_id: str
    ) -> str:
        """Anonymize user mentions based on privacy preferences."""
        # This would need to be implemented based on the content format
        # For now, return content as-is
        return content