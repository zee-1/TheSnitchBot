"""
Retry utility functions for The Snitch Discord Bot.
Provides decorators and functions for handling retries with exponential backoff.
"""

import asyncio
import functools
import random
import time
from typing import Callable, Type, Union, Tuple, Any, Optional
import logging

from src.core.exceptions import is_retryable_error

logger = logging.getLogger(__name__)


def exponential_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None
):
    """
    Decorator for exponential backoff retry logic.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential calculation
        jitter: Whether to add random jitter to delays
        retryable_exceptions: Tuple of exception types that should trigger retries
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    # Check if this exception should trigger a retry
                    if retryable_exceptions and not isinstance(e, retryable_exceptions):
                        raise
                    
                    if not retryable_exceptions and not is_retryable_error(e):
                        raise
                    
                    # Don't retry on the last attempt
                    if attempt == max_retries:
                        break
                    
                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (exponential_base ** attempt), max_delay)
                    
                    # Add jitter to prevent thundering herd
                    if jitter:
                        delay = delay * (0.5 + random.random() * 0.5)
                    
                    logger.warning(
                        f"Attempt {attempt + 1} failed, retrying in {delay:.2f}s",
                        exc_info=e,
                        extra={
                            "function": func.__name__,
                            "attempt": attempt + 1,
                            "max_retries": max_retries,
                            "delay": delay,
                            "error": str(e)
                        }
                    )
                    
                    await asyncio.sleep(delay)
            
            # All retries exhausted
            logger.error(
                f"All {max_retries} retry attempts failed for {func.__name__}",
                exc_info=last_exception
            )
            raise last_exception
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    # Check if this exception should trigger a retry
                    if retryable_exceptions and not isinstance(e, retryable_exceptions):
                        raise
                    
                    if not retryable_exceptions and not is_retryable_error(e):
                        raise
                    
                    # Don't retry on the last attempt
                    if attempt == max_retries:
                        break
                    
                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (exponential_base ** attempt), max_delay)
                    
                    # Add jitter to prevent thundering herd
                    if jitter:
                        delay = delay * (0.5 + random.random() * 0.5)
                    
                    logger.warning(
                        f"Attempt {attempt + 1} failed, retrying in {delay:.2f}s",
                        exc_info=e,
                        extra={
                            "function": func.__name__,
                            "attempt": attempt + 1,
                            "max_retries": max_retries,
                            "delay": delay,
                            "error": str(e)
                        }
                    )
                    
                    time.sleep(delay)
            
            # All retries exhausted
            logger.error(
                f"All {max_retries} retry attempts failed for {func.__name__}",
                exc_info=last_exception
            )
            raise last_exception
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class RetryConfig:
    """Configuration for retry behavior."""
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number."""
        delay = min(self.base_delay * (self.exponential_base ** attempt), self.max_delay)
        
        if self.jitter:
            delay = delay * (0.5 + random.random() * 0.5)
        
        return delay


