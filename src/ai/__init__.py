"""
AI processing modules for The Snitch Discord Bot.

This package provides:
- Groq client for fast AI inference
- Newsletter generation pipeline (RAG + Chain of Thought)
- Message embedding and semantic search
- Content analysis and controversy detection
"""

from .groq_client import GroqClient, get_groq_client
from .pipeline import NewsletterPipeline, get_newsletter_pipeline
from .embedding_service import EmbeddingService, get_embedding_service
from .service import AIService, get_ai_service

__all__ = [
    "GroqClient",
    "get_groq_client", 
    "NewsletterPipeline",
    "get_newsletter_pipeline",
    "EmbeddingService",
    "get_embedding_service",
    "AIService",
    "get_ai_service"
]