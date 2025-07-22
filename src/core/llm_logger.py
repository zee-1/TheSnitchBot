"""
LLM Chain Logger for monitoring AI service interactions.
Provides comprehensive logging of prompts, responses, and service invocations.
"""

import json
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
import uuid
import logging
from dataclasses import dataclass, asdict
from enum import Enum

from src.core.logging import get_logger
from src.core.config import get_settings

logger = get_logger(__name__)


class LogLevel(str, Enum):
    """Log levels for LLM operations."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class LogType(str, Enum):
    """Types of LLM logs."""
    CHAIN_STEP = "chain_step"
    SERVICE_INVOCATION = "service_invocation"
    COMPLETION = "completion"
    ERROR = "error"
    PERFORMANCE = "performance"


@dataclass
class LLMLogEntry:
    """Structure for LLM log entries."""
    timestamp: str
    session_id: str
    log_type: LogType
    level: LogLevel
    
    # Service information
    provider: Optional[str] = None
    model: Optional[str] = None
    task_type: Optional[str] = None
    chain_step: Optional[str] = None
    
    # Request data
    prompt: Optional[str] = None
    messages: Optional[List[Dict[str, str]]] = None
    parameters: Optional[Dict[str, Any]] = None
    
    # Response data
    response_content: Optional[str] = None
    usage_stats: Optional[Dict[str, Any]] = None
    duration_ms: Optional[float] = None
    
    # Context
    server_id: Optional[str] = None
    user_id: Optional[str] = None
    command: Optional[str] = None
    error_message: Optional[str] = None
    
    # Additional metadata
    metadata: Optional[Dict[str, Any]] = None


class LLMLogger:
    """
    Comprehensive logger for LLM chain operations and service invocations.
    
    Features:
    - JSON Lines format for easy parsing
    - Async file operations to avoid blocking
    - Daily log rotation
    - Debug and chain-specific logging
    - Performance monitoring
    """
    
    def __init__(self):
        self.settings = get_settings()
        
        # Log directories
        self.log_base_dir = Path("logs/llm")
        self.chain_log_dir = self.log_base_dir / "chains"
        self.debug_log_dir = self.log_base_dir / "debug"
        self.performance_log_dir = self.log_base_dir / "performance"
        
        # Create directories
        for dir_path in [self.chain_log_dir, self.debug_log_dir, self.performance_log_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # Current session
        self.session_id = str(uuid.uuid4())
        
        # Write queue for async operations
        self._write_queue = asyncio.Queue()
        self._writer_task = None
        self._shutdown = False
        
        # Buffer for batch writes
        self._log_buffer: List[LLMLogEntry] = []
        self._buffer_size = 10
        self._buffer_flush_interval = 5  # seconds
        
        logger.info(f"LLM Logger initialized with session {self.session_id}")
    
    async def start(self):
        """Start the async log writer."""
        if self._writer_task is None:
            self._writer_task = asyncio.create_task(self._log_writer())
            self._flush_task = asyncio.create_task(self._buffer_flusher())
            logger.info("LLM Logger writer tasks started")
    
    async def stop(self):
        """Stop the async log writer and flush remaining logs."""
        self._shutdown = True
        
        # Flush remaining buffer
        if self._log_buffer:
            await self._flush_buffer()
        
        # Cancel tasks
        if self._writer_task:
            self._writer_task.cancel()
            try:
                await self._writer_task
            except asyncio.CancelledError:
                pass
        
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        
        logger.info("LLM Logger stopped")
    
    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        return datetime.now(timezone.utc).isoformat()
    
    def _get_daily_filename(self, log_type: str) -> Path:
        """Get filename for daily log files."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        
        if log_type == "chain":
            return self.chain_log_dir / f"chains-{date_str}.jsonl"
        elif log_type == "debug":
            return self.debug_log_dir / f"debug-{date_str}.jsonl"
        elif log_type == "performance":
            return self.performance_log_dir / f"performance-{date_str}.jsonl"
        else:
            return self.log_base_dir / f"general-{date_str}.jsonl"
    
    async def _write_log_entry(self, entry: LLMLogEntry, log_file_type: str):
        """Write a single log entry to file."""
        try:
            log_file = self._get_daily_filename(log_file_type)
            
            # Convert to JSON
            log_data = asdict(entry)
            log_line = json.dumps(log_data, default=str, separators=(',', ':'))
            
            # Async write
            async with asyncio.Lock():  # Ensure thread safety
                with open(log_file, 'a', encoding='utf-8') as f:
                    f.write(log_line + '\n')
            
        except Exception as e:
            logger.error(f"Failed to write LLM log entry: {e}")
    
    async def _log_writer(self):
        """Async task to process log writes."""
        while not self._shutdown:
            try:
                # Wait for log entries with timeout
                try:
                    entry_data = await asyncio.wait_for(
                        self._write_queue.get(), timeout=1.0
                    )
                    entry, log_file_type = entry_data
                    await self._write_log_entry(entry, log_file_type)
                except asyncio.TimeoutError:
                    continue
                    
            except Exception as e:
                logger.error(f"Error in LLM log writer: {e}")
    
    async def _buffer_flusher(self):
        """Periodically flush the log buffer."""
        while not self._shutdown:
            await asyncio.sleep(self._buffer_flush_interval)
            if self._log_buffer:
                await self._flush_buffer()
    
    async def _flush_buffer(self):
        """Flush all buffered log entries."""
        if not self._log_buffer:
            return
        
        buffer_copy = self._log_buffer.copy()
        self._log_buffer.clear()
        
        for entry in buffer_copy:
            await self._write_queue.put((entry, "debug"))
    
    async def log_chain_step(
        self,
        chain_step: str,
        provider: str,
        model: str,
        task_type: str,
        prompt: str,
        response: str,
        duration_ms: float,
        usage_stats: Optional[Dict[str, Any]] = None,
        messages: Optional[List[Dict[str, str]]] = None,
        parameters: Optional[Dict[str, Any]] = None,
        server_id: Optional[str] = None,
        user_id: Optional[str] = None,
        command: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log a chain step completion."""
        entry = LLMLogEntry(
            timestamp=self._get_timestamp(),
            session_id=self.session_id,
            log_type=LogType.CHAIN_STEP,
            level=LogLevel.INFO,
            provider=provider,
            model=model,
            task_type=task_type,
            chain_step=chain_step,
            prompt=prompt[:500] + "..." if len(prompt) > 500 else prompt,  # Truncate long prompts
            messages=messages,
            parameters=parameters,
            response_content=response[:1000] + "..." if len(response) > 1000 else response,
            usage_stats=usage_stats,
            duration_ms=duration_ms,
            server_id=server_id,
            user_id=user_id,
            command=command,
            metadata=metadata
        )
        
        await self._write_queue.put((entry, "chain"))
        logger.debug(f"Logged chain step: {chain_step} with {provider}/{model}")
    
    async def log_service_invocation(
        self,
        service_name: str,
        method_name: str,
        parameters: Dict[str, Any],
        result: Optional[Any] = None,
        duration_ms: Optional[float] = None,
        error: Optional[str] = None,
        server_id: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log a service method invocation."""
        level = LogLevel.ERROR if error else LogLevel.DEBUG
        
        entry = LLMLogEntry(
            timestamp=self._get_timestamp(),
            session_id=self.session_id,
            log_type=LogType.SERVICE_INVOCATION,
            level=level,
            chain_step=f"{service_name}.{method_name}",
            parameters=parameters,
            response_content=str(result)[:500] if result else None,
            duration_ms=duration_ms,
            server_id=server_id,
            user_id=user_id,
            error_message=error,
            metadata={
                "service": service_name,
                "method": method_name,
                **(metadata or {})
            }
        )
        
        await self._write_queue.put((entry, "debug"))
        logger.debug(f"Logged service invocation: {service_name}.{method_name}")
    
    async def log_completion(
        self,
        provider: str,
        model: str,
        prompt: str,
        response: str,
        duration_ms: float,
        usage_stats: Optional[Dict[str, Any]] = None,
        task_type: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        server_id: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log a direct LLM completion (not part of a chain)."""
        entry = LLMLogEntry(
            timestamp=self._get_timestamp(),
            session_id=self.session_id,
            log_type=LogType.COMPLETION,
            level=LogLevel.INFO,
            provider=provider,
            model=model,
            task_type=task_type,
            prompt=prompt[:500] + "..." if len(prompt) > 500 else prompt,
            response_content=response[:1000] + "..." if len(response) > 1000 else response,
            usage_stats=usage_stats,
            duration_ms=duration_ms,
            parameters={
                "temperature": temperature,
                "max_tokens": max_tokens
            },
            server_id=server_id,
            user_id=user_id,
            metadata=metadata
        )
        
        await self._write_queue.put((entry, "chain"))
        logger.debug(f"Logged completion: {provider}/{model}")
    
    async def log_error(
        self,
        error_message: str,
        service_name: Optional[str] = None,
        method_name: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        server_id: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log an error in LLM processing."""
        entry = LLMLogEntry(
            timestamp=self._get_timestamp(),
            session_id=self.session_id,
            log_type=LogType.ERROR,
            level=LogLevel.ERROR,
            provider=provider,
            model=model,
            chain_step=f"{service_name}.{method_name}" if service_name and method_name else None,
            parameters=parameters,
            error_message=error_message,
            server_id=server_id,
            user_id=user_id,
            metadata=metadata
        )
        
        await self._write_queue.put((entry, "debug"))
        logger.error(f"Logged LLM error: {error_message}")
    
    async def log_performance(
        self,
        operation: str,
        duration_ms: float,
        tokens_used: Optional[int] = None,
        cost_estimate: Optional[float] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log performance metrics."""
        entry = LLMLogEntry(
            timestamp=self._get_timestamp(),
            session_id=self.session_id,
            log_type=LogType.PERFORMANCE,
            level=LogLevel.INFO,
            provider=provider,
            model=model,
            chain_step=operation,
            duration_ms=duration_ms,
            usage_stats={
                "tokens_used": tokens_used,
                "cost_estimate": cost_estimate
            },
            metadata=metadata
        )
        
        await self._write_queue.put((entry, "performance"))
        logger.debug(f"Logged performance: {operation} took {duration_ms}ms")
    
    async def cleanup_old_logs(self, days_to_keep: int = 30):
        """Clean up log files older than specified days."""
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        for log_dir in [self.chain_log_dir, self.debug_log_dir, self.performance_log_dir]:
            for log_file in log_dir.glob("*.jsonl"):
                try:
                    file_date = datetime.fromtimestamp(log_file.stat().st_mtime)
                    if file_date < cutoff_date:
                        log_file.unlink()
                        logger.info(f"Cleaned up old log file: {log_file}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup log file {log_file}: {e}")
    
    def get_log_stats(self) -> Dict[str, Any]:
        """Get statistics about log files."""
        stats = {
            "session_id": self.session_id,
            "log_directories": {
                "chains": str(self.chain_log_dir),
                "debug": str(self.debug_log_dir),
                "performance": str(self.performance_log_dir)
            },
            "file_counts": {},
            "total_size_mb": 0
        }
        
        total_size = 0
        for log_type, log_dir in [
            ("chains", self.chain_log_dir),
            ("debug", self.debug_log_dir),
            ("performance", self.performance_log_dir)
        ]:
            files = list(log_dir.glob("*.jsonl"))
            stats["file_counts"][log_type] = len(files)
            
            size = sum(f.stat().st_size for f in files)
            total_size += size
        
        stats["total_size_mb"] = round(total_size / (1024 * 1024), 2)
        return stats


# Global LLM logger instance
_llm_logger: Optional[LLMLogger] = None


async def get_llm_logger() -> LLMLogger:
    """Get or create the global LLM logger."""
    global _llm_logger
    
    if _llm_logger is None:
        _llm_logger = LLMLogger()
        await _llm_logger.start()
    
    return _llm_logger


async def close_llm_logger():
    """Close the global LLM logger."""
    global _llm_logger
    
    if _llm_logger is not None:
        await _llm_logger.stop()
        _llm_logger = None


# Convenience functions for common logging operations
async def log_chain_step(chain_step: str, provider: str, model: str, task_type: str, 
                        prompt: str, response: str, duration_ms: float, **kwargs):
    """Convenience function to log chain steps."""
    llm_logger = await get_llm_logger()
    await llm_logger.log_chain_step(
        chain_step, provider, model, task_type, prompt, response, duration_ms, **kwargs
    )


async def log_service_invocation(service_name: str, method_name: str, parameters: Dict[str, Any], 
                               result: Optional[Any] = None, duration_ms: Optional[float] = None, **kwargs):
    """Convenience function to log service invocations."""
    llm_logger = await get_llm_logger()
    await llm_logger.log_service_invocation(
        service_name, method_name, parameters, result, duration_ms, **kwargs
    )


async def log_llm_error(error_message: str, **kwargs):
    """Convenience function to log LLM errors."""
    llm_logger = await get_llm_logger()
    await llm_logger.log_error(error_message, **kwargs)


async def log_performance(operation: str, duration_ms: float, **kwargs):
    """Convenience function to log performance metrics."""
    llm_logger = await get_llm_logger()
    await llm_logger.log_performance(operation, duration_ms, **kwargs)