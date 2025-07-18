# Python Backend Structure - The Snitch Discord Bot

## Overview
This document outlines the Python-specific backend structure for "The Snitch" Discord bot, optimized for Azure cloud services and following Python best practices.

## Technology Stack

### Core Framework & Libraries
- **Azure Functions**: `azure-functions` for serverless compute
- **Discord Integration**: `discord.py` for Discord API
- **AI/ML**: `langchain`, `groq` for AI processing
- **Database**: `azure-cosmos` for Cosmos DB, `asyncpg` for PostgreSQL
- **Vector DB**: `chromadb` for embeddings and similarity search
- **HTTP Client**: `httpx` for async HTTP requests
- **Configuration**: `pydantic` for settings management
- **Logging**: `structlog` for structured logging

### Azure SDK for Python
- `azure-functions`
- `azure-cosmos`
- `azure-storage-blob`
- `azure-servicebus`
- `azure-keyvault-secrets`
- `azure-monitor-opentelemetry`

## Project Structure

```
src/
├── __init__.py
├── main.py                    # Application entry point
├── requirements.txt           # Python dependencies
├── host.json                  # Azure Functions host config
├── local.settings.json        # Local development settings
├── function_app.py            # Azure Functions app definition
│
├── core/                      # Core application logic
│   ├── __init__.py
│   ├── config.py              # Configuration management
│   ├── dependencies.py        # Dependency injection
│   ├── exceptions.py          # Custom exceptions
│   └── logging.py             # Logging configuration
│
├── models/                    # Data models
│   ├── __init__.py
│   ├── base.py                # Base model classes
│   ├── server.py              # Server configuration model
│   ├── message.py             # Message model
│   ├── tip.py                 # Tip submission model
│   ├── newsletter.py          # Newsletter model
│   └── user.py                # User model
│
├── functions/                 # Azure Functions
│   ├── __init__.py
│   ├── timer_newsletter.py    # Timer-triggered newsletter
│   ├── discord_commands.py    # HTTP-triggered commands
│   ├── message_processor.py   # Service Bus triggered processor
│   └── health_check.py        # Health check endpoint
│
├── services/                  # Business logic services
│   ├── __init__.py
│   ├── discord_service.py     # Discord API service
│   ├── ai_service.py          # AI processing service
│   ├── newsletter_service.py  # Newsletter generation
│   ├── command_service.py     # Command processing
│   ├── message_service.py     # Message processing
│   └── tip_service.py         # Tip management
│
├── data/                      # Data access layer
│   ├── __init__.py
│   ├── repositories/          # Repository pattern
│   │   ├── __init__.py
│   │   ├── base.py            # Base repository
│   │   ├── server_repository.py
│   │   ├── message_repository.py
│   │   ├── tip_repository.py
│   │   └── newsletter_repository.py
│   ├── cosmos_client.py       # Cosmos DB client
│   ├── blob_client.py         # Blob storage client
│   └── chroma_client.py       # ChromaDB client
│
├── ai/                        # AI processing modules
│   ├── __init__.py
│   ├── chains/                # LangChain components
│   │   ├── __init__.py
│   │   ├── news_desk.py       # Story identification
│   │   ├── editor_chief.py    # Story selection
│   │   └── star_reporter.py   # Article writing
│   ├── prompts/               # Prompt templates
│   │   ├── __init__.py
│   │   ├── newsletter.py      # Newsletter prompts
│   │   ├── commands.py        # Command prompts
│   │   └── personas.py        # Persona templates
│   ├── groq_client.py         # Groq API client
│   ├── embedding_service.py   # Text embedding service
│   └── pipeline.py            # AI pipeline orchestration
│
├── discord/                   # Discord integration
│   ├── __init__.py
│   ├── client.py              # Discord client
│   ├── commands/              # Slash commands
│   │   ├── __init__.py
│   │   ├── base.py            # Base command class
│   │   ├── breaking_news.py   # Breaking news command
│   │   ├── fact_check.py      # Fact check command
│   │   ├── leak.py            # Leak command
│   │   ├── config_commands.py # Configuration commands
│   │   └── tip_command.py     # Tip submission command
│   ├── handlers/              # Event handlers
│   │   ├── __init__.py
│   │   ├── message_handler.py
│   │   ├── interaction_handler.py
│   │   └── error_handler.py
│   └── utils/                 # Discord utilities
│       ├── __init__.py
│       ├── formatters.py      # Message formatting
│       ├── validators.py      # Input validation
│       └── permissions.py     # Permission checks
│
├── messaging/                 # Service communication
│   ├── __init__.py
│   ├── service_bus.py         # Service Bus client
│   ├── publishers.py          # Message publishers
│   ├── subscribers.py         # Message subscribers
│   └── schemas.py             # Message schemas
│
├── security/                  # Security modules
│   ├── __init__.py
│   ├── key_vault.py           # Key Vault client
│   ├── auth.py                # Authentication
│   ├── encryption.py          # Encryption utilities
│   └── secrets.py             # Secret management
│
├── monitoring/                # Observability
│   ├── __init__.py
│   ├── metrics.py             # Metrics collection
│   ├── tracing.py             # Distributed tracing
│   ├── health.py              # Health checks
│   └── alerts.py              # Alert handling
│
├── utils/                     # Shared utilities
│   ├── __init__.py
│   ├── datetime_utils.py      # Date/time utilities
│   ├── text_utils.py          # Text processing
│   ├── validation.py          # Input validation
│   ├── retry.py               # Retry logic
│   └── cache.py               # Caching utilities
│
└── tests/                     # Test suites
    ├── __init__.py
    ├── conftest.py            # Pytest configuration
    ├── unit/                  # Unit tests
    │   ├── test_services/
    │   ├── test_models/
    │   └── test_utils/
    ├── integration/           # Integration tests
    │   ├── test_discord/
    │   ├── test_database/
    │   └── test_ai/
    └── fixtures/              # Test fixtures
        ├── discord_data.py
        ├── database_data.py
        └── ai_responses.py
```

