"""
Groq API client for The Snitch Discord Bot.
Provides fast AI inference using Groq's API.
"""

import asyncio
from typing import Dict, Any, List, Optional, Union
import json
import httpx
from datetime import datetime
import logging

from src.core.config import Settings
from src.core.exceptions import AIServiceError, AIProviderError, AIQuotaExceededError, AIModelNotAvailableError
from src.core.logging import get_logger, log_api_call
from src.utils.retry import api_retry

logger = get_logger(__name__)


class GroqClient:
    """Client for interacting with Groq API."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.api_key = settings.groq_api_key
        self.model_name = settings.groq_model_name
        self.base_url = "https://api.groq.com/openai/v1"
        
        # HTTP client with proper timeouts
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0),  # 60 second timeout
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
        )
        
        # Rate limiting
        self._request_count = 0
        self._last_reset = datetime.now()
        self._max_requests_per_minute = 30  # Conservative limit
    
    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()
    
    def _check_rate_limit(self) -> None:
        """Check if we're within rate limits."""
        now = datetime.now()
        
        # Reset counter every minute
        if (now - self._last_reset).total_seconds() >= 60:
            self._request_count = 0
            self._last_reset = now
        
        if self._request_count >= self._max_requests_per_minute:
            raise AIProviderError("groq", "Rate limit exceeded")
        
        self._request_count += 1
    
    @api_retry
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        top_p: float = 1.0,
        stream: bool = False,
        stop: Optional[Union[str, List[str]]] = None
    ) -> Dict[str, Any]:
        """
        Create a chat completion using Groq API.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            model: Model to use (defaults to configured model)
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens in response
            top_p: Nucleus sampling parameter
            stream: Whether to stream the response
            stop: Stop sequences
            
        Returns:
            Chat completion response
        """
        start_time = datetime.now()
        
        try:
            self._check_rate_limit()
            
            # Prepare request payload
            payload = {
                "model": model or self.model_name,
                "messages": messages,
                "temperature": temperature,
                "top_p": top_p,
                "stream": stream
            }
            
            if max_tokens:
                payload["max_tokens"] = max_tokens
            
            if stop:
                payload["stop"] = stop
            
            # Make API request
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                json=payload
            )
            
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            
            # Log API call
            log_api_call(
                service="groq",
                endpoint="/chat/completions",
                method="POST",
                status_code=response.status_code,
                duration_ms=duration_ms
            )
            
            # Handle response
            if response.status_code == 200:
                result = response.json()
                
                logger.info(
                    "Groq chat completion successful",
                    model=payload["model"],
                    prompt_tokens=result.get("usage", {}).get("prompt_tokens", 0),
                    completion_tokens=result.get("usage", {}).get("completion_tokens", 0),
                    duration_ms=duration_ms
                )
                
                return result
            
            elif response.status_code == 429:
                logger.warning("Groq rate limit exceeded")
                raise AIQuotaExceededError("Groq API rate limit exceeded")
            
            elif response.status_code == 401:
                logger.error("Groq authentication failed")
                raise AIProviderError("groq", "Authentication failed - check API key")
            
            elif response.status_code == 404:
                logger.error(f"Groq model not found: {payload['model']}")
                raise AIModelNotAvailableError(payload["model"])
            
            else:
                error_text = response.text
                logger.error(f"Groq API error: {response.status_code} - {error_text}")
                raise AIProviderError("groq", f"API error: {response.status_code}")
        
        except httpx.TimeoutException:
            logger.error("Groq API timeout")
            raise AIProviderError("groq", "Request timeout")
        
        except httpx.RequestError as e:
            logger.error(f"Groq API request error: {e}")
            raise AIProviderError("groq", f"Request error: {e}")
        
        except Exception as e:
            logger.error(f"Unexpected error in Groq chat completion: {e}")
            raise AIServiceError(f"Unexpected error: {e}")
    
    async def simple_completion(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Simple text completion using chat format.
        
        Args:
            prompt: The input prompt
            model: Model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            
        Returns:
            Generated text response
        """
        messages = [{"role": "user", "content": prompt}]
        
        response = await self.chat_completion(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        return response["choices"][0]["message"]["content"]
    
    async def conversation_completion(
        self,
        conversation: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Complete a conversation with optional system prompt.
        
        Args:
            conversation: List of conversation messages
            system_prompt: Optional system prompt to prepend
            model: Model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            
        Returns:
            AI response to the conversation
        """
        messages = []
        
        # Add system prompt if provided
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # Add conversation history
        messages.extend(conversation)
        
        response = await self.chat_completion(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        return response["choices"][0]["message"]["content"]
    
    async def analyze_content(
        self,
        content: str,
        analysis_type: str,
        context: Optional[str] = None,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze content for specific attributes.
        
        Args:
            content: Content to analyze
            analysis_type: Type of analysis (sentiment, controversy, etc.)
            context: Optional context for the analysis
            model: Model to use
            
        Returns:
            Analysis results as dictionary
        """
        
        analysis_prompts = {
            "sentiment": f"""
            Analyze the sentiment of the following text. Return a JSON object with:
            - sentiment: "positive", "negative", or "neutral"
            - score: float between -1 (very negative) and 1 (very positive)
            - confidence: float between 0 and 1
            
            Text: "{content}"
            
            Return only valid JSON:
            """,
            
            "controversy": f"""
            Analyze how controversial or debate-inducing this text might be. Return a JSON object with:
            - controversy_score: float between 0 (not controversial) and 1 (very controversial)
            - factors: list of strings explaining what makes it controversial
            - confidence: float between 0 and 1
            
            Text: "{content}"
            
            Return only valid JSON:
            """,
            
            "toxicity": f"""
            Analyze the toxicity level of this text. Return a JSON object with:
            - toxicity_score: float between 0 (not toxic) and 1 (very toxic)
            - categories: list of toxicity categories found (if any)
            - confidence: float between 0 and 1
            
            Text: "{content}"
            
            Return only valid JSON:
            """,
            
            "engagement": f"""
            Analyze how engaging or interesting this text is for social media. Return a JSON object with:
            - engagement_score: float between 0 (boring) and 1 (very engaging)
            - factors: list of strings explaining engagement factors
            - confidence: float between 0 and 1
            
            Text: "{content}"
            
            Return only valid JSON:
            """
        }
        
        if analysis_type not in analysis_prompts:
            raise ValueError(f"Unknown analysis type: {analysis_type}")
        
        prompt = analysis_prompts[analysis_type]
        
        if context:
            prompt += f"\n\nAdditional context: {context}"
        
        try:
            response = await self.simple_completion(
                prompt=prompt,
                model=model,
                temperature=0.3,  # Lower temperature for analysis
                max_tokens=500
            )
            
            # Try to parse JSON response
            result = json.loads(response.strip())
            
            logger.info(
                "Content analysis completed",
                analysis_type=analysis_type,
                content_length=len(content),
                result_keys=list(result.keys())
            )
            
            return result
        
        except json.JSONDecodeError as e:
            # Safely log without Unicode issues
            response_preview = response[:100] if response else "<empty>"
            logger.error(f"Failed to parse analysis JSON: {str(e)}, response preview: {repr(response_preview)}")
            # Return default values
            return {
                f"{analysis_type}_score": 0.0,
                "confidence": 0.0,
                "error": "Failed to parse AI response"
            }
        
        except Exception as e:
            logger.error(f"Content analysis failed: {e}")
            raise AIServiceError(f"Analysis failed: {e}")
    
    async def get_available_models(self) -> List[str]:
        """Get list of available models from Groq."""
        try:
            response = await self.client.get(f"{self.base_url}/models")
            
            if response.status_code == 200:
                models_data = response.json()
                return [model["id"] for model in models_data.get("data", [])]
            else:
                logger.warning(f"Failed to get models: {response.status_code}")
                return []
        
        except Exception as e:
            logger.error(f"Error getting available models: {e}")
            return []
    
    async def health_check(self) -> bool:
        """Check if Groq API is accessible."""
        try:
            models = await self.get_available_models()
            return len(models) > 0
        except Exception as e:
            logger.error(f"Groq health check failed: {e}")
            return False
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics."""
        return {
            "requests_this_minute": self._request_count,
            "max_requests_per_minute": self._max_requests_per_minute,
            "last_reset": self._last_reset.isoformat(),
            "model_name": self.model_name
        }


# Global Groq client instance
_groq_client: Optional[GroqClient] = None


async def get_groq_client(settings: Optional[Settings] = None) -> GroqClient:
    """Get or create the global Groq client."""
    global _groq_client
    
    if _groq_client is None:
        if settings is None:
            from src.core.config import get_settings
            settings = get_settings()
        
        _groq_client = GroqClient(settings)
    
    return _groq_client


async def close_groq_client() -> None:
    """Close the global Groq client."""
    global _groq_client
    
    if _groq_client is not None:
        await _groq_client.close()
        _groq_client = None