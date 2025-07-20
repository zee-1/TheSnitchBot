"""
Configuration management for The Snitch Discord Bot.
Handles environment variables and application settings.
"""

from pydantic_settings import BaseSettings
from pydantic import Field, field_validator, ConfigDict
from typing import Optional, List
import os
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Discord Configuration
    discord_token: str = Field(..., env="DISCORD_TOKEN")
    discord_client_id: str = Field(..., env="DISCORD_CLIENT_ID")
    discord_client_secret: str = Field(..., env="DISCORD_CLIENT_SECRET")
    
    # Azure Configuration
    azure_subscription_id: str = Field(..., env="AZURE_SUBSCRIPTION_ID")
    azure_tenant_id: str = Field(..., env="AZURE_TENANT_ID")
    azure_client_id: str = Field(..., env="AZURE_CLIENT_ID")
    azure_client_secret: str = Field(..., env="AZURE_CLIENT_SECRET")
    
    # Azure Cosmos DB
    cosmos_connection_string: str = Field(..., env="COSMOS_CONNECTION_STRING")
    cosmos_database_name: str = Field("snitch_bot_db", env="COSMOS_DATABASE_NAME")
    # 2-container setup for free tier optimization
    cosmos_container_operational: str = Field("operational_data", env="COSMOS_CONTAINER_OPERATIONAL")  # servers + tips
    cosmos_container_content: str = Field("content_data", env="COSMOS_CONTAINER_CONTENT")  # newsletters
    # Legacy fields for backward compatibility
    cosmos_container_servers: str = Field("operational_data", env="COSMOS_CONTAINER_SERVERS")
    cosmos_container_tips: str = Field("operational_data", env="COSMOS_CONTAINER_TIPS")
    cosmos_container_newsletters: str = Field("content_data", env="COSMOS_CONTAINER_NEWSLETTERS")
    cosmos_container_messages: str = Field("operational_data", env="COSMOS_CONTAINER_MESSAGES")
    
    # Azure Blob Storage
    blob_connection_string: str = Field(..., env="BLOB_CONNECTION_STRING")
    blob_container_name: str = Field("snitch-files", env="BLOB_CONTAINER_NAME")
    
    # Azure Service Bus
    service_bus_connection_string: str = Field(..., env="SERVICE_BUS_CONNECTION_STRING")
    service_bus_queue_messages: str = Field("message-processing", env="SERVICE_BUS_QUEUE_MESSAGES")
    service_bus_topic_events: str = Field("bot-events", env="SERVICE_BUS_TOPIC_EVENTS")
    
    # Azure Key Vault
    key_vault_url: str = Field(..., env="KEY_VAULT_URL")
    
    # AI Services
    groq_api_key: str = Field(..., env="GROQ_API_KEY")
    groq_model_name: str = Field("mixtral-8x7b-32768", env="GROQ_MODEL_NAME")
    
    # ChromaDB Configuration
    chroma_host: str = Field("localhost", env="CHROMA_HOST")
    chroma_port: int = Field(8000, env="CHROMA_PORT")
    chroma_persist_directory: str = Field("./chroma_data", env="CHROMA_PERSIST_DIRECTORY")
    
    # Application Settings
    environment: str = Field("development", env="ENVIRONMENT")
    log_level: str = Field("INFO", env="LOG_LEVEL")
    debug: bool = Field(True, env="DEBUG")
    
    # Newsletter Configuration
    default_newsletter_time: str = Field("09:00", env="DEFAULT_NEWSLETTER_TIME")
    default_timezone: str = Field("UTC", env="DEFAULT_TIMEZONE")
    max_messages_per_analysis: int = Field(1000, env="MAX_MESSAGES_PER_ANALYSIS")
    
    # Rate Limiting
    rate_limit_commands_per_minute: int = Field(10, env="RATE_LIMIT_COMMANDS_PER_MINUTE")
    rate_limit_newsletter_per_day: int = Field(1, env="RATE_LIMIT_NEWSLETTER_PER_DAY")
    
    # Security
    secret_key: str = Field(..., env="SECRET_KEY")
    encryption_key: str = Field(..., env="ENCRYPTION_KEY")
    
    # Monitoring
    azure_monitor_connection_string: Optional[str] = Field(None, env="AZURE_MONITOR_CONNECTION_STRING")
    application_insights_instrumentation_key: Optional[str] = Field(None, env="APPLICATION_INSIGHTS_INSTRUMENTATION_KEY")
    
    # External Services
    cloudflare_api_token: Optional[str] = Field(None, env="CLOUDFLARE_API_TOKEN")
    cloudflare_zone_id: Optional[str] = Field(None, env="CLOUDFLARE_ZONE_ID")
    
    # Development Settings
    enable_mock_services: bool = Field(False, env="ENABLE_MOCK_SERVICES")
    mock_ai_responses: bool = Field(False, env="MOCK_AI_RESPONSES")
    skip_discord_verification: bool = Field(False, env="SKIP_DISCORD_VERIFICATION")
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v):
        """Validate log level is one of the accepted values."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v.upper()
    
    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v):
        """Validate environment is one of the accepted values."""
        valid_envs = ["development", "staging", "production"]
        if v.lower() not in valid_envs:
            raise ValueError(f"Environment must be one of {valid_envs}")
        return v.lower()
    
    @field_validator("chroma_persist_directory")
    @classmethod
    def validate_chroma_directory(cls, v):
        """Ensure ChromaDB persist directory exists."""
        path = Path(v)
        path.mkdir(parents=True, exist_ok=True)
        return str(path)
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"
    
    @property
    def chroma_url(self) -> str:
        """Get ChromaDB URL."""
        return f"http://{self.chroma_host}:{self.chroma_port}"
    
    @property
    def CHROMA_DB_PATH(self) -> str:
        """Get ChromaDB persistence path (alias for embedding service)."""
        return self.chroma_persist_directory
    
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        validate_assignment=True,
        # Note: secrets handling in Pydantic v2 is done differently
    )


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings instance."""
    return settings


def get_config() -> Settings:
    """Get application settings instance (alias for get_settings for backward compatibility)."""
    return settings


def reload_settings() -> Settings:
    """Reload settings from environment (useful for testing)."""
    global settings
    settings = Settings()
    return settings