## Key Python Components

### 1. Core Configuration (`core/config.py`)
```python
from pydantic import BaseSettings, Field
from typing import Optional

class Settings(BaseSettings):
    # Discord
    discord_token: str = Field(..., env="DISCORD_TOKEN")
    discord_client_id: str = Field(..., env="DISCORD_CLIENT_ID")
    
    # Azure
    cosmos_connection_string: str = Field(..., env="COSMOS_CONNECTION_STRING")
    blob_connection_string: str = Field(..., env="BLOB_CONNECTION_STRING")
    service_bus_connection_string: str = Field(..., env="SERVICE_BUS_CONNECTION_STRING")
    key_vault_url: str = Field(..., env="KEY_VAULT_URL")
    
    # AI
    groq_api_key: str = Field(..., env="GROQ_API_KEY")
    
    # ChromaDB
    chroma_host: str = Field("localhost", env="CHROMA_HOST")
    chroma_port: int = Field(8000, env="CHROMA_PORT")
    
    class Config:
        env_file = ".env"
        case_sensitive = False
```

### 2. Azure Functions Entry Point (`function_app.py`)
```python
import azure.functions as func
import logging
from src.functions.timer_newsletter import timer_newsletter_handler
from src.functions.discord_commands import discord_commands_handler
from src.functions.message_processor import message_processor_handler

app = func.FunctionApp()

@app.timer_trigger(schedule="0 */5 * * * *", arg_name="mytimer")
def timer_newsletter(mytimer: func.TimerRequest) -> None:
    return timer_newsletter_handler(mytimer)

@app.route(route="discord/commands", auth_level=func.AuthLevel.FUNCTION)
def discord_commands(req: func.HttpRequest) -> func.HttpResponse:
    return discord_commands_handler(req)

@app.service_bus_queue_trigger(
    arg_name="msg",
    connection="SERVICE_BUS_CONNECTION_STRING",
    queue_name="message-processing"
)
def message_processor(msg: func.ServiceBusMessage) -> None:
    return message_processor_handler(msg)
```

### 3. Discord Service (`services/discord_service.py`)
```python
import discord
from discord.ext import commands
from typing import Optional, List
from src.models.message import Message
from src.core.config import Settings

class DiscordService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = discord.Client(intents=discord.Intents.all())
    
    async def send_message(self, channel_id: int, content: str) -> None:
        """Send message to Discord channel"""
        channel = self.client.get_channel(channel_id)
        if channel:
            await channel.send(content)
    
    async def get_recent_messages(
        self, 
        channel_id: int, 
        limit: int = 100
    ) -> List[Message]:
        """Get recent messages from channel"""
        channel = self.client.get_channel(channel_id)
        messages = []
        
        if channel:
            async for message in channel.history(limit=limit):
                messages.append(Message.from_discord_message(message))
        
        return messages
    
    async def register_slash_commands(self) -> None:
        """Register slash commands with Discord"""
        # Command registration logic
        pass
```

