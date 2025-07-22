"""
AI processing modules for The Snitch Discord Bot.

This package provides:
- Multi-provider LLM client (Groq, Gemini, Mistral) with intelligent routing
- Newsletter generation pipeline (RAG + Chain of Thought)
- Message embedding and semantic search
- Content analysis and controversy detection
"""

from .llm_client import LLMClient, get_llm_client, LLMProvider, TaskType
from .pipeline import NewsletterPipeline, get_newsletter_pipeline
from .embedding_service import EmbeddingService, get_embedding_service
from .service import AIService, get_ai_service

# Backward compatibility
from .llm_client import get_groq_client

# Define GroqClient alias after importing LLMClient
GroqClient = LLMClient

__all__ = [
    "LLMClient",
    "get_llm_client",
    "LLMProvider", 
    "TaskType",
    "NewsletterPipeline",
    "get_newsletter_pipeline",
    "EmbeddingService",
    "get_embedding_service",
    "AIService",
    "get_ai_service",
    # Backward compatibility
    "get_groq_client"
]