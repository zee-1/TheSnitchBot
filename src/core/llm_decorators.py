"""
Decorators for automatic LLM logging and monitoring.
"""

import functools
import time
import asyncio
from typing import Any, Callable, Dict, Optional
import inspect

from src.core.llm_logger import get_llm_logger, log_service_invocation, log_llm_error
from src.core.logging import get_logger

logger = get_logger(__name__)


def log_llm_service(
    service_name: Optional[str] = None,
    include_result: bool = False,
    include_params: bool = True,
    max_result_length: int = 500
):
    """
    Decorator to automatically log service method invocations.
    
    Args:
        service_name: Name of the service (auto-detected if None)
        include_result: Whether to log the result
        include_params: Whether to log parameters
        max_result_length: Maximum length of result to log
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            # Get service name
            actual_service_name = service_name
            if not actual_service_name:
                if args and hasattr(args[0], '__class__'):
                    actual_service_name = args[0].__class__.__name__
                else:
                    actual_service_name = func.__module__.split('.')[-1]
            
            # Get method name
            method_name = func.__name__
            
            # Prepare parameters for logging
            log_params = {}
            if include_params:
                # Get function signature to map args to param names
                sig = inspect.signature(func)
                param_names = list(sig.parameters.keys())
                
                # Map positional args
                for i, arg in enumerate(args[1:], 1):  # Skip self/cls
                    if i < len(param_names):
                        param_name = param_names[i]
                        if isinstance(arg, (str, int, float, bool, list, dict)):
                            log_params[param_name] = arg
                        else:
                            log_params[param_name] = str(type(arg).__name__)
                
                # Add keyword args
                for key, value in kwargs.items():
                    if isinstance(value, (str, int, float, bool, list, dict)):
                        log_params[key] = value
                    else:
                        log_params[key] = str(type(value).__name__)
            
            # Execute function with timing
            start_time = time.time()
            error = None
            result = None
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                error = str(e)
                raise
            finally:
                duration_ms = (time.time() - start_time) * 1000
                
                # Log the service invocation
                try:
                    log_result = None
                    if include_result and result is not None:
                        result_str = str(result)
                        log_result = (result_str[:max_result_length] + "...") if len(result_str) > max_result_length else result_str
                    
                    await log_service_invocation(
                        service_name=actual_service_name,
                        method_name=method_name,
                        parameters=log_params,
                        result=log_result,
                        duration_ms=duration_ms,
                        error=error
                    )
                except Exception as log_error:
                    logger.warning(f"Failed to log service invocation: {log_error}")
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            # For sync functions, we need to handle logging differently
            actual_service_name = service_name
            if not actual_service_name:
                if args and hasattr(args[0], '__class__'):
                    actual_service_name = args[0].__class__.__name__
                else:
                    actual_service_name = func.__module__.split('.')[-1]
            
            method_name = func.__name__
            
            # Prepare parameters
            log_params = {}
            if include_params:
                sig = inspect.signature(func)
                param_names = list(sig.parameters.keys())
                
                for i, arg in enumerate(args[1:], 1):
                    if i < len(param_names):
                        param_name = param_names[i]
                        if isinstance(arg, (str, int, float, bool, list, dict)):
                            log_params[param_name] = arg
                        else:
                            log_params[param_name] = str(type(arg).__name__)
                
                for key, value in kwargs.items():
                    if isinstance(value, (str, int, float, bool, list, dict)):
                        log_params[key] = value
                    else:
                        log_params[key] = str(type(value).__name__)
            
            # Execute with timing
            start_time = time.time()
            error = None
            result = None
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                error = str(e)
                raise
            finally:
                duration_ms = (time.time() - start_time) * 1000
                
                # Schedule async logging
                try:
                    log_result = None
                    if include_result and result is not None:
                        result_str = str(result)
                        log_result = (result_str[:max_result_length] + "...") if len(result_str) > max_result_length else result_str
                    
                    # Use asyncio.create_task to schedule logging
                    loop = None
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            loop.create_task(log_service_invocation(
                                service_name=actual_service_name,
                                method_name=method_name,
                                parameters=log_params,
                                result=log_result,
                                duration_ms=duration_ms,
                                error=error
                            ))
                    except RuntimeError:
                        # No event loop running, skip async logging
                        pass
                except Exception as log_error:
                    logger.warning(f"Failed to schedule service invocation logging: {log_error}")
        
        # Return appropriate wrapper based on whether function is async
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def log_llm_chain(
    chain_name: Optional[str] = None,
    task_type: Optional[str] = None,
    extract_prompt: Optional[Callable] = None,
    extract_response: Optional[Callable] = None
):
    """
    Decorator to automatically log LLM chain steps.
    
    Args:
        chain_name: Name of the chain step (auto-detected if None)
        task_type: Type of task being performed
        extract_prompt: Function to extract prompt from arguments
        extract_response: Function to extract response from result
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # Get chain name
            actual_chain_name = chain_name or func.__name__
            
            start_time = time.time()
            result = None
            error = None
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                error = str(e)
                raise
            finally:
                duration_ms = (time.time() - start_time) * 1000
                
                try:
                    # Extract context from self if available
                    provider = None
                    model = None
                    if args and hasattr(args[0], 'llm_client'):
                        # Try to get current provider/model from client state
                        pass
                    
                    # Extract prompt and response
                    prompt = ""
                    response = ""
                    
                    if extract_prompt:
                        try:
                            prompt = extract_prompt(*args, **kwargs)
                        except:
                            prompt = "Could not extract prompt"
                    
                    if extract_response and result:
                        try:
                            response = extract_response(result)
                        except:
                            response = str(result)[:500]
                    
                    # Log the chain step
                    llm_logger = await get_llm_logger()
                    await llm_logger.log_chain_step(
                        chain_step=actual_chain_name,
                        provider=provider or "unknown",
                        model=model or "unknown",
                        task_type=task_type or "unknown",
                        prompt=prompt,
                        response=response,
                        duration_ms=duration_ms,
                        error_message=error
                    )
                    
                except Exception as log_error:
                    logger.warning(f"Failed to log chain step: {log_error}")
        
        return wrapper if asyncio.iscoroutinefunction(func) else func
    
    return decorator