### 4. AI Pipeline (`ai/pipeline.py`)
```python
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from src.ai.groq_client import GroqClient
from src.ai.chains.news_desk import NewsDeskChain
from src.ai.chains.editor_chief import EditorChiefChain
from src.ai.chains.star_reporter import StarReporterChain
from src.models.message import Message
from typing import List, Dict, Any

class NewsletterPipeline:
    def __init__(self, groq_client: GroqClient):
        self.groq_client = groq_client
        self.news_desk = NewsDeskChain(groq_client)
        self.editor_chief = EditorChiefChain(groq_client)
        self.star_reporter = StarReporterChain(groq_client)
    
    async def generate_newsletter(
        self, 
        messages: List[Message],
        persona: str,
        server_id: str
    ) -> str:
        """Generate newsletter using full RAG/CoT pipeline"""
        
        # Chain A: News Desk - Identify potential stories
        potential_stories = await self.news_desk.identify_stories(messages)
        
        # Chain B: Editor-in-Chief - Select main headline
        headline_story = await self.editor_chief.select_headline(
            potential_stories, persona
        )
        
        # Chain C: Star Reporter - Write final article
        newsletter = await self.star_reporter.write_article(
            headline_story, persona, messages
        )
        
        return newsletter
```

### 5. Repository Pattern (`data/repositories/base.py`)
```python
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TypeVar, Generic
from src.models.base import BaseModel

T = TypeVar('T', bound=BaseModel)

class BaseRepository(ABC, Generic[T]):
    def __init__(self, cosmos_client):
        self.cosmos_client = cosmos_client
    
    @abstractmethod
    async def create(self, item: T) -> T:
        pass
    
    @abstractmethod
    async def get_by_id(self, item_id: str) -> Optional[T]:
        pass
    
    @abstractmethod
    async def update(self, item: T) -> T:
        pass
    
    @abstractmethod
    async def delete(self, item_id: str) -> bool:
        pass
    
    @abstractmethod
    async def list(self, **filters) -> List[T]:
        pass
```

### 6. Dependency Injection (`core/dependencies.py`)
```python
from functools import lru_cache
from src.core.config import Settings
from src.data.cosmos_client import CosmosClient
from src.data.chroma_client import ChromaClient
from src.services.discord_service import DiscordService
from src.services.ai_service import AIService
from src.ai.groq_client import GroqClient

@lru_cache()
def get_settings() -> Settings:
    return Settings()

def get_cosmos_client(settings: Settings = None) -> CosmosClient:
    if settings is None:
        settings = get_settings()
    return CosmosClient(settings.cosmos_connection_string)

def get_chroma_client(settings: Settings = None) -> ChromaClient:
    if settings is None:
        settings = get_settings()
    return ChromaClient(settings.chroma_host, settings.chroma_port)

def get_discord_service(settings: Settings = None) -> DiscordService:
    if settings is None:
        settings = get_settings()
    return DiscordService(settings)

def get_ai_service(settings: Settings = None) -> AIService:
    if settings is None:
        settings = get_settings()
    groq_client = GroqClient(settings.groq_api_key)
    return AIService(groq_client)
```

## Development Dependencies (`requirements.txt`)

```txt
# Azure Functions
azure-functions==1.18.0
azure-functions-worker==1.0.0

# Azure SDK
azure-cosmos==4.5.1
azure-storage-blob==12.19.0
azure-servicebus==7.11.4
azure-keyvault-secrets==4.7.0
azure-monitor-opentelemetry==1.2.0

# Discord
discord.py==2.3.2

# AI/ML
langchain==0.1.0
groq==0.4.1
chromadb==0.4.18
sentence-transformers==2.2.2

# HTTP & Async
httpx==0.25.2
aiohttp==3.9.1

# Data & Validation
pydantic==2.5.0
python-dotenv==1.0.0

# Database
asyncpg==0.29.0

# Logging & Monitoring
structlog==23.2.0
opentelemetry-api==1.21.0
opentelemetry-sdk==1.21.0

# Testing
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-mock==3.12.0
httpx==0.25.2

# Development
black==23.11.0
flake8==6.1.0
mypy==1.7.1
pre-commit==3.6.0
```

## Key Python Features

### 1. **Async/Await Support**
- All I/O operations are async
- Azure Functions with async handlers
- Discord.py async client
- Async database operations

### 2. **Type Hints**
- Full type annotations
- Pydantic models for validation
- mypy for static type checking

### 3. **Dependency Injection**
- Centralized dependency management
- Easy testing with mock dependencies
- Configuration management with Pydantic

### 4. **Error Handling**
- Custom exception classes
- Structured error logging
- Retry logic for external services

### 5. **Testing Strategy**
- pytest for unit/integration tests
- Mock external dependencies
- Async test support with pytest-asyncio
- Test fixtures for reproducible data

This Python structure provides a robust, scalable, and maintainable backend for the Discord bot while leveraging Azure's serverless capabilities and following Python best practices.