async def retry_async(
    func: Callable,
    config: RetryConfig,
    *args,
    **kwargs
) -> Any:
    """
    Retry an async function with the given configuration.
    
    Args:
        func: The async function to retry
        config: Retry configuration
        *args: Arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function
    
    Returns:
        The result of the function call
    
    Raises:
        The last exception encountered if all retries fail
    """
    last_exception = None
    
    for attempt in range(config.max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            
            # Check if this exception should trigger a retry
            if config.retryable_exceptions and not isinstance(e, config.retryable_exceptions):
                raise
            
            if not config.retryable_exceptions and not is_retryable_error(e):
                raise
            
            # Don't retry on the last attempt
            if attempt == config.max_retries:
                break
            
            delay = config.calculate_delay(attempt)
            
            logger.warning(
                f"Retry attempt {attempt + 1} failed, retrying in {delay:.2f}s",
                extra={
                    "function": func.__name__ if hasattr(func, '__name__') else str(func),
                    "attempt": attempt + 1,
                    "max_retries": config.max_retries,
                    "delay": delay,
                    "error": str(e)
                }
            )
            
            await asyncio.sleep(delay)
    
    logger.error(
        f"All {config.max_retries} retry attempts failed",
        exc_info=last_exception
    )
    raise last_exception


def retry_sync(
    func: Callable,
    config: RetryConfig,
    *args,
    **kwargs
) -> Any:
    """
    Retry a sync function with the given configuration.
    
    Args:
        func: The function to retry
        config: Retry configuration
        *args: Arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function
    
    Returns:
        The result of the function call
    
    Raises:
        The last exception encountered if all retries fail
    """
    last_exception = None
    
    for attempt in range(config.max_retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            
            # Check if this exception should trigger a retry
            if config.retryable_exceptions and not isinstance(e, config.retryable_exceptions):
                raise
            
            if not config.retryable_exceptions and not is_retryable_error(e):
                raise
            
            # Don't retry on the last attempt
            if attempt == config.max_retries:
                break
            
            delay = config.calculate_delay(attempt)
            
            logger.warning(
                f"Retry attempt {attempt + 1} failed, retrying in {delay:.2f}s",
                extra={
                    "function": func.__name__ if hasattr(func, '__name__') else str(func),
                    "attempt": attempt + 1,
                    "max_retries": config.max_retries,
                    "delay": delay,
                    "error": str(e)
                }
            )
            
            time.sleep(delay)
    
    logger.error(
        f"All {config.max_retries} retry attempts failed",
        exc_info=last_exception
    )
    raise last_exception


# Predefined retry configurations for common scenarios
DATABASE_RETRY_CONFIG = RetryConfig(
    max_retries=3,
    base_delay=1.0,
    max_delay=30.0,
    exponential_base=2.0,
    jitter=True
)

API_RETRY_CONFIG = RetryConfig(
    max_retries=5,
    base_delay=0.5,
    max_delay=60.0,
    exponential_base=2.0,
    jitter=True
)

QUICK_RETRY_CONFIG = RetryConfig(
    max_retries=2,
    base_delay=0.1,
    max_delay=1.0,
    exponential_base=2.0,
    jitter=False
)

AGGRESSIVE_RETRY_CONFIG = RetryConfig(
    max_retries=10,
    base_delay=0.1,
    max_delay=120.0,
    exponential_base=1.5,
    jitter=True
)


# Convenience decorators with predefined configurations
def database_retry(func: Callable) -> Callable:
    """Decorator for database operations with standard retry config."""
    return exponential_backoff(
        max_retries=DATABASE_RETRY_CONFIG.max_retries,
        base_delay=DATABASE_RETRY_CONFIG.base_delay,
        max_delay=DATABASE_RETRY_CONFIG.max_delay,
        exponential_base=DATABASE_RETRY_CONFIG.exponential_base,
        jitter=DATABASE_RETRY_CONFIG.jitter
    )(func)


def api_retry(func: Callable) -> Callable:
    """Decorator for API operations with standard retry config."""
    return exponential_backoff(
        max_retries=API_RETRY_CONFIG.max_retries,
        base_delay=API_RETRY_CONFIG.base_delay,
        max_delay=API_RETRY_CONFIG.max_delay,
        exponential_base=API_RETRY_CONFIG.exponential_base,
        jitter=API_RETRY_CONFIG.jitter
    )(func)


def quick_retry(func: Callable) -> Callable:
    """Decorator for quick operations with minimal retry."""
    return exponential_backoff(
        max_retries=QUICK_RETRY_CONFIG.max_retries,
        base_delay=QUICK_RETRY_CONFIG.base_delay,
        max_delay=QUICK_RETRY_CONFIG.max_delay,
        exponential_base=QUICK_RETRY_CONFIG.exponential_base,
        jitter=QUICK_RETRY_CONFIG.jitter
    )(func)