class LLMContextLogger:
    """
    Context manager for logging LLM operations with detailed context.
    """
    
    def __init__(
        self,
        operation_name: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        task_type: Optional[str] = None,
        server_id: Optional[str] = None,
        user_id: Optional[str] = None,
        command: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.operation_name = operation_name
        self.provider = provider
        self.model = model
        self.task_type = task_type
        self.server_id = server_id
        self.user_id = user_id
        self.command = command
        self.metadata = metadata or {}
        
        self.start_time = None
        self.llm_logger = None
    
    async def __aenter__(self):
        self.start_time = time.time()
        self.llm_logger = await get_llm_logger()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.time() - self.start_time) * 1000
        
        try:
            if exc_type:
                # Log error
                await self.llm_logger.log_error(
                    error_message=str(exc_val),
                    service_name=self.operation_name,
                    provider=self.provider,
                    model=self.model,
                    server_id=self.server_id,
                    user_id=self.user_id,
                    metadata=self.metadata
                )
            else:
                # Log successful performance
                await self.llm_logger.log_performance(
                    operation=self.operation_name,
                    duration_ms=duration_ms,
                    provider=self.provider,
                    model=self.model,
                    metadata={
                        "server_id": self.server_id,
                        "user_id": self.user_id,
                        "command": self.command,
                        **self.metadata
                    }
                )
        except Exception as log_error:
            logger.warning(f"Failed to log LLM context: {log_error}")
    
    async def log_prompt_response(self, prompt: str, response: str, usage_stats: Optional[Dict[str, Any]] = None):
        """Log a prompt and response within this context."""
        if self.llm_logger:
            await self.llm_logger.log_completion(
                provider=self.provider or "unknown",
                model=self.model or "unknown", 
                prompt=prompt,
                response=response,
                duration_ms=(time.time() - self.start_time) * 1000 if self.start_time else 0,
                usage_stats=usage_stats,
                task_type=self.task_type,
                server_id=self.server_id,
                user_id=self.user_id,
                metadata=self.metadata
            )


# Convenience function to create context logger
def llm_context(operation_name: str, **kwargs) -> LLMContextLogger:
    """Create an LLM context logger."""
    return LLMContextLogger(operation_name, **kwargs)