"""
Base classes for newsletter pipeline chains.
Provides common functionality for newsletter generation chains.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from src.ai.llm_client import LLMClient, TaskType
from src.core.logging import get_logger


class BaseNewsletterChain(ABC):
    """Base class for newsletter pipeline chains."""
    
    # Each subclass should override this to specify their task type
    task_type: TaskType = TaskType.ANALYSIS
    
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
        self.logger = get_logger(self.__class__.__name__)
    
    async def _safe_ai_completion(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        fallback_response: Optional[str] = None
    ) -> str:
        """Safely get AI completion with error handling."""
        try:
            response = await self.llm_client.simple_completion(
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                task_type=self.task_type  # Use the chain's task type
            )
            return response.strip()
        except Exception as e:
            self.logger.error(f"AI completion failed: {e}")
            if fallback_response:
                return fallback_response
            raise

    async def _safe_ai_chat_completion(
        self,
        messages: list,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        fallback_response: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Safely get chat completion with error handling."""
        try:
            response = await self.llm_client.chat_completion(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                task_type=self.task_type  # Use the chain's task type
            )
            return response
        except Exception as e:
            self.logger.error(f"AI chat completion failed: {e}")
            if fallback_response:
                return fallback_response
            raise