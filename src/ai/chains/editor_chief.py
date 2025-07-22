"""
Editor-in-Chief Chain - Chain B of the newsletter pipeline.
Selects the best story from candidates identified by News Desk.
"""

from typing import List, Dict, Any, Optional
import logging

from .base_newsletter_chain import BaseNewsletterChain
from src.ai.llm_client import LLMClient, TaskType
from src.ai.prompts.newsletter import NewsletterPrompts
from src.models.server import PersonaType
from src.core.exceptions import AIServiceError
from src.core.logging import get_logger

logger = get_logger(__name__)


class EditorChiefChain(BaseNewsletterChain):
    """Chain B: Selects the best story for the newsletter headline."""
    
    task_type = TaskType.THINKING  # Complex editorial decision-making
    
    async def select_headline(
        self,
        story_candidates: List[Dict[str, Any]],
        persona: PersonaType,
        server_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Select the best story from candidates for the newsletter headline.
        
        Args:
            story_candidates: List of story candidates from News Desk
            persona: Bot persona for decision-making style
            server_context: Additional context about the server
            
        Returns:
            Selected story with editorial decisions
        """
        try:
            if not story_candidates:
                logger.warning("No story candidates provided for headline selection")
                return self._create_fallback_story()
            
            # If only one candidate, still run it through editorial review
            if len(story_candidates) == 1:
                return await self._review_single_story(story_candidates[0], persona, server_context)
            
            # Prepare candidates for editorial review
            candidates_data = self._prepare_candidates_data(story_candidates)
            
            # Get appropriate prompt
            system_prompt = NewsletterPrompts.get_editor_chief_prompt(persona)
            
            # Create editorial review prompt
            editorial_prompt = f"""
            Review these story candidates and select the best one for today's newsletter headline.
            
            STORY CANDIDATES:
            {candidates_data}
            
            Consider:
            - Which story will most engage this server's community?
            - Which has the best combination of entertainment value and relevance?
            - Which will generate the most positive discussion?
            - Which fits best with the {persona.replace('_', ' ')} persona?
            
            Select ONE story and explain your editorial decision.
            """
            
            # Get AI editorial decision with TaskType routing
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": editorial_prompt})
            
            response_data = await self._safe_ai_chat_completion(
                messages=messages,
                temperature=0.6,  # Slightly lower temperature for editorial decisions
                max_tokens=2048
            )
            response = response_data["choices"][0]["message"]["content"]
            
            # Parse editorial decision
            selected_story = self._parse_editorial_decision(response, story_candidates)
            
            # Add editorial metadata
            editorial_story = self._add_editorial_metadata(selected_story, response, story_candidates)
            
            logger.info(
                "Editorial selection completed",
                selected_headline=editorial_story.get("headline", "Unknown"),
                total_candidates=len(story_candidates),
                persona=persona,
                story_score=editorial_story.get("story_score", 0)
            )
            
            return editorial_story
        
        except Exception as e:
            logger.error(f"Error in editor-in-chief story selection: {e}")
            
            # Fallback to highest scoring story
            if story_candidates:
                fallback_story = max(story_candidates, key=lambda s: s.get("story_score", 0))
                fallback_story["is_fallback"] = True
                fallback_story["editorial_reasoning"] = "Automatic selection due to processing error"
                return fallback_story
            
            raise AIServiceError(f"Editorial selection failed: {e}")
    
    def _prepare_candidates_data(self, candidates: List[Dict[str, Any]]) -> str:
        """Prepare story candidates data for editorial review."""
        
        formatted_candidates = []
        
        for i, story in enumerate(candidates, 1):
            candidate_text = f"""
            **CANDIDATE {i}:**
            Headline: {story.get('headline', 'No headline')}
            Summary: {story.get('summary', 'No summary')}
            Newsworthiness: {story.get('newsworthiness', 'Not specified')}
            Key Players: {story.get('key_players', 'Not specified')}
            
            METRICS:
            - Story Score: {story.get('story_score', 0):.2f}/1.0
            - Related Messages: {story.get('related_message_count', 0)}
            - Total Engagement: {story.get('total_engagement', 0):.2f}
            - Unique Participants: {story.get('unique_participants', 0)}
            - Average Controversy: {story.get('average_controversy', 0):.2f}/1.0
            - Time Span: {story.get('time_span_hours', 0):.1f} hours
            """
            
            formatted_candidates.append(candidate_text)
        
        return "\n".join(formatted_candidates)
    
    async def _review_single_story(
        self,
        story: Dict[str, Any],
        persona: PersonaType,
        server_context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Review a single story candidate for editorial improvements."""
        
        try:
            system_prompt = NewsletterPrompts.get_editor_chief_prompt(persona)
            
            review_prompt = f"""
            Review this single story candidate for the newsletter. Even though it's the only option,
            provide editorial feedback and improvements.
            
            STORY:
            Headline: {story.get('headline', 'No headline')}
            Summary: {story.get('summary', 'No summary')}
            Metrics: Score {story.get('story_score', 0):.2f}, {story.get('unique_participants', 0)} participants
            
            Provide:
            1. An improved headline if needed
            2. Editorial angle for the reporter
            3. Why this story works for the community
            4. Any concerns or adjustments needed
            """
            
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": review_prompt})
            
            response_data = await self._safe_ai_chat_completion(
                messages=messages,
                temperature=0.6,
                max_tokens=2048
            )
            response = response_data["choices"][0]["message"]["content"]
            
            # Add editorial review to story
            reviewed_story = {
                **story,
                "editorial_review": response,
                "editorial_reasoning": "Single candidate review completed",
                "is_selected": True
            }
            
            return reviewed_story
        
        except Exception as e:
            logger.warning(f"Single story review failed: {e}")
            story["editorial_reasoning"] = "Review failed, proceeding with original"
            story["is_selected"] = True
            return story
    
    def _parse_editorial_decision(self, response: str, candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Parse the AI's editorial decision to identify selected story."""
        
        response_lower = response.lower()
        
        # Look for explicit story selection
        for i, candidate in enumerate(candidates, 1):
            candidate_indicators = [
                f"story {i}",
                f"candidate {i}",
                candidate.get("headline", "").lower()[:20]  # First 20 chars of headline
            ]
            
            for indicator in candidate_indicators:
                if indicator and indicator in response_lower:
                    selected_story = candidate.copy()
                    selected_story["is_selected"] = True
                    return selected_story
        
        # Fallback: analyze response for keywords related to each story
        best_match = None
        best_score = 0
        
        for candidate in candidates:
            score = 0
            headline_words = candidate.get("headline", "").lower().split()
            summary_words = candidate.get("summary", "").lower().split()[:10]  # First 10 words
            
            # Count keyword matches
            for word in headline_words + summary_words:
                if len(word) > 3 and word in response_lower:
                    score += 1
            
            if score > best_score:
                best_score = score
                best_match = candidate
        
        if best_match:
            selected_story = best_match.copy()
            selected_story["is_selected"] = True
            return selected_story
        
        # Ultimate fallback: highest scoring story
        selected_story = max(candidates, key=lambda s: s.get("story_score", 0)).copy()
        selected_story["is_selected"] = True
        selected_story["selection_method"] = "fallback_highest_score"
        
        return selected_story
    
    def _add_editorial_metadata(
        self,
        selected_story: Dict[str, Any],
        editorial_response: str,
        all_candidates: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Add editorial metadata to the selected story."""
        
        # Parse editorial elements from response
        editorial_elements = self._parse_editorial_elements(editorial_response)
        
        # Create enhanced story with editorial data
        editorial_story = {
            **selected_story,
            "editorial_decision": editorial_response,
            "editorial_reasoning": editorial_elements.get("reasoning", "Story selected by editorial review"),
            "suggested_headline": editorial_elements.get("headline", selected_story.get("headline")),
            "reporting_angle": editorial_elements.get("angle", "Standard reporting approach"),
            "editorial_priority": self._calculate_editorial_priority(selected_story, all_candidates),
            "editorial_notes": editorial_elements.get("notes", []),
            "selection_timestamp": self._get_current_timestamp(),
            "rejected_candidates": len(all_candidates) - 1
        }
        
        return editorial_story
    
    def _parse_editorial_elements(self, response: str) -> Dict[str, Any]:
        """Parse editorial elements from the AI response."""
        
        elements = {}
        lines = response.split('\n')
        
        current_section = None
        content_buffer = []
        
        for line in lines:
            line = line.strip()
            
            # Identify sections
            if line.startswith("**SELECTED") or "HEADLINE STORY" in line:
                current_section = "selection"
            elif line.startswith("Reasoning:") or "REASONING" in line:
                current_section = "reasoning"
                content = line.replace("Reasoning:", "").replace("**REASONING:**", "").strip()
                if content:
                    content_buffer = [content]
            elif line.startswith("**HEADLINE:**"):
                current_section = "headline"
                content = line.replace("**HEADLINE:**", "").strip()
                if content:
                    elements["headline"] = content
            elif line.startswith("**ANGLE:**"):
                current_section = "angle"
                content = line.replace("**ANGLE:**", "").strip()
                if content:
                    elements["angle"] = content
            elif current_section and line:
                content_buffer.append(line)
            elif current_section and not line:
                # End of section
                if current_section == "reasoning" and content_buffer:
                    elements["reasoning"] = " ".join(content_buffer)
                content_buffer = []
                current_section = None
        
        # Handle any remaining content
        if current_section == "reasoning" and content_buffer:
            elements["reasoning"] = " ".join(content_buffer)
        
        return elements
    
    def _calculate_editorial_priority(
        self,
        selected_story: Dict[str, Any],
        all_candidates: List[Dict[str, Any]]
    ) -> str:
        """Calculate editorial priority level."""
        
        story_score = selected_story.get("story_score", 0)
        engagement = selected_story.get("total_engagement", 0)
        participants = selected_story.get("unique_participants", 0)
        
        # Calculate priority based on multiple factors
        priority_score = (story_score * 0.4) + (min(engagement / 5, 1) * 0.3) + (min(participants / 10, 1) * 0.3)
        
        if priority_score >= 0.8:
            return "high"
        elif priority_score >= 0.5:
            return "medium"
        else:
            return "low"
    
    def _get_current_timestamp(self) -> str:
        """Get current timestamp for editorial records."""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def _create_fallback_story(self) -> Dict[str, Any]:
        """Create a fallback story when no candidates are available."""
        
        return {
            "headline": "Community Activity Update",
            "summary": "Regular community discussions and interactions continue across the server.",
            "newsworthiness": "Baseline community activity",
            "key_players": "Community members",
            "story_score": 0.3,
            "editorial_reasoning": "Fallback story - no specific candidates available",
            "reporting_angle": "General community update",
            "is_fallback": True,
            "is_selected": True
        }