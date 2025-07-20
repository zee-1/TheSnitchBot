
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

import discord

from src.discord_bot.commands.breaking_news import BreakingNewsCommand
from src.core.exceptions import AIServiceError
from src.models.server import ServerConfig, PersonaType

# Mock the get_ai_service function to avoid actual AI calls
@pytest.fixture(autouse=True)
def mock_get_ai_service():
    with patch('src.ai.get_ai_service') as mock:
        yield mock

@pytest.fixture
def command():
    return BreakingNewsCommand()

@pytest.fixture
def mock_context():
    """Creates a mock command context."""
    ctx = MagicMock()
    ctx.defer = AsyncMock()
    ctx.respond = AsyncMock()
    ctx.user_id = "test_user"
    ctx.guild_id = "test_guild"
    ctx.channel_id = "112233445566778899"
    ctx.channel.name = "test-channel"
    ctx.server_config = ServerConfig(
        server_id="123456789012345678",
        server_name="Test Server",
        owner_id="987654321098765432",
        persona=PersonaType.SASSY_REPORTER
    )
    
    # Mock the discord channel and its history
    mock_channel = MagicMock()
    mock_channel.history = MagicMock()
    
    # Create mock messages
    mock_messages = []
    for i in range(10):
        msg = MagicMock()
        msg.author.bot = False
        msg.content = f"This is test message {i}"
        msg.controversy_score = 0.5
        mock_messages.append(msg)
        
    # Make channel.history an async iterator
    async def mock_history_iterator(*args, **kwargs):
        for msg in mock_messages:
            yield msg
            
    mock_channel.history.return_value = mock_history_iterator()
    
    # Mock the interaction client to return the mock channel
    ctx.interaction.client.get_channel.return_value = mock_channel
    
    return ctx


@pytest.mark.asyncio
async def test_breaking_news_success(command, mock_context, mock_get_ai_service):
    """Tests the breaking news command under normal conditions."""
    
    # Mock the AI service response
    mock_ai_service = AsyncMock()
    mock_ai_service.generate_smart_breaking_news.return_value = "This is a breaking news bulletin."
    mock_get_ai_service.return_value = mock_ai_service
    
    # Execute the command
    await command.execute(mock_context)
    
    # Assertions
    mock_context.defer.assert_called_once()
    mock_ai_service.generate_smart_breaking_news.assert_called_once()
    mock_context.respond.assert_called_once()
    
    # Check the content of the response
    response_embed = mock_context.respond.call_args[1]['embed']
    assert response_embed.title == "🚨 BREAKING NEWS"
    assert response_embed.description == "This is a breaking news bulletin."


@pytest.mark.asyncio
async def test_breaking_news_ai_service_error(command, mock_context, mock_get_ai_service):
    """Tests the fallback to mock bulletin when AI service fails."""
    
    # Mock the AI service to raise an error
    mock_ai_service = AsyncMock()
    mock_ai_service.generate_smart_breaking_news.side_effect = AIServiceError("AI is down")
    mock_get_ai_service.return_value = mock_ai_service
    
    # Execute the command
    await command.execute(mock_context)
    
    # Assertions
    mock_context.defer.assert_called_once()
    mock_ai_service.generate_smart_breaking_news.assert_called_once()
    mock_context.respond.assert_called_once()
    
    # Check that the mock bulletin was used
    response_embed = mock_context.respond.call_args[1]['embed']
    assert "BREAKING:" in response_embed.description


@pytest.mark.asyncio
async def test_breaking_news_insufficient_content(command, mock_context):
    """Tests the command when there are not enough messages."""
    
    # Modify the mock channel to return fewer messages
    mock_channel = MagicMock()
    mock_channel.history = MagicMock()
    
    async def mock_history_iterator(*args, **kwargs):
        for i in range(2): # Only 2 messages
            msg = MagicMock()
            msg.author.bot = False
            msg.content = f"Short message {i}"
            yield msg
            
    mock_channel.history.return_value = mock_history_iterator()
    mock_context.interaction.client.get_channel.return_value = mock_channel
    
    # Execute the command
    await command.execute(mock_context)
    
    # Assertions
    mock_context.defer.assert_called_once()
    mock_context.respond.assert_called_once()
    
    response_embed = mock_context.respond.call_args[1]['embed']
    assert response_embed.title == "⚠️ Insufficient Activity"

