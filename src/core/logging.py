"""
Logging configuration for The Snitch Discord Bot.
Provides structured logging with proper formatting and levels.
"""

import logging
import logging.config
import sys
from typing import Dict, Any, Optional
from datetime import datetime
import json
import structlog
from pathlib import Path

from src.core.config import Settings


def setup_logging(settings: Settings) -> None:
    """Set up logging configuration for the application."""
    
    # Create logs directory if it doesn't exist
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Configure standard logging
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            },
            "detailed": {
                "format": "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            },
            "json": {
                "()": "src.core.logging.JSONFormatter"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": settings.log_level,
                "formatter": "standard",
                "stream": sys.stdout
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": settings.log_level,
                "formatter": "detailed",
                "filename": "logs/snitch_bot.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5
            },
            "error_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "ERROR",
                "formatter": "json",
                "filename": "logs/errors.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 10
            }
        },
        "loggers": {
            "src": {
                "level": settings.log_level,
                "handlers": ["console", "file", "error_file"],
                "propagate": False
            },
            "azure": {
                "level": "WARNING",
                "handlers": ["file"],
                "propagate": False
            },
            "discord": {
                "level": "INFO",
                "handlers": ["file"],
                "propagate": False
            },
            "urllib3": {
                "level": "WARNING",
                "handlers": ["file"],
                "propagate": False
            },
            "httpx": {
                "level": "WARNING",
                "handlers": ["file"],
                "propagate": False
            }
        },
        "root": {
            "level": "WARNING",
            "handlers": ["console"]
        }
    }
    
    # Apply logging configuration
    logging.config.dictConfig(logging_config)
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer() if settings.environment == "production" else structlog.dev.ConsoleRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in ["name", "msg", "args", "levelname", "levelno", "pathname", 
                          "filename", "module", "lineno", "funcName", "created", 
                          "msecs", "relativeCreated", "thread", "threadName", 
                          "processName", "process", "getMessage", "exc_info", 
                          "exc_text", "stack_info"]:
                log_data[key] = value
        
        return json.dumps(log_data, default=str)


class DiscordLogFilter(logging.Filter):
    """Filter to exclude sensitive Discord information from logs."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter out sensitive information."""
        message = record.getMessage()
        
        # Don't log messages containing tokens or sensitive data
        sensitive_keywords = ["token", "secret", "password", "key"]
        
        for keyword in sensitive_keywords:
            if keyword.lower() in message.lower():
                # Replace sensitive content
                record.msg = "[REDACTED - Contains sensitive information]"
                record.args = ()
                break
        
        return True


class ContextualLogger:
    """Logger with contextual information for better debugging."""
    
    def __init__(self, name: str):
        self.logger = structlog.get_logger(name)
        self.context: Dict[str, Any] = {}
    
    def bind(self, **kwargs) -> "ContextualLogger":
        """Bind context to logger."""
        new_logger = ContextualLogger(self.logger.name)
        new_logger.logger = self.logger.bind(**kwargs)
        new_logger.context = {**self.context, **kwargs}
        return new_logger
    
    def debug(self, message: str, **kwargs) -> None:
        """Log debug message."""
        self.logger.debug(message, **kwargs)
    
    def info(self, message: str, **kwargs) -> None:
        """Log info message."""
        self.logger.info(message, **kwargs)
    
    def warning(self, message: str, **kwargs) -> None:
        """Log warning message."""
        self.logger.warning(message, **kwargs)
    
    def error(self, message: str, **kwargs) -> None:
        """Log error message."""
        self.logger.error(message, **kwargs)
    
    def critical(self, message: str, **kwargs) -> None:
        """Log critical message."""
        self.logger.critical(message, **kwargs)
    
    def exception(self, message: str, **kwargs) -> None:
        """Log exception with traceback."""
        self.logger.exception(message, **kwargs)


def get_logger(name: str) -> ContextualLogger:
    """Get a contextual logger instance."""
    return ContextualLogger(name)


def log_function_call(func):
    """Decorator to log function calls with parameters."""
    def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        logger = logger.bind(function=func.__name__)
        
        # Log function entry
        logger.debug("Function called", args=str(args)[:200], kwargs=str(kwargs)[:200])
        
        try:
            result = func(*args, **kwargs)
            logger.debug("Function completed successfully")
            return result
        except Exception as e:
            logger.error("Function failed", error=str(e), error_type=type(e).__name__)
            raise
    
    return wrapper


def log_async_function_call(func):
    """Decorator to log async function calls with parameters."""
    async def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        logger = logger.bind(function=func.__name__)
        
        # Log function entry
        logger.debug("Async function called", args=str(args)[:200], kwargs=str(kwargs)[:200])
        
        try:
            result = await func(*args, **kwargs)
            logger.debug("Async function completed successfully")
            return result
        except Exception as e:
            logger.error("Async function failed", error=str(e), error_type=type(e).__name__)
            raise
    
    return wrapper


class LoggingMixin:
    """Mixin class to add logging capabilities to any class."""
    
    @property
    def logger(self) -> ContextualLogger:
        """Get logger for this class."""
        if not hasattr(self, '_logger'):
            self._logger = get_logger(self.__class__.__module__).bind(
                class_name=self.__class__.__name__
            )
        return self._logger


def setup_azure_function_logging() -> None:
    """Set up logging specifically for Azure Functions."""
    # Azure Functions have their own logging system
    # We need to integrate with it properly
    
    import azure.functions as func
    
    # Create a custom handler that works with Azure Functions
    class AzureFunctionHandler(logging.Handler):
        def emit(self, record):
            # Azure Functions logging integration
            pass
    
    # Add the handler to our loggers
    azure_handler = AzureFunctionHandler()
    azure_handler.setLevel(logging.INFO)
    
    # Get the root logger and add our handler
    root_logger = logging.getLogger("src")
    root_logger.addHandler(azure_handler)


def log_performance(operation: str):
    """Decorator to log operation performance."""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            logger = logger.bind(operation=operation, function=func.__name__)
            
            start_time = datetime.now()
            logger.debug("Operation started")
            
            try:
                result = await func(*args, **kwargs)
                duration = (datetime.now() - start_time).total_seconds()
                logger.info("Operation completed", duration_seconds=duration)
                return result
            except Exception as e:
                duration = (datetime.now() - start_time).total_seconds()
                logger.error("Operation failed", duration_seconds=duration, error=str(e))
                raise
        
        def sync_wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            logger = logger.bind(operation=operation, function=func.__name__)
            
            start_time = datetime.now()
            logger.debug("Operation started")
            
            try:
                result = func(*args, **kwargs)
                duration = (datetime.now() - start_time).total_seconds()
                logger.info("Operation completed", duration_seconds=duration)
                return result
            except Exception as e:
                duration = (datetime.now() - start_time).total_seconds()
                logger.error("Operation failed", duration_seconds=duration, error=str(e))
                raise
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# Security logging functions
def log_security_event(event_type: str, user_id: str, server_id: str, details: Dict[str, Any]) -> None:
    """Log security-related events."""
    security_logger = get_logger("security")
    security_logger.warning(
        "Security event detected",
        event_type=event_type,
        user_id=user_id,
        server_id=server_id,
        details=details
    )


def log_command_usage(command: str, user_id: str, server_id: str, success: bool, **kwargs) -> None:
    """Log command usage for analytics."""
    command_logger = get_logger("commands")
    command_logger.info(
        "Command executed",
        command=command,
        user_id=user_id,
        server_id=server_id,
        success=success,
        **kwargs
    )


def log_api_call(service: str, endpoint: str, method: str, status_code: int, duration_ms: float) -> None:
    """Log external API calls."""
    api_logger = get_logger("api")
    api_logger.info(
        "API call made",
        service=service,
        endpoint=endpoint,
        method=method,
        status_code=status_code,
        duration_ms=duration_ms
    )