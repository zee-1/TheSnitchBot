"""
User preferences repository for The Snitch Discord Bot.
Handles CRUD operations for user privacy preferences in Azure Cosmos DB.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime

from src.data.repositories.base import BaseRepository
from src.data.cosmos_client import CosmosDBClient
from src.models.user_preferences import UserPreferences, FeatureOptOut, PrivacyLevel
from src.core.logging import get_logger

logger = get_logger(__name__)


class UserPreferencesRepository(BaseRepository[UserPreferences]):
    """Repository for managing user privacy preferences."""
    
    def __init__(self, cosmos_client: CosmosDBClient, container_name: str):
        super().__init__(cosmos_client, container_name, UserPreferences)
    
    async def get_by_user_and_server(self, user_id: str, server_id: str) -> Optional[UserPreferences]:
        """Get user preferences for a specific user in a server."""
        try:
            query = """
            SELECT * FROM c 
            WHERE c.user_id = @user_id 
            AND c.server_id = @server_id
            """
            parameters = [
                {"name": "@user_id", "value": user_id},
                {"name": "@server_id", "value": server_id}
            ]
            
            results = await self.query(
                query=query,
                parameters=parameters,
                partition_key=server_id,
                max_count=1
            )
            
            return results[0] if results else None
            
        except Exception as e:
            logger.error(f"Error getting user preferences for {user_id} in server {server_id}: {e}")
            return None
    
    async def get_all_server_preferences(self, server_id: str) -> List[UserPreferences]:
        """Get all user preferences for a server."""
        try:
            query = """
            SELECT * FROM c 
            WHERE c.server_id = @server_id
            """
            parameters = [
                {"name": "@server_id", "value": server_id}
            ]
            
            return await self.query(
                query=query,
                parameters=parameters,
                partition_key=server_id
            )
            
        except Exception as e:
            logger.error(f"Error getting all preferences for server {server_id}: {e}")
            return []
    
    async def get_opted_out_users(
        self, 
        server_id: str, 
        feature: FeatureOptOut
    ) -> List[str]:
        """Get list of user IDs who opted out of a specific feature."""
        try:
            query = """
            SELECT c.user_id FROM c 
            WHERE c.server_id = @server_id
            AND (
                c.privacy_level = @opt_out_level
                OR ARRAY_CONTAINS(c.feature_opt_outs, @feature)
            )
            """
            parameters = [
                {"name": "@server_id", "value": server_id},
                {"name": "@opt_out_level", "value": PrivacyLevel.COMPLETE_OPT_OUT.value},
                {"name": "@feature", "value": feature.value}
            ]
            
            results = await self.query(
                query=query,
                parameters=parameters,
                partition_key=server_id
            )
            
            return [result.user_id for result in results]
            
        except Exception as e:
            logger.error(f"Error getting opted out users for feature {feature}: {e}")
            return []
    
    async def get_anonymous_users(self, server_id: str) -> List[str]:
        """Get list of user IDs who want anonymous participation."""
        try:
            query = """
            SELECT c.user_id FROM c 
            WHERE c.server_id = @server_id
            AND (
                c.privacy_level = @anonymous_level
                OR c.anonymous_in_analysis = true
            )
            """
            parameters = [
                {"name": "@server_id", "value": server_id},
                {"name": "@anonymous_level", "value": PrivacyLevel.ANONYMOUS_ONLY.value}
            ]
            
            results = await self.query(
                query=query,
                parameters=parameters,
                partition_key=server_id
            )
            
            return [result.user_id for result in results]
            
        except Exception as e:
            logger.error(f"Error getting anonymous users for server {server_id}: {e}")
            return []
    
    async def create_or_update_preferences(
        self, 
        user_id: str, 
        server_id: str,
        privacy_level: Optional[PrivacyLevel] = None,
        feature_opt_outs: Optional[List[FeatureOptOut]] = None,
        anonymous_in_analysis: Optional[bool] = None,
        exclude_from_social_mapping: Optional[bool] = None
    ) -> UserPreferences:
        """Create or update user preferences."""
        try:
            # Get existing preferences
            existing = await self.get_by_user_and_server(user_id, server_id)
            
            if existing:
                # Update existing preferences
                if privacy_level is not None:
                    existing.set_privacy_level(privacy_level)
                
                if feature_opt_outs is not None:
                    existing.feature_opt_outs = feature_opt_outs
                
                if anonymous_in_analysis is not None:
                    existing.anonymous_in_analysis = anonymous_in_analysis
                
                if exclude_from_social_mapping is not None:
                    existing.exclude_from_social_mapping = exclude_from_social_mapping
                
                existing.last_updated = datetime.now()
                await self.update(existing)
                return existing
            
            else:
                # Create new preferences
                new_prefs = UserPreferences(
                    user_id=user_id,
                    server_id=server_id,
                    privacy_level=privacy_level or PrivacyLevel.FULL_PARTICIPATION,
                    feature_opt_outs=feature_opt_outs or [],
                    anonymous_in_analysis=anonymous_in_analysis or False,
                    exclude_from_social_mapping=exclude_from_social_mapping or False
                )
                
                await self.create(new_prefs)
                return new_prefs
                
        except Exception as e:
            logger.error(f"Error creating/updating preferences for {user_id}: {e}")
            raise
    
    async def opt_user_out_of_feature(
        self, 
        user_id: str, 
        server_id: str, 
        feature: FeatureOptOut
    ) -> bool:
        """Opt user out of a specific feature."""
        try:
            prefs = await self.get_by_user_and_server(user_id, server_id)
            
            if not prefs:
                # Create new preferences with opt-out
                prefs = UserPreferences(
                    user_id=user_id,
                    server_id=server_id,
                    feature_opt_outs=[feature]
                )
                await self.create(prefs)
            else:
                # Update existing preferences
                prefs.opt_out_of_feature(feature)
                await self.update(prefs)
            
            logger.info(f"User {user_id} opted out of {feature.value}")
            return True
            
        except Exception as e:
            logger.error(f"Error opting user {user_id} out of {feature.value}: {e}")
            return False
    
    async def opt_user_in_to_feature(
        self, 
        user_id: str, 
        server_id: str, 
        feature: FeatureOptOut
    ) -> bool:
        """Opt user back into a specific feature."""
        try:
            prefs = await self.get_by_user_and_server(user_id, server_id)
            
            if prefs:
                prefs.opt_in_to_feature(feature)
                await self.update(prefs)
                logger.info(f"User {user_id} opted back into {feature.value}")
                return True
            
            # If no preferences exist, user is already opted in by default
            return True
            
        except Exception as e:
            logger.error(f"Error opting user {user_id} into {feature.value}: {e}")
            return False
    
    async def get_privacy_statistics(self, server_id: str) -> Dict[str, Any]:
        """Get privacy statistics for a server."""
        try:
            query = """
            SELECT 
                c.privacy_level,
                COUNT(1) as count
            FROM c 
            WHERE c.server_id = @server_id
            GROUP BY c.privacy_level
            """
            parameters = [
                {"name": "@server_id", "value": server_id}
            ]
            
            results = await self.query(
                query=query,
                parameters=parameters,
                partition_key=server_id
            )
            
            stats = {
                "total_users_with_preferences": sum(r["count"] for r in results),
                "privacy_levels": {r["privacy_level"]: r["count"] for r in results}
            }
            
            # Get feature-specific opt-out counts
            feature_query = """
            SELECT 
                f.feature,
                COUNT(1) as count
            FROM c
            JOIN f IN c.feature_opt_outs
            WHERE c.server_id = @server_id
            GROUP BY f.feature
            """
            
            feature_results = await self.query(
                query=feature_query,
                parameters=parameters,
                partition_key=server_id
            )
            
            stats["feature_opt_outs"] = {
                r["feature"]: r["count"] for r in feature_results
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting privacy statistics for server {server_id}: {e}")
            return {
                "error": str(e),
                "total_users_with_preferences": 0,
                "privacy_levels": {},
                "feature_opt_outs": {}
            }