"""
Multi-provider LLM client for The Snitch Discord Bot.
Supports Groq, Gemini, and Mistral APIs with intelligent routing.
"""

import asyncio
from typing import Dict, Any, List, Optional, Union
import json
import httpx
from datetime import datetime
import logging
from enum import Enum

from src.core.config import Settings
from src.core.exceptions import AIServiceError, AIProviderError, AIQuotaExceededError, AIModelNotAvailableError
from src.core.logging import get_logger, log_api_call
from src.core.llm_logger import get_llm_logger, log_chain_step, log_llm_error, log_performance
from src.core.llm_decorators import log_llm_service
from src.utils.retry import api_retry

logger = get_logger(__name__)


class LLMProvider(str, Enum):
    """Available LLM providers."""
    GROQ = "groq"
    GEMINI = "gemini"
    MISTRAL = "mistral"


class TaskType(str, Enum):
    """Task types for intelligent routing."""
    THINKING = "thinking"  # Complex reasoning tasks
    INTERMEDIATE = "intermediate"  # Medium complexity analysis
    FINAL = "final"  # Final output generation
    ANALYSIS = "analysis"  # Content analysis tasks


class LLMClient:
    """Multi-provider LLM client with intelligent routing."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        
        # Provider configurations
        self.providers = {
            LLMProvider.GROQ: {
                "base_url": settings.groq_endpoint,
                "api_key": settings.groq_api_key,
                "models": {
                    "thinking": settings.groq_model_thinking,  # Thinking model
                    "default": settings.groq_model_name
                },
                "headers": {
                    "Authorization": f"Bearer {settings.groq_api_key}",
                    "Content-Type": "application/json"
                }
            },
            LLMProvider.GEMINI: {
                "base_url": settings.gemini_endpoint,
                "api_key": settings.gemini_api_key,
                "models": {
                    "flash": settings.gemini_flash_model,
                    "pro": settings.gemini_pro_model
                },
                "headers": {
                    "x-goog-api-key": settings.gemini_api_key,
                    "Content-Type": "application/json"
                }
            },
            LLMProvider.MISTRAL: {
                "base_url": settings.mistral_endpoint,
                "api_key": settings.mistral_api_key,
                "models": {
                    "large": settings.mistral_large,
                    "small": settings.mistral_small
                },
                "headers": {
                    "Authorization": f"Bearer {settings.mistral_api_key}",
                    "Content-Type": "application/json"
                }
            }
        }
        
        # Task routing configuration
        self.task_routing = {
            TaskType.THINKING: (LLMProvider.GROQ, "thinking"),
            TaskType.ANALYSIS: (LLMProvider.GROQ, "default"),
            TaskType.INTERMEDIATE: (LLMProvider.GEMINI, "flash"),
            TaskType.FINAL: (LLMProvider.GEMINI, "pro")  # Can fallback to Mistral large
        }
        
        # HTTP clients for each provider
        self.clients = {
            provider: httpx.AsyncClient(
                timeout=httpx.Timeout(60.0),
                headers=config["headers"]
            )
            for provider, config in self.providers.items()
        }
        
        # Rate limiting per provider
        self._request_counts = {provider: 0 for provider in LLMProvider}
        self._last_resets = {provider: datetime.now() for provider in LLMProvider}
        self._max_requests_per_minute = {
            LLMProvider.GROQ: 30,
            LLMProvider.GEMINI: 60,
            LLMProvider.MISTRAL: 50
        }
    
    async def close(self) -> None:
        """Close all HTTP clients."""
        for client in self.clients.values():
            await client.aclose()
    
    def _check_rate_limit(self, provider: LLMProvider) -> None:
        """Check if we're within rate limits for a provider."""
        now = datetime.now()
        
        # Reset counter every minute
        if (now - self._last_resets[provider]).total_seconds() >= 60:
            self._request_counts[provider] = 0
            self._last_resets[provider] = now
        
        if self._request_counts[provider] >= self._max_requests_per_minute[provider]:
            raise AIProviderError(provider.value, "Rate limit exceeded")
        
        self._request_counts[provider] += 1
    
    def _get_provider_for_task(self, task_type: TaskType) -> tuple[LLMProvider, str]:
        """Get the optimal provider and model for a task type."""
        if task_type in self.task_routing:
            return self.task_routing[task_type]
        
        # Default fallback
        return LLMProvider.GROQ, "default"
    
    async def _make_groq_request(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Make a request to Groq API."""
        provider = LLMProvider.GROQ
        config = self.providers[provider]
        client = self.clients[provider]
        
        self._check_rate_limit(provider)
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            **kwargs
        }
        
        if max_tokens:
            payload["max_tokens"] = max_tokens
        
        response = await client.post(
            f"{config['base_url']}/chat/completions",
            json=payload
        )
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 429:
            raise AIQuotaExceededError("Groq API rate limit exceeded")
        elif response.status_code == 401:
            raise AIProviderError("groq", "Authentication failed")
        elif response.status_code == 404:
            raise AIModelNotAvailableError(f"Groq model '{model}' not found. Available models might have changed.")
        else:
            raise AIProviderError("groq", f"API error: {response.status_code}")
    
    async def _make_gemini_request(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Make a request to Gemini API."""
        provider = LLMProvider.GEMINI
        config = self.providers[provider]
        client = self.clients[provider]
        
        self._check_rate_limit(provider)
        
        # Convert messages to Gemini format
        gemini_messages = self._convert_to_gemini_format(messages)
        
        payload = {
            "contents": gemini_messages,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens or 2048
            }
        }
        
        # Construct URL properly to avoid double slashes
        base_url = config['base_url'].rstrip('/')
        response = await client.post(
            f"{base_url}/{model}:generateContent",
            json=payload
        )
        
        if response.status_code == 200:
            gemini_response = response.json()
            # Convert Gemini response to OpenAI format
            return self._convert_from_gemini_format(gemini_response)
        elif response.status_code == 429:
            raise AIQuotaExceededError("Gemini API rate limit exceeded")
        elif response.status_code == 401:
            raise AIProviderError("gemini", "Authentication failed")
        elif response.status_code == 404:
            raise AIModelNotAvailableError(f"Gemini model '{model}' not found or endpoint incorrect. Check model name and API endpoint.")
        else:
            error_text = ""
            try:
                error_data = response.json()
                error_text = f": {error_data}"
            except:
                pass
            raise AIProviderError("gemini", f"API error: {response.status_code}{error_text}")
    
    async def _make_mistral_request(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Make a request to Mistral API."""
        provider = LLMProvider.MISTRAL
        config = self.providers[provider]
        client = self.clients[provider]
        
        self._check_rate_limit(provider)
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            **kwargs
        }
        
        if max_tokens:
            payload["max_tokens"] = max_tokens
        
        response = await client.post(
            f"{config['base_url']}",
            json=payload
        )
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 429:
            raise AIQuotaExceededError("Mistral API rate limit exceeded")
        elif response.status_code == 401:
            raise AIProviderError("mistral", "Authentication failed")
        elif response.status_code == 404:
            raise AIModelNotAvailableError(f"Mistral model '{model}' not found or endpoint incorrect. Check model name and API endpoint.")
        else:
            error_text = ""
            try:
                error_data = response.json()
                error_text = f": {error_data}"
            except:
                pass
            raise AIProviderError("mistral", f"API error: {response.status_code}{error_text}")
    
    def _convert_to_gemini_format(self, messages: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """Convert OpenAI format messages to Gemini format."""
        gemini_messages = []
        system_content_buffer = []

        other_messages = []
        for msg in messages:
            if msg.get("role") == "system":
                system_content_buffer.append(msg.get("content", ""))
            else:
                other_messages.append(msg)
        
        full_system_prompt = "\n".join(system_content_buffer)

        is_first_user_message = True
        for msg in other_messages:
            role = msg.get("role")
            content = msg.get("content", "")

            if role == "user":
                if full_system_prompt and is_first_user_message:
                    content = f"{full_system_prompt}\n\n---\n\nUser: {content}"
                    is_first_user_message = False

                gemini_messages.append({
                    "role": "user",
                    "parts": [{"text": content}]
                })
            elif role == "assistant":
                gemini_messages.append({
                    "role": "model",
                    "parts": [{"text": content}]
                })
        
        if full_system_prompt and is_first_user_message:
            gemini_messages.insert(0, {
                "role": "user",
                "parts": [{"text": full_system_prompt}]
            })

        return gemini_messages
    
    def _convert_from_gemini_format(self, gemini_response: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Gemini response to OpenAI format."""
        if "candidates" not in gemini_response or not gemini_response["candidates"]:
            raise AIServiceError("No candidates in Gemini response")
        
        candidate = gemini_response["candidates"][0]
        content = candidate["content"]["parts"][0]["text"]
        
        return {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": content
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": gemini_response.get("usageMetadata", {}).get("promptTokenCount", 0),
                "completion_tokens": gemini_response.get("usageMetadata", {}).get("candidatesTokenCount", 0)
            }
        }
    
    @api_retry
    @log_llm_service("LLMClient", include_result=False, include_params=True)
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        task_type: TaskType = TaskType.ANALYSIS,
        model: Optional[str] = None,
        provider: Optional[LLMProvider] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        server_id: Optional[str] = None,
        user_id: Optional[str] = None,
        command: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a chat completion with intelligent routing.
        
        Args:
            messages: List of message dictionaries
            task_type: Type of task for optimal routing
            model: Specific model to use (overrides routing)
            provider: Specific provider to use (overrides routing)
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            **kwargs: Additional provider-specific parameters
            
        Returns:
            Chat completion response in OpenAI format
        """
        start_time = datetime.now()
        
        try:
            # Determine provider and model
            if provider and model:
                selected_provider = provider
                selected_model = model
            elif provider:
                selected_provider = provider
                # Pick an appropriate default model for each provider
                provider_models = self.providers[provider]["models"]
                if provider == LLMProvider.GROQ:
                    selected_model = provider_models.get("default", provider_models.get("thinking"))
                elif provider == LLMProvider.GEMINI:
                    selected_model = provider_models.get("flash", provider_models.get("pro"))
                elif provider == LLMProvider.MISTRAL:
                    selected_model = provider_models.get("small", provider_models.get("large"))
                else:
                    # Fallback: use the first available model
                    selected_model = list(provider_models.values())[0]
            else:
                selected_provider, model_key = self._get_provider_for_task(task_type)
                selected_model = model or self.providers[selected_provider]["models"][model_key]
            
            logger.info(f"Routing {task_type} task to {selected_provider} with model {selected_model}")
            
            # Extract prompt for logging
            prompt_text = ""
            if messages:
                # Combine messages into a single prompt string for logging
                prompt_parts = []
                for msg in messages[-3:]:  # Log last 3 messages for context
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")
                    prompt_parts.append(f"[{role}] {content[:200]}")
                prompt_text = " | ".join(prompt_parts)
            
            # Make request to appropriate provider
            if selected_provider == LLMProvider.GROQ:
                result = await self._make_groq_request(
                    messages, selected_model, temperature, max_tokens, **kwargs
                )
            elif selected_provider == LLMProvider.GEMINI:
                result = await self._make_gemini_request(
                    messages, selected_model, temperature, max_tokens, **kwargs
                )
            elif selected_provider == LLMProvider.MISTRAL:
                result = await self._make_mistral_request(
                    messages, selected_model, temperature, max_tokens, **kwargs
                )
            else:
                raise AIServiceError(f"Unknown provider: {selected_provider}")
            
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            
            # Extract response content
            response_content = ""
            usage_stats = {}
            if result and "choices" in result and result["choices"]:
                response_content = result["choices"][0].get("message", {}).get("content", "")
                usage_stats = result.get("usage", {})
            
            # Log to existing system
            log_api_call(
                service=selected_provider.value,
                endpoint="/chat/completions",
                method="POST",
                status_code=200,
                duration_ms=duration_ms
            )
            
            # Log to LLM chain logger
            try:
                await log_chain_step(
                    chain_step="llm_completion",
                    provider=selected_provider.value,
                    model=selected_model,
                    task_type=task_type.value,
                    prompt=prompt_text,
                    response=response_content,
                    duration_ms=duration_ms,
                    usage_stats=usage_stats,
                    parameters={
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        **kwargs
                    },
                    server_id=server_id,
                    user_id=user_id,
                    command=command
                )
            except Exception as log_error:
                logger.warning(f"Failed to log LLM completion: {log_error}")
            
            logger.info(
                "LLM completion successful",
                provider=selected_provider.value,
                model=selected_model,
                task_type=task_type.value,
                duration_ms=duration_ms,
                tokens_used=usage_stats.get("total_tokens", 0)
            )
            
            return result
            
        except Exception as e:
            # Log the error
            try:
                await log_llm_error(
                    error_message=str(e),
                    service_name="LLMClient",
                    method_name="chat_completion",
                    provider=selected_provider.value if 'selected_provider' in locals() else None,
                    model=selected_model if 'selected_model' in locals() else None,
                    parameters={
                        "task_type": task_type.value,
                        "temperature": temperature,
                        "max_tokens": max_tokens
                    },
                    server_id=server_id,
                    user_id=user_id,
                    metadata={"command": command}
                )
            except Exception as log_error:
                logger.warning(f"Failed to log LLM error: {log_error}")
            
            # Try fallback providers based on error type and task
            fallback_attempted = False
            
            # For 404/model errors, try Groq as ultimate fallback
            if "not found" in str(e).lower() or "404" in str(e) or isinstance(e, AIModelNotAvailableError):
                logger.warning(f"Model not available error, falling back to Groq: {e}")
                try:
                    fallback_model = self.providers[LLMProvider.GROQ]["models"]["default"]
                    fallback_result = await self._make_groq_request(
                        messages, fallback_model, temperature, max_tokens, **kwargs
                    )
                    fallback_attempted = True
                    
                    # Log successful fallback
                    try:
                        duration_ms = (datetime.now() - start_time).total_seconds() * 1000
                        response_content = fallback_result["choices"][0].get("message", {}).get("content", "") if fallback_result.get("choices") else ""
                        
                        await log_chain_step(
                            chain_step="llm_completion_model_fallback",
                            provider="groq",
                            model=fallback_model,
                            task_type=task_type.value,
                            prompt=prompt_text if 'prompt_text' in locals() else "",
                            response=response_content,
                            duration_ms=duration_ms,
                            usage_stats=fallback_result.get("usage", {}),
                            server_id=server_id,
                            user_id=user_id,
                            command=command,
                            metadata={"fallback_from": selected_provider.value if 'selected_provider' in locals() else "unknown", "original_error": str(e)}
                        )
                    except Exception as log_error:
                        logger.warning(f"Failed to log model fallback completion: {log_error}")
                    
                    return fallback_result
                    
                except Exception as fallback_error:
                    logger.error(f"Groq fallback also failed: {fallback_error}")
                    # Continue to original fallback logic below
            
            # Original fallback logic for final tasks
            if not fallback_attempted and task_type == TaskType.FINAL and 'selected_provider' in locals() and selected_provider == LLMProvider.GEMINI:
                logger.warning(f"Gemini failed for final task, falling back to Mistral: {e}")
                try:
                    fallback_result = await self._make_mistral_request(
                        messages, self.providers[LLMProvider.MISTRAL]["models"]["large"], 
                        temperature, max_tokens, **kwargs
                    )
                    
                    # Log successful fallback
                    try:
                        duration_ms = (datetime.now() - start_time).total_seconds() * 1000
                        response_content = fallback_result["choices"][0].get("message", {}).get("content", "") if fallback_result.get("choices") else ""
                        
                        await log_chain_step(
                            chain_step="llm_completion_fallback",
                            provider="mistral",
                            model=self.providers[LLMProvider.MISTRAL]["models"]["large"],
                            task_type=task_type.value,
                            prompt=prompt_text if 'prompt_text' in locals() else "",
                            response=response_content,
                            duration_ms=duration_ms,
                            usage_stats=fallback_result.get("usage", {}),
                            server_id=server_id,
                            user_id=user_id,
                            command=command,
                            metadata={"fallback_from": "gemini", "original_error": str(e)}
                        )
                    except Exception as log_error:
                        logger.warning(f"Failed to log fallback completion: {log_error}")
                    
                    return fallback_result
                    
                except Exception as fallback_error:
                    logger.error(f"Fallback to Mistral also failed: {fallback_error}")
                    # Log fallback failure
                    try:
                        await log_llm_error(
                            error_message=f"Fallback failed: {fallback_error}",
                            service_name="LLMClient",
                            method_name="chat_completion_fallback",
                            provider="mistral",
                            model=self.providers[LLMProvider.MISTRAL]["models"]["large"],
                            server_id=server_id,
                            user_id=user_id,
                            metadata={"original_error": str(e), "fallback_error": str(fallback_error)}
                        )
                    except:
                        pass
            
            logger.error(f"LLM completion failed: {e}")
            raise
    
    async def simple_completion(
        self,
        prompt: str,
        task_type: TaskType = TaskType.ANALYSIS,
        model: Optional[str] = None,
        provider: Optional[LLMProvider] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """Simple text completion with intelligent routing."""
        messages = [{"role": "user", "content": prompt}]
        
        response = await self.chat_completion(
            messages=messages,
            task_type=task_type,
            model=model,
            provider=provider,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        return response["choices"][0]["message"]["content"]
    
    async def conversation_completion(
        self,
        conversation: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        task_type: TaskType = TaskType.ANALYSIS,
        model: Optional[str] = None,
        provider: Optional[LLMProvider] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """Complete a conversation with intelligent routing."""
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.extend(conversation)
        
        response = await self.chat_completion(
            messages=messages,
            task_type=task_type,
            model=model,
            provider=provider,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        return response["choices"][0]["message"]["content"]
    
    async def analyze_content(
        self,
        content: str,
        analysis_type: str,
        context: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[LLMProvider] = None
    ) -> Dict[str, Any]:
        """Analyze content using the optimal provider for analysis tasks."""
        
        analysis_prompts = {
            "fact_check": f"""
            Analyze the truthness of the content, where this content is true or not:
            - fact-check: needs investigation,true  or false
            - score: float between 0 (false fact) and 1 (absolute truth)
            - confidence: float between 0 and 1
            
            Text: "{content}"
            
            Return only valid JSON:
            """,
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
                task_type=TaskType.ANALYSIS,
                model=model,
                provider=provider,
                temperature=0.3,
                max_tokens=500
            )
            
            # Clean and parse JSON response
            cleaned_response = response.strip()
            
            # Remove markdown code block markers if present
            if cleaned_response.startswith('```json'):
                end_marker = cleaned_response.find('```', 7)
                if end_marker != -1:
                    cleaned_response = cleaned_response[7:end_marker].strip()
                else:
                    cleaned_response = cleaned_response[7:].strip()
            elif cleaned_response.startswith('```'):
                end_marker = cleaned_response.find('```', 3)
                if end_marker != -1:
                    cleaned_response = cleaned_response[3:end_marker].strip()
                else:
                    cleaned_response = cleaned_response[3:].strip()
            
            result = json.loads(cleaned_response)
            
            logger.info(
                "Content analysis completed",
                analysis_type=analysis_type,
                content_length=len(content),
                result_keys=list(result.keys())
            )
            
            return result
        
        except json.JSONDecodeError as e:
            response_preview = response[:100] if response else "<empty>"
            cleaned_preview = cleaned_response[:100] if 'cleaned_response' in locals() else "<not cleaned>"
            logger.error(
                f"Failed to parse analysis JSON: {str(e)}, "
                f"original response preview: {repr(response_preview)}, "
                f"cleaned response preview: {repr(cleaned_preview)}"
            )
            return {
                f"{analysis_type}_score": 0.0,
                "confidence": 0.0,
                "error": "Failed to parse AI response"
            }
        
        except Exception as e:
            logger.error(f"Content analysis failed: {e}")
            raise AIServiceError(f"Analysis failed: {e}")
    
    async def health_check(self) -> Dict[str, bool]:
        """Check health of all providers."""
        results = {}
        
        for provider in LLMProvider:
            try:
                # Simple test request
                test_messages = [{"role": "user", "content": "Hello"}]
                await self.chat_completion(
                    messages=test_messages,
                    provider=provider,
                    max_tokens=10
                )
                results[provider.value] = True
            except Exception as e:
                logger.error(f"{provider.value} health check failed: {e}")
                results[provider.value] = False
        
        return results
    
    def validate_configuration(self) -> Dict[str, Any]:
        """Validate API configuration and provide diagnostics."""
        diagnostics = {}
        
        for provider, config in self.providers.items():
            provider_diag = {
                "provider": provider.value,
                "has_api_key": bool(config.get("api_key")),
                "has_base_url": bool(config.get("base_url")),
                "models": list(config.get("models", {}).keys()),
                "issues": []
            }
            
            # Check for common configuration issues
            if not config.get("api_key"):
                provider_diag["issues"].append("Missing API key")
            
            if not config.get("base_url"):
                provider_diag["issues"].append("Missing base URL")
            
            # Provider-specific checks
            if provider == LLMProvider.GEMINI:
                if "gemini-" not in str(config.get("models", {}).get("pro", "")):
                    provider_diag["issues"].append("Pro model name doesn't contain 'gemini-'")
                if "gemini-" not in str(config.get("models", {}).get("flash", "")):
                    provider_diag["issues"].append("Flash model name doesn't contain 'gemini-'")
                if "generativelanguage.googleapis.com" not in config.get("base_url", ""):
                    provider_diag["issues"].append("Base URL doesn't look like official Gemini API endpoint")
            
            elif provider == LLMProvider.MISTRAL:
                if "api.mistral.ai" not in config.get("base_url", ""):
                    provider_diag["issues"].append("Base URL doesn't look like official Mistral API endpoint")
            
            elif provider == LLMProvider.GROQ:
                if "api.groq.com" not in config.get("base_url", ""):
                    provider_diag["issues"].append("Base URL doesn't look like official Groq API endpoint")
            
            diagnostics[provider.value] = provider_diag
        
        return diagnostics
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics for all providers."""
        return {
            provider.value: {
                "requests_this_minute": self._request_counts[provider],
                "max_requests_per_minute": self._max_requests_per_minute[provider],
                "last_reset": self._last_resets[provider].isoformat()
            }
            for provider in LLMProvider
        }


# Global LLM client instance
_llm_client: Optional[LLMClient] = None

# Backward compatibility class alias
GroqClient = LLMClient


async def get_llm_client(settings: Optional[Settings] = None) -> LLMClient:
    """Get or create the global LLM client."""
    global _llm_client
    
    if _llm_client is None:
        if settings is None:
            from src.core.config import get_settings
            settings = get_settings()
        
        _llm_client = LLMClient(settings)
    
    return _llm_client


async def close_llm_client() -> None:
    """Close the global LLM client."""
    global _llm_client
    
    if _llm_client is not None:
        await _llm_client.close()
        _llm_client = None


# Backward compatibility aliases
async def get_groq_client(settings: Optional[Settings] = None):
    """Backward compatibility alias for get_llm_client."""
    return await get_llm_client(settings)

async def close_groq_client():
    """Backward compatibility alias for close_llm_client."""
    return await close_llm_client()