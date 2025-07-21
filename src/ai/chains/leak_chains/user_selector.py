"""
Enhanced User Selector for Leak Command
Implements improved random user selection with better filtering.
"""

from typing import List, Dict, Any, Optional
import random
from datetime import datetime, timedelta, timezone
from src.core.logging import get_logger

logger = get_logger(__name__)


class EnhancedUserSelector:
    """Enhanced user selection with improved criteria and randomization."""
    
    def __init__(
        self,
        min_recent_messages: int = 2,
        exclude_recent_targets: bool = True,
        min_message_length: int = 10,
        max_users_to_consider: int = 50,
        fallback_candidate_limit: int = 10
    ):
        self.min_recent_messages = min_recent_messages
        self.exclude_recent_targets = exclude_recent_targets
        self.min_message_length = min_message_length
        self.max_users_to_consider = max_users_to_consider
        self.fallback_candidate_limit = fallback_candidate_limit
        self.recent_targets = {}  # Store recent targets per server
        self.logger = get_logger(__name__)
    
    async def select_random_user(
        self,
        recent_messages: List[Any],
        command_user_id: str,
        server_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Select a single random user from recent activity.
        
        Args:
            recent_messages: List of recent Discord messages
            command_user_id: ID of user who ran the command
            server_id: Server ID for tracking recent targets
            
        Returns:
            Dictionary with selected user info or None if no suitable users
        """
        try:
            self.logger.info(f"Starting user selection for server {server_id}")
            
            # Build candidate pool
            candidates = self._build_candidate_pool(recent_messages, command_user_id)
            
            if not candidates:
                self.logger.warning("No candidates found")
                return None
            
            # Apply selection filters
            filtered_candidates = self._apply_selection_filters(candidates, server_id)
            
            if not filtered_candidates:
                self.logger.warning("No candidates passed filtering, applying fallback strategy")
                # Fallback: If recently-targeted filter eliminated all users, 
                # select any N users at random from all valid candidates
                filtered_candidates = self._apply_fallback_selection(candidates, server_id)
            
            # Select random user
            selected_user = self._select_random_user(filtered_candidates)
            
            # Track selection for future filtering
            self._track_selection(selected_user["user_id"], server_id)
            
            self.logger.info(f"Selected user {selected_user['user_id']} from {len(candidates)} candidates")
            return selected_user
            
        except Exception as e:
            self.logger.error(f"User selection failed: {e}")
            return None
    
    def _build_candidate_pool(self, recent_messages: List[Any], command_user_id: str) -> List[Dict[str, Any]]:
        """Build pool of potential target users."""
        
        user_activity = {}
        
        # Analyze recent messages to build user profiles
        for msg in recent_messages[-200:]:  # Look at last 200 messages
            try:
                # Skip bots and command user
                if (msg.author.bot or 
                    str(msg.author.id) == command_user_id or
                    len(msg.content.strip()) < self.min_message_length):
                    continue
                
                user_id = str(msg.author.id)
                
                # Initialize user data if not exists
                if user_id not in user_activity:
                    user_activity[user_id] = {
                        'user_id': user_id,
                        'user_obj': msg.author,
                        'message_count': 0,
                        'recent_messages': [],
                        'total_chars': 0,
                        'last_message_time': None,
                        'channels_active': set(),
                        'avg_message_length': 0,
                        'activity_score': 0
                    }
                
                # Update user activity data
                user_data = user_activity[user_id]
                user_data['message_count'] += 1
                user_data['recent_messages'].append(msg.content)
                user_data['total_chars'] += len(msg.content)
                user_data['channels_active'].add(str(msg.channel.id))
                user_data['last_message_time'] = msg.created_at if hasattr(msg, 'created_at') else datetime.now(timezone.utc)
                
                # Keep only recent messages for analysis
                if len(user_data['recent_messages']) > 10:
                    user_data['recent_messages'] = user_data['recent_messages'][-10:]
                
            except Exception as e:
                self.logger.warning(f"Error processing message: {e}")
                continue
        
        # Calculate additional metrics and filter candidates
        candidates = []
        
        for user_data in user_activity.values():
            try:
                # Calculate metrics
                user_data['avg_message_length'] = (
                    user_data['total_chars'] / user_data['message_count'] 
                    if user_data['message_count'] > 0 else 0
                )
                
                # Calculate activity score (for potential future weighting)
                if user_data['last_message_time']:
                    # Ensure both datetimes are timezone-aware for comparison
                    now = datetime.now(timezone.utc)
                    last_msg_time = user_data['last_message_time']
                    
                    # If last_msg_time is naive, make it aware
                    if last_msg_time.tzinfo is None:
                        last_msg_time = last_msg_time.replace(tzinfo=timezone.utc)
                    
                    recency_hours = (now - last_msg_time).total_seconds() / 3600
                else:
                    recency_hours = 24
                recency_factor = max(0, 1 - (recency_hours / 24))  # Decay over 24 hours
                
                user_data['activity_score'] = (
                    user_data['message_count'] * 0.4 +  # Message frequency
                    (user_data['avg_message_length'] / 100) * 0.2 +  # Message substance
                    len(user_data['channels_active']) * 0.2 +  # Channel diversity
                    recency_factor * 0.2  # Recent activity
                )
                
                # Filter by minimum criteria
                if (user_data['message_count'] >= self.min_recent_messages and
                    user_data['avg_message_length'] >= self.min_message_length):
                    candidates.append(user_data)
                
            except Exception as e:
                self.logger.warning(f"Error calculating user metrics: {e}")
                continue
        
        # Sort by activity score and limit to reasonable number
        candidates.sort(key=lambda x: x['activity_score'], reverse=True)
        return candidates[:self.max_users_to_consider]
    
    def _apply_selection_filters(self, candidates: List[Dict[str, Any]], server_id: str) -> List[Dict[str, Any]]:
        """Apply additional filtering logic to candidates."""
        
        filtered = []
        
        for candidate in candidates:
            try:
                user_id = candidate['user_id']
                
                # Filter 1: Exclude recently targeted users
                if self.exclude_recent_targets and self._was_recently_targeted(user_id, server_id):
                    continue
                
                # Filter 2: Prefer users with moderate activity (not too high, not too low)
                activity_score = candidate['activity_score']
                if activity_score < 0.1:  # Too inactive
                    continue
                
                # Filter 3: Ensure user has enough content for analysis
                if len(candidate['recent_messages']) < 1:
                    continue
                
                # Filter 4: Skip users with very short messages only
                if candidate['avg_message_length'] < 15:
                    continue
                
                filtered.append(candidate)
                
            except Exception as e:
                self.logger.warning(f"Error filtering candidate: {e}")
                continue
        
        return filtered
    
    def _apply_fallback_selection(self, candidates: List[Dict[str, Any]], server_id: str) -> List[Dict[str, Any]]:
        """Apply fallback selection when no candidates pass the recent-target filter."""
        
        fallback_candidates = []
        
        # Apply only essential filters, ignoring recent-target restriction
        for candidate in candidates:
            try:
                user_id = candidate['user_id']
                
                # Apply only basic quality filters, skip recent-target filter
                
                # Filter: Ensure minimum activity level
                activity_score = candidate['activity_score']
                if activity_score < 0.05:  # Lower threshold for fallback
                    continue
                
                # Filter: Ensure user has some content for analysis
                if len(candidate['recent_messages']) < 1:
                    continue
                
                # Filter: Skip users with extremely short messages only
                if candidate['avg_message_length'] < 10:  # Lower threshold for fallback
                    continue
                
                fallback_candidates.append(candidate)
                
            except Exception as e:
                self.logger.warning(f"Error in fallback filtering for candidate: {e}")
                continue
        
        if not fallback_candidates:
            # If even fallback fails, return the top candidates by activity
            self.logger.warning("Fallback filtering failed, using top active candidates")
            fallback_candidates = candidates[:min(self.fallback_candidate_limit, len(candidates))]
        
        # Randomly shuffle and limit to configurable number for selection
        import random
        random.shuffle(fallback_candidates)
        max_fallback_candidates = min(self.fallback_candidate_limit, len(fallback_candidates))
        
        self.logger.info(f"Fallback selection: {len(fallback_candidates)} candidates available, using top {max_fallback_candidates}")
        return fallback_candidates[:max_fallback_candidates]
    
    def _select_random_user(self, candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Select a user randomly from filtered candidates."""
        
        if not candidates:
            raise ValueError("No candidates available for selection")
        
        # Pure random selection - this is the core requirement
        selected_candidate = random.choice(candidates)
        
        # Extract user info for return
        try:
            user_obj = selected_candidate['user_obj']
            return {
                'user_id': selected_candidate['user_id'],
                'user_obj': user_obj,
                'display_name': (
                    user_obj.display_name 
                    if hasattr(user_obj, 'display_name') 
                    else user_obj.name
                ),
                'username': user_obj.name,
                'recent_messages': selected_candidate['recent_messages'],
                'message_count': selected_candidate['message_count'],
                'activity_score': selected_candidate['activity_score'],
                'channels_active': list(selected_candidate['channels_active'])
            }
        except Exception as e:
            self.logger.error(f"Error extracting user info: {e}")
            # Return minimal info as fallback
            return {
                'user_id': selected_candidate['user_id'],
                'user_obj': selected_candidate['user_obj'],
                'display_name': f"User-{selected_candidate['user_id'][:8]}",
                'username': f"User-{selected_candidate['user_id'][:8]}",
                'recent_messages': selected_candidate.get('recent_messages', []),
                'message_count': selected_candidate.get('message_count', 0),
                'activity_score': selected_candidate.get('activity_score', 0.5),
                'channels_active': []
            }
    
    def _was_recently_targeted(self, user_id: str, server_id: str, hours: int = 24) -> bool:
        """Check if user was targeted recently."""
        
        if server_id not in self.recent_targets:
            return False
        
        server_targets = self.recent_targets[server_id]
        
        if user_id not in server_targets:
            return False
        
        last_targeted = server_targets[user_id]
        now = datetime.now(timezone.utc)
        
        # Ensure last_targeted is timezone-aware
        if last_targeted.tzinfo is None:
            last_targeted = last_targeted.replace(tzinfo=timezone.utc)
            
        time_since = now - last_targeted
        
        return time_since.total_seconds() < (hours * 3600)
    
    def _track_selection(self, user_id: str, server_id: str) -> None:
        """Track user selection for future filtering."""
        
        if server_id not in self.recent_targets:
            self.recent_targets[server_id] = {}
        
        self.recent_targets[server_id][user_id] = datetime.now(timezone.utc)
        
        # Clean up old entries (older than 7 days)
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=7)
        server_targets = self.recent_targets[server_id]
        
        old_targets = []
        for uid, timestamp in server_targets.items():
            # Ensure timestamp is timezone-aware for comparison
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            if timestamp < cutoff_time:
                old_targets.append(uid)
        
        for uid in old_targets:
            del server_targets[uid]
    
    def get_selection_stats(self, server_id: str) -> Dict[str, Any]:
        """Get statistics about recent selections."""
        
        if server_id not in self.recent_targets:
            return {
                'total_recent_targets': 0,
                'oldest_target_age_hours': 0,
                'targets_in_last_24h': 0
            }
        
        server_targets = self.recent_targets[server_id]
        now = datetime.now(timezone.utc)
        
        targets_24h = 0
        for timestamp in server_targets.values():
            # Ensure timestamp is timezone-aware for comparison
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            if (now - timestamp).total_seconds() < 86400:  # 24 hours
                targets_24h += 1
        
        oldest_age_hours = 0
        if server_targets:
            oldest_timestamp = min(server_targets.values())
            # Ensure timestamp is timezone-aware for comparison
            if oldest_timestamp.tzinfo is None:
                oldest_timestamp = oldest_timestamp.replace(tzinfo=timezone.utc)
            oldest_age_hours = (now - oldest_timestamp).total_seconds() / 3600
        
        return {
            'total_recent_targets': len(server_targets),
            'oldest_target_age_hours': oldest_age_hours,
            'targets_in_last_24h': targets_24h
        }
    
    def reset_target_history(self, server_id: str) -> None:
        """Reset target history for a server (useful for testing)."""
        if server_id in self.recent_targets:
            del self.recent_targets[server_id]
        self.logger.info(f"Reset target history for server {server_id}")


# Global instance for use across the application
_user_selector: Optional[EnhancedUserSelector] = None


def get_user_selector() -> EnhancedUserSelector:
    """Get or create the global user selector instance."""
    global _user_selector
    
    if _user_selector is None:
        _user_selector = EnhancedUserSelector()
    
    return _user_selector