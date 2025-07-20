"""
Custom exceptions for The Snitch Discord Bot.
Defines application-specific exception classes for better error handling.
"""

from typing import Optional, Dict, Any


class SnitchBotError(Exception):
    """Base exception class for The Snitch Bot."""
    
    def __init__(self, message: str, error_code: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging/serialization."""
        return {
            "error_type": self.__class__.__name__,
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details
        }


# Configuration Exceptions
class ConfigurationError(SnitchBotError):
    """Raised when there are configuration issues."""
    pass


class MissingConfigurationError(ConfigurationError):
    """Raised when required configuration is missing."""
    pass


class InvalidConfigurationError(ConfigurationError):
    """Raised when configuration values are invalid."""
    pass


# Bot Lifecycle Exceptions
class BotInitializationError(SnitchBotError):
    """Raised when the bot fails to initialize properly."""
    pass


class MessageProcessingError(SnitchBotError):
    """Raised when there's an error processing Discord messages."""
    pass


# Database Exceptions
class DatabaseError(SnitchBotError):
    """Base exception for database-related errors."""
    pass


class DatabaseConnectionError(DatabaseError):
    """Raised when database connection fails."""
    pass


class DatabaseOperationError(DatabaseError):
    """Raised when database operations fail."""
    pass


class EntityNotFoundError(DatabaseError):
    """Raised when requested entity is not found."""
    
    def __init__(self, entity_type: str, entity_id: str, **kwargs):
        message = f"{entity_type} with ID '{entity_id}' not found"
        super().__init__(message, **kwargs)
        self.entity_type = entity_type
        self.entity_id = entity_id


class EntityAlreadyExistsError(DatabaseError):
    """Raised when trying to create an entity that already exists."""
    
    def __init__(self, entity_type: str, entity_id: str, **kwargs):
        message = f"{entity_type} with ID '{entity_id}' already exists"
        super().__init__(message, **kwargs)
        self.entity_type = entity_type
        self.entity_id = entity_id


# Discord API Exceptions
class DiscordError(SnitchBotError):
    """Base exception for Discord-related errors."""
    pass


class DiscordAPIError(DiscordError):
    """Raised when Discord API calls fail."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.status_code = status_code


class DiscordPermissionError(DiscordError):
    """Raised when bot lacks required Discord permissions."""
    
    def __init__(self, permission: str, server_id: str, **kwargs):
        message = f"Missing permission '{permission}' in server {server_id}"
        super().__init__(message, **kwargs)
        self.permission = permission
        self.server_id = server_id


class DiscordServerNotFoundError(DiscordError):
    """Raised when Discord server is not found."""
    
    def __init__(self, server_id: str, **kwargs):
        message = f"Discord server '{server_id}' not found"
        super().__init__(message, **kwargs)
        self.server_id = server_id


class DiscordChannelNotFoundError(DiscordError):
    """Raised when Discord channel is not found."""
    
    def __init__(self, channel_id: str, **kwargs):
        message = f"Discord channel '{channel_id}' not found"
        super().__init__(message, **kwargs)
        self.channel_id = channel_id


class DiscordUserNotFoundError(DiscordError):
    """Raised when Discord user is not found."""
    
    def __init__(self, user_id: str, **kwargs):
        message = f"Discord user '{user_id}' not found"
        super().__init__(message, **kwargs)
        self.user_id = user_id


# AI Service Exceptions
class AIServiceError(SnitchBotError):
    """Base exception for AI service errors."""
    pass


class AIProviderError(AIServiceError):
    """Raised when AI provider (Groq) returns an error."""
    
    def __init__(self, provider: str, message: str, **kwargs):
        super().__init__(message, **kwargs)
        self.provider = provider


class AIQuotaExceededError(AIServiceError):
    """Raised when AI service quota is exceeded."""
    pass


class AIModelNotAvailableError(AIServiceError):
    """Raised when requested AI model is not available."""
    
    def __init__(self, model_name: str, **kwargs):
        message = f"AI model '{model_name}' is not available"
        super().__init__(message, **kwargs)
        self.model_name = model_name


class AIResponseParsingError(AIServiceError):
    """Raised when AI response cannot be parsed."""
    pass


# Newsletter Generation Exceptions
class NewsletterError(SnitchBotError):
    """Base exception for newsletter-related errors."""
    pass


class NewsletterGenerationError(NewsletterError):
    """Raised when newsletter generation fails."""
    pass


class NewsletterDeliveryError(NewsletterError):
    """Raised when newsletter delivery fails."""
    
    def __init__(self, newsletter_id: str, channel_id: str, reason: str, **kwargs):
        message = f"Failed to deliver newsletter {newsletter_id} to channel {channel_id}: {reason}"
        super().__init__(message, **kwargs)
        self.newsletter_id = newsletter_id
        self.channel_id = channel_id
        self.reason = reason


class InsufficientContentError(NewsletterError):
    """Raised when there's not enough content to generate a newsletter."""
    
    def __init__(self, server_id: str, message_count: int, **kwargs):
        message = f"Insufficient content for newsletter in server {server_id}: only {message_count} messages"
        super().__init__(message, **kwargs)
        self.server_id = server_id
        self.message_count = message_count


# Command Processing Exceptions
class CommandError(SnitchBotError):
    """Base exception for command processing errors."""
    pass


class CommandPermissionError(CommandError):
    """Raised when user lacks permission to execute command."""
    
    def __init__(self, command: str, user_id: str, server_id: str, **kwargs):
        message = f"User {user_id} lacks permission to execute '{command}' in server {server_id}"
        super().__init__(message, **kwargs)
        self.command = command
        self.user_id = user_id
        self.server_id = server_id


class CommandCooldownError(CommandError):
    """Raised when command is on cooldown."""
    
    def __init__(self, command: str, remaining_seconds: int, **kwargs):
        message = f"Command '{command}' is on cooldown for {remaining_seconds} seconds"
        super().__init__(message, **kwargs)
        self.command = command
        self.remaining_seconds = remaining_seconds


class InvalidCommandArgumentError(CommandError):
    """Raised when command arguments are invalid."""
    
    def __init__(self, command: str, argument: str, reason: str, **kwargs):
        message = f"Invalid argument '{argument}' for command '{command}': {reason}"
        super().__init__(message, **kwargs)
        self.command = command
        self.argument = argument
        self.reason = reason


# Rate Limiting Exceptions
class RateLimitError(SnitchBotError):
    """Raised when rate limits are exceeded."""
    
    def __init__(self, operation: str, limit: int, window_seconds: int, **kwargs):
        message = f"Rate limit exceeded for '{operation}': {limit} operations per {window_seconds} seconds"
        super().__init__(message, **kwargs)
        self.operation = operation
        self.limit = limit
        self.window_seconds = window_seconds


# Vector Database Exceptions
class VectorDatabaseError(SnitchBotError):
    """Base exception for vector database (ChromaDB) errors."""
    pass


class VectorDatabaseConnectionError(VectorDatabaseError):
    """Raised when vector database connection fails."""
    pass


class VectorCollectionNotFoundError(VectorDatabaseError):
    """Raised when vector collection is not found."""
    
    def __init__(self, collection_name: str, **kwargs):
        message = f"Vector collection '{collection_name}' not found"
        super().__init__(message, **kwargs)
        self.collection_name = collection_name


class EmbeddingGenerationError(VectorDatabaseError):
    """Raised when text embedding generation fails."""
    pass


# Tip Processing Exceptions
class TipProcessingError(SnitchBotError):
    """Base exception for tip processing errors."""
    pass


class TipValidationError(TipProcessingError):
    """Raised when tip content validation fails."""
    pass


class TipDuplicateError(TipProcessingError):
    """Raised when duplicate tip is submitted."""
    
    def __init__(self, tip_content_hash: str, **kwargs):
        message = f"Duplicate tip detected with hash {tip_content_hash}"
        super().__init__(message, **kwargs)
        self.tip_content_hash = tip_content_hash


# Security Exceptions
class SecurityError(SnitchBotError):
    """Base exception for security-related errors."""
    pass


class AuthenticationError(SecurityError):
    """Raised when authentication fails."""
    pass


class AuthorizationError(SecurityError):
    """Raised when authorization fails."""
    
    def __init__(self, user_id: str, resource: str, action: str, **kwargs):
        message = f"User {user_id} not authorized to {action} on {resource}"
        super().__init__(message, **kwargs)
        self.user_id = user_id
        self.resource = resource
        self.action = action


class InvalidTokenError(SecurityError):
    """Raised when security token is invalid."""
    pass


# External Service Exceptions
class ExternalServiceError(SnitchBotError):
    """Base exception for external service errors."""
    pass


class CloudflareError(ExternalServiceError):
    """Raised when Cloudflare API errors occur."""
    pass


class AzureServiceError(ExternalServiceError):
    """Raised when Azure service errors occur."""
    
    def __init__(self, service: str, operation: str, message: str, **kwargs):
        full_message = f"Azure {service} error during {operation}: {message}"
        super().__init__(full_message, **kwargs)
        self.service = service
        self.operation = operation


# Validation Exceptions
class ValidationError(SnitchBotError):
    """Raised when data validation fails."""
    
    def __init__(self, field: str, value: Any, reason: str, **kwargs):
        message = f"Validation failed for field '{field}' with value '{value}': {reason}"
        super().__init__(message, **kwargs)
        self.field = field
        self.value = value
        self.reason = reason


# Retry Exceptions
class RetryableError(SnitchBotError):
    """Base class for errors that can be retried."""
    
    def __init__(self, message: str, max_retries: int = 3, **kwargs):
        super().__init__(message, **kwargs)
        self.max_retries = max_retries


class NonRetryableError(SnitchBotError):
    """Base class for errors that should not be retried."""
    pass


# Utility functions for exception handling
def is_retryable_error(error: Exception) -> bool:
    """Check if an error is retryable."""
    retryable_types = (
        DatabaseConnectionError,
        DiscordAPIError,
        AIProviderError,
        VectorDatabaseConnectionError,
        ExternalServiceError,
        RetryableError
    )
    
    return isinstance(error, retryable_types)


def get_error_category(error: Exception) -> str:
    """Get error category for logging and monitoring."""
    if isinstance(error, DatabaseError):
        return "database"
    elif isinstance(error, DiscordError):
        return "discord"
    elif isinstance(error, AIServiceError):
        return "ai_service"
    elif isinstance(error, NewsletterError):
        return "newsletter"
    elif isinstance(error, CommandError):
        return "command"
    elif isinstance(error, SecurityError):
        return "security"
    elif isinstance(error, ExternalServiceError):
        return "external_service"
    elif isinstance(error, ValidationError):
        return "validation"
    else:
        return "unknown"


def create_error_response(error: SnitchBotError) -> Dict[str, Any]:
    """Create standardized error response."""
    return {
        "success": False,
        "error": {
            "type": error.__class__.__name__,
            "code": error.error_code,
            "message": error.message,
            "category": get_error_category(error),
            "retryable": is_retryable_error(error),
            "details": error.details
        }
    }