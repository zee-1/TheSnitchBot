"""
Base classes for leak command Chain of Thoughts implementation.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from src.ai.llm_client import LLMClient, TaskType
from src.core.logging import get_logger
logger = get_logger(__name__)


@dataclass
class ContextAnalysis:
    """Results from context analysis step."""
    user_communication_style: Dict[str, Any]
    active_topics: List[str]
    server_culture_assessment: Dict[str, Any]
    relevance_factors: Dict[str, float]
    user_interests: List[str]
    recent_interactions: List[Dict[str, Any]]
    reasoning: str


@dataclass
class ContentConcept:
    """A potential leak content concept with scoring."""
    concept_id: str
    description: str
    relevance_score: float
    appropriateness_score: float
    server_fit_score: float
    reasoning: str
    content_hooks: Dict[str, Any]


@dataclass
class ContentPlan:
    """Results from content planning step."""
    selected_concept: ContentConcept
    alternative_concepts: List[ContentConcept]
    persona_requirements: Dict[str, Any]
    content_guidelines: Dict[str, Any]
    reasoning: str


@dataclass
class LeakContent:
    """Final leak content with metadata."""
    content: str
    reliability_percentage: int
    source_attribution: str
    content_length: int
    reasoning: str


class BaseLeakChain(ABC):
    """Base class for leak command CoT chains."""
    
    # Each subclass should override this to specify their task type
    task_type: TaskType = TaskType.ANALYSIS
    
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
        self.logger = get_logger(self.__class__.__name__)
    
    @abstractmethod
    async def process(self, *args, **kwargs) -> Any:
        """Process this step of the chain."""
        pass
    
    async def _safe_ai_completion(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
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
    
    def _extract_score_from_response(self, response: str, score_name: str) -> float:
        """Extract a score from AI response."""
        try:
            # Look for patterns like "RELEVANCE_SCORE: 0.8" or "Relevance: 8/10"
            import re
            patterns = [
                rf"{score_name.upper()}_SCORE:\s*([0-9.]+)",
                rf"{score_name.lower()}\s*:\s*([0-9.]+)",
                rf"{score_name.lower()}\s*:\s*([0-9]+)/10"
            ]
            
            for pattern in patterns:
                match = re.search(pattern, response, re.IGNORECASE)
                if match:
                    score = float(match.group(1))
                    # Normalize /10 scores to 0-1
                    if "/10" in pattern and score > 1:
                        score = score / 10
                    return min(max(score, 0.0), 1.0)  # Clamp to 0-1
            
            # Default if no score found
            return 0.5
        except Exception:
            return 0.5