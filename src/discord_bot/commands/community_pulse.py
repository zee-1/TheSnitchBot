"""
Community Pulse command for The Snitch Discord Bot.
Analyzes server social dynamics and generates engaging community insights.
"""

import discord
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import asyncio

from src.discord_bot.commands.base import PublicCommand, CommandContext, EmbedBuilder
from src.core.logging import get_logger
from src.models.message import Message
from src.models.user_preferences import FeatureOptOut, PrivacyManager

logger = get_logger(__name__)


class CommunityPulseCommand(PublicCommand):
    """Generate community pulse analysis with social insights."""
    
    def __init__(self):
        super().__init__(
            name="community-pulse",
            description="Get real-time community insights and social dynamics",
            cooldown_seconds=15
        )
    
    def define_parameters(self) -> Dict[str, Dict[str, Any]]:
        """Define command parameters for Discord."""
        return {
            "timeframe": {
                "type": str,
                "description": "Time period to analyze",
                "required": False,
                "default": "24h",
                "choices": ["1h", "6h", "24h", "7d", "30d"]
            },
            "style": {
                "type": str,
                "description": "Presentation style for the pulse report",
                "required": False,
                "default": "dashboard",
                "choices": ["dashboard", "story", "weather", "gaming", "network"]
            },
            "focus": {
                "type": str,
                "description": "Specific aspect to focus on",
                "required": False,
                "default": "overall",
                "choices": ["overall", "social", "topics", "mood", "activity", "patterns"]
            }
        }
    
    async def execute(self, ctx: CommandContext, timeframe: str = "24h", style: str = "dashboard", focus: str = "overall"):
        """Execute community pulse analysis."""
        try:
            # Get time range for analysis
            start_time, end_time = self._parse_timeframe(timeframe)
            
            # Collect data for analysis with privacy filtering
            pulse_data = await self._collect_pulse_data(ctx, start_time, end_time)
            
            if not pulse_data["messages"]:
                embed = EmbedBuilder.info(
                    "No Community Activity",
                    f"No messages found in the last {timeframe} to analyze. Try a longer timeframe!"
                )
                await ctx.respond(embed=embed)
                return
            
            # Generate AI analysis
            ai_service = ctx.container.get_ai_service()
            analysis = await ai_service.generate_community_pulse(
                messages=pulse_data["messages"],
                metrics=pulse_data["metrics"],
                server_config=ctx.server_config,
                timeframe=timeframe,
                style=style,
                focus=focus
            )
            
            # Create and send response embed
            embed = await self._create_pulse_embed(analysis, pulse_data, timeframe, style, focus)
            
            # Send to output channel if configured
            try:
                from src.discord_bot.utils.channel_utils import send_to_output_channel
                await send_to_output_channel(ctx, embed)
            except Exception as e:
                logger.warning(f"Failed to send to output channel: {e}")
                await ctx.respond(embed=embed)
                
        except Exception as e:
            logger.error(f"Community pulse analysis failed: {e}", exc_info=True)
            embed = EmbedBuilder.error(
                "Analysis Failed",
                "Failed to generate community pulse. Please try again later."
            )
            await ctx.respond(embed=embed)
    
    def _parse_timeframe(self, timeframe: str) -> tuple[datetime, datetime]:
        """Parse timeframe string into start and end times."""
        end_time = datetime.now()
        
        if timeframe == "1h":
            start_time = end_time - timedelta(hours=1)
        elif timeframe == "6h":
            start_time = end_time - timedelta(hours=6)
        elif timeframe == "24h":
            start_time = end_time - timedelta(hours=24)
        elif timeframe == "7d":
            start_time = end_time - timedelta(days=7)
        elif timeframe == "30d":
            start_time = end_time - timedelta(days=30)
        else:
            start_time = end_time - timedelta(hours=24)
        
        return start_time, end_time
    
    async def _collect_pulse_data(self, ctx: CommandContext, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Collect all data needed for pulse analysis with privacy filtering."""
        message_repo = ctx.container.get_message_repository()
        server_repo = ctx.container.get_server_repository()
        
        # Get privacy manager and filter opted-out users
        try:
            user_prefs_repo = ctx.container.get_user_preferences_repository()
            privacy_manager = PrivacyManager(user_prefs_repo)
        except:
            # If privacy system not available, proceed without filtering
            privacy_manager = None
        
        # Get messages from configured source channel or current channel
        source_channel_id = getattr(ctx.server_config, 'source_channel_id', None)
        
        if source_channel_id:
            # Get from configured source channel
            messages = await message_repo.get_by_channel_and_time_range(
                channel_id=source_channel_id,
                server_id=ctx.server_config.server_id,
                start_time=start_time,
                end_time=end_time,
                limit=500
            )
        else:
            # Get from entire server
            messages = await message_repo.get_by_server_and_time_range(
                server_id=ctx.server_config.server_id,
                start_time=start_time,
                end_time=end_time,
                limit=500
            )
        
        # Apply privacy filtering
        if privacy_manager:
            try:
                messages = await privacy_manager.filter_messages_by_privacy(
                    messages, ctx.server_config.server_id, FeatureOptOut.COMMUNITY_PULSE
                )
                logger.info(f"Applied privacy filtering: {len(messages)} messages after filtering")
            except Exception as e:
                logger.warning(f"Privacy filtering failed, proceeding without: {e}")
        
        # Calculate basic metrics
        metrics = await self._calculate_pulse_metrics(messages)
        
        # Get server stats for context
        server_stats = await server_repo.get_server_stats()
        
        return {
            "messages": messages,
            "metrics": metrics,
            "server_stats": server_stats,
            "timeframe": {
                "start": start_time,
                "end": end_time
            }
        }
    
    async def _calculate_pulse_metrics(self, messages: List[Message]) -> Dict[str, Any]:
        """Calculate pulse metrics from messages."""
        if not messages:
            return self._empty_metrics()
        
        # Basic counts
        total_messages = len(messages)
        unique_users = len(set(msg.author_id for msg in messages))
        total_reactions = sum(msg.total_reactions for msg in messages)
        total_replies = sum(msg.reply_count for msg in messages)
        
        # User activity analysis
        user_activity = {}
        user_reactions = {}
        conversation_chains = 0
        
        for msg in messages:
            # Track user activity
            if msg.author_id not in user_activity:
                user_activity[msg.author_id] = {
                    "messages": 0,
                    "total_chars": 0,
                    "reactions_given": 0,
                    "reactions_received": msg.total_reactions,
                    "replies": msg.reply_count
                }
            
            user_activity[msg.author_id]["messages"] += 1
            user_activity[msg.author_id]["total_chars"] += len(msg.content)
            user_activity[msg.author_id]["reactions_received"] += msg.total_reactions
            
            # Count conversation chains (replies)
            if msg.reply_count > 0:
                conversation_chains += 1
        
        # Find most active users
        most_active = sorted(
            user_activity.items(),
            key=lambda x: x[1]["messages"],
            reverse=True
        )[:5]
        
        # Find most engaging content
        most_engaging = sorted(
            messages,
            key=lambda x: x.total_reactions + (x.reply_count * 2),
            reverse=True
        )[:3]
        
        # Calculate mood indicators (simplified)
        positive_indicators = sum(1 for msg in messages if any(
            emoji in msg.content.lower() 
            for emoji in ["😄", "😂", "🎉", "❤️", "👍", ":)", "lol", "haha"]
        ))
        
        # Activity patterns
        hourly_activity = {}
        for msg in messages:
            try:
                # Handle timestamp as string or datetime
                if isinstance(msg.timestamp, str):
                    # Parse ISO format timestamp string
                    from datetime import datetime
                    timestamp = datetime.fromisoformat(msg.timestamp.replace('Z', '+00:00'))
                    hour = timestamp.hour
                else:
                    hour = msg.timestamp.hour
                hourly_activity[hour] = hourly_activity.get(hour, 0) + 1
            except Exception as e:
                logger.warning(f"Failed to parse timestamp {msg.timestamp}: {e}")
                continue
        
        peak_hours = sorted(hourly_activity.items(), key=lambda x: x[1], reverse=True)[:3]
        
        return {
            "total_messages": total_messages,
            "unique_users": unique_users,
            "total_reactions": total_reactions,
            "total_replies": total_replies,
            "conversation_chains": conversation_chains,
            "avg_message_length": sum(len(msg.content) for msg in messages) / total_messages if messages else 0,
            "most_active_users": most_active,
            "most_engaging_content": most_engaging,
            "positive_indicators": positive_indicators,
            "mood_score": min(100, (positive_indicators / total_messages * 100)) if total_messages > 0 else 50,
            "peak_hours": peak_hours,
            "engagement_rate": (total_reactions + total_replies) / total_messages if total_messages > 0 else 0
        }
    
    def _empty_metrics(self) -> Dict[str, Any]:
        """Return empty metrics structure."""
        return {
            "total_messages": 0,
            "unique_users": 0,
            "total_reactions": 0,
            "total_replies": 0,
            "conversation_chains": 0,
            "avg_message_length": 0,
            "most_active_users": [],
            "most_engaging_content": [],
            "positive_indicators": 0,
            "mood_score": 50,
            "peak_hours": [],
            "engagement_rate": 0
        }
    
    async def _create_pulse_embed(self, analysis: Dict[str, Any], pulse_data: Dict[str, Any], timeframe: str, style: str, focus: str) -> discord.Embed:
        """Create formatted embed for pulse analysis."""
        metrics = pulse_data["metrics"]
        
        # Style-specific formatting
        if style == "dashboard":
            embed = self._create_dashboard_embed(analysis, metrics, timeframe)
        elif style == "story":
            embed = self._create_story_embed(analysis, metrics, timeframe)
        elif style == "weather":
            embed = self._create_weather_embed(analysis, metrics, timeframe)
        elif style == "gaming":
            embed = self._create_gaming_embed(analysis, metrics, timeframe)
        elif style == "network":
            embed = self._create_network_embed(analysis, metrics, timeframe)
        else:
            embed = self._create_dashboard_embed(analysis, metrics, timeframe)
        
        # Add footer with metadata
        embed.set_footer(
            text=f"Community Pulse • {timeframe} • {focus} focus • Generated at {datetime.now().strftime('%H:%M')}"
        )
        
        return embed
    
    def _create_dashboard_embed(self, analysis: Dict[str, Any], metrics: Dict[str, Any], timeframe: str) -> discord.Embed:
        """Create dashboard-style embed."""
        embed = discord.Embed(
            title="📊 Community Pulse Dashboard",
            description=analysis.get("summary", "Community analysis summary"),
            color=self._get_mood_color(metrics["mood_score"]),
            timestamp=datetime.now()
        )
        
        # Activity metrics
        embed.add_field(
            name="💬 Activity Metrics",
            value=f"**Messages:** {metrics['total_messages']}\n"
                  f"**Active Users:** {metrics['unique_users']}\n"
                  f"**Engagement:** {metrics['engagement_rate']:.1f} reactions/replies per message",
            inline=True
        )
        
        # Social metrics
        embed.add_field(
            name="🤝 Social Dynamics",
            value=f"**Conversations:** {metrics['conversation_chains']}\n"
                  f"**Total Reactions:** {metrics['total_reactions']}\n"
                  f"**Community Mood:** {self._get_mood_emoji(metrics['mood_score'])} {metrics['mood_score']:.0f}%",
            inline=True
        )
        
        # Top users
        if metrics["most_active_users"]:
            top_users = "\n".join([
                f"<@{user_id}>: {data['messages']} msgs"
                for user_id, data in metrics["most_active_users"][:3]
            ])
            embed.add_field(
                name="🌟 Most Active",
                value=top_users,
                inline=False
            )
        
        # Add AI insights
        if "insights" in analysis:
            embed.add_field(
                name="🔍 Key Insights",
                value=analysis["insights"][:1000],
                inline=False
            )
        
        return embed
    
    def _create_story_embed(self, analysis: Dict[str, Any], metrics: Dict[str, Any], timeframe: str) -> discord.Embed:
        """Create story-mode embed."""
        embed = discord.Embed(
            title="📖 Community Story",
            description=analysis.get("story", "The tale of your community..."),
            color=discord.Color.purple(),
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="📈 The Numbers Tell a Tale",
            value=f"In the last {timeframe}, {metrics['unique_users']} adventurers shared {metrics['total_messages']} messages, "
                  f"sparking {metrics['total_reactions']} reactions and {metrics['conversation_chains']} conversations.",
            inline=False
        )
        
        return embed
    
    def _create_weather_embed(self, analysis: Dict[str, Any], metrics: Dict[str, Any], timeframe: str) -> discord.Embed:
        """Create weather-report embed."""
        weather_emoji = self._get_weather_emoji(metrics["mood_score"])
        
        embed = discord.Embed(
            title=f"{weather_emoji} Community Weather Report",
            description=f"Current conditions: {self._get_weather_description(metrics['mood_score'])}",
            color=self._get_mood_color(metrics["mood_score"]),
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="🌡️ Activity Temperature",
            value=f"{self._get_activity_temp(metrics['total_messages'])}°C\n"
                  f"Feels like: {metrics['engagement_rate']:.1f} interactions",
            inline=True
        )
        
        embed.add_field(
            name="💨 Social Wind Speed",
            value=f"{metrics['conversation_chains']} conversations/hour\n"
                  f"Direction: {self._get_trend_direction(metrics)}",
            inline=True
        )
        
        return embed
    
    def _create_gaming_embed(self, analysis: Dict[str, Any], metrics: Dict[str, Any], timeframe: str) -> discord.Embed:
        """Create gaming-stats embed."""
        embed = discord.Embed(
            title="🎮 Community Gaming Stats",
            description=f"Server Performance in the last {timeframe}",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        # Gaming-style stats
        embed.add_field(
            name="⚡ Performance Metrics",
            value=f"**XP Gained:** {metrics['total_messages']} points\n"
                  f"**Players Active:** {metrics['unique_users']}\n"
                  f"**Combo Multiplier:** {metrics['engagement_rate']:.1f}x",
            inline=True
        )
        
        embed.add_field(
            name="🏆 Leaderboard",
            value="\n".join([
                f"#{i+1} <@{user_id}> - {data['messages']} pts"
                for i, (user_id, data) in enumerate(metrics["most_active_users"][:3])
            ]) if metrics["most_active_users"] else "No players found",
            inline=True
        )
        
        return embed
    
    def _create_network_embed(self, analysis: Dict[str, Any], metrics: Dict[str, Any], timeframe: str) -> discord.Embed:
        """Create social-network embed."""
        embed = discord.Embed(
            title="🌐 Social Network Analysis",
            description="Community connection patterns",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        # Network stats
        embed.add_field(
            name="🔗 Network Health",
            value=f"**Nodes:** {metrics['unique_users']} users\n"
                  f"**Connections:** {metrics['conversation_chains']}\n"
                  f"**Network Density:** {self._calculate_network_density(metrics):.2f}",
            inline=True
        )
        
        return embed
    
    def _get_mood_color(self, mood_score: float) -> discord.Color:
        """Get color based on mood score."""
        if mood_score >= 80:
            return discord.Color.green()
        elif mood_score >= 60:
            return discord.Color.yellow()
        elif mood_score >= 40:
            return discord.Color.orange()
        else:
            return discord.Color.red()
    
    def _get_mood_emoji(self, mood_score: float) -> str:
        """Get emoji based on mood score."""
        if mood_score >= 80:
            return "😄"
        elif mood_score >= 60:
            return "🙂"
        elif mood_score >= 40:
            return "😐"
        else:
            return "😔"
    
    def _get_weather_emoji(self, mood_score: float) -> str:
        """Get weather emoji based on mood."""
        if mood_score >= 80:
            return "☀️"
        elif mood_score >= 60:
            return "⛅"
        elif mood_score >= 40:
            return "🌧️"
        else:
            return "⛈️"
    
    def _get_weather_description(self, mood_score: float) -> str:
        """Get weather description."""
        if mood_score >= 80:
            return "Bright and cheerful with high energy"
        elif mood_score >= 60:
            return "Partly sunny with moderate activity"
        elif mood_score >= 40:
            return "Overcast with light conversation showers"
        else:
            return "Stormy with scattered drama"
    
    def _get_activity_temp(self, message_count: int) -> int:
        """Convert message count to temperature."""
        return min(50, message_count // 2)
    
    def _get_trend_direction(self, metrics: Dict[str, Any]) -> str:
        """Get trend direction."""
        if metrics["engagement_rate"] > 2:
            return "📈 Rising"
        elif metrics["engagement_rate"] > 1:
            return "➡️ Steady"
        else:
            return "📉 Calm"
    
    def _calculate_network_density(self, metrics: Dict[str, Any]) -> float:
        """Calculate network density."""
        users = metrics["unique_users"]
        if users < 2:
            return 0.0
        
        max_connections = users * (users - 1) / 2
        actual_connections = metrics["conversation_chains"]
        return actual_connections / max_connections if max_connections > 0 else 0.0