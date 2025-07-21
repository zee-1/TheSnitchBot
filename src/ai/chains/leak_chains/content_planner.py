"""
Content Planner - CoT Step 2
Plans relevant content concepts based on context analysis.
"""

from typing import List, Dict, Any
import uuid
from .base import BaseLeakChain, ContextAnalysis, ContentConcept, ContentPlan
from src.models.server import PersonaType
from src.core.logging import get_logger

logger = get_logger(__name__)


class ContentPlanner(BaseLeakChain):
    """Plans content concepts for leak generation based on context analysis."""
    
    async def plan_content(
        self,
        context_analysis: ContextAnalysis,
        persona: PersonaType,
        content_guidelines: Dict[str, Any]
    ) -> ContentPlan:
        """
        Plan content concepts based on context analysis.
        
        Args:
            context_analysis: Results from context analyzer
            persona: Bot persona for content style
            content_guidelines: Content safety and style guidelines
            
        Returns:
            ContentPlan with selected concept and alternatives
        """
        try:
            self.logger.info("Starting content planning")
            
            # Generate multiple content concepts
            content_concepts = await self._generate_content_concepts(
                context_analysis, persona, content_guidelines
            )
            
            # Score and rank concepts
            scored_concepts = await self._score_concepts(
                content_concepts, context_analysis, persona
            )
            
            # Select best concept
            selected_concept = scored_concepts[0] if scored_concepts else None
            alternative_concepts = scored_concepts[1:4]  # Keep top 3 alternatives
            
            # Prepare persona requirements
            persona_requirements = self._get_persona_requirements(persona)
            
            # Generate planning reasoning
            reasoning = self._generate_planning_reasoning(
                selected_concept, alternative_concepts, context_analysis
            )
            
            content_plan = ContentPlan(
                selected_concept=selected_concept,
                alternative_concepts=alternative_concepts,
                persona_requirements=persona_requirements,
                content_guidelines=content_guidelines,
                reasoning=reasoning
            )
            
            self.logger.info(f"Content planning completed. Selected concept: {selected_concept.concept_id if selected_concept else 'None'}")
            return content_plan
            
        except Exception as e:
            self.logger.error(f"Content planning failed: {e}")
            return self._get_fallback_plan(persona, content_guidelines)
    
    async def _generate_content_concepts(
        self,
        context_analysis: ContextAnalysis,
        persona: PersonaType,
        content_guidelines: Dict[str, Any]
    ) -> List[ContentConcept]:
        """Generate multiple content concept ideas using AI."""
        
        prompt = f"""Generate 4 different leak content concepts based on the following analysis:

CONTEXT ANALYSIS:
{context_analysis.reasoning}

USER INTERESTS: {', '.join(context_analysis.user_interests)}
ACTIVE TOPICS: {', '.join(context_analysis.active_topics)}
COMMUNICATION STYLE: {context_analysis.user_communication_style['style']}
SERVER CULTURE: {context_analysis.server_culture_assessment['culture_type']}

RELEVANCE FACTORS:
- Gaming: {context_analysis.relevance_factors.get('gaming', 0.5):.2f}
- Social: {context_analysis.relevance_factors.get('social', 0.5):.2f}
- Hobby: {context_analysis.relevance_factors.get('hobby', 0.5):.2f}
- Meme: {context_analysis.relevance_factors.get('meme', 0.5):.2f}
- Personality: {context_analysis.relevance_factors.get('personality', 0.5):.2f}

PERSONA: {persona.value}

Generate 4 distinct leak concepts, each focused on different themes:

CONCEPT_1_THEME: Gaming/Tech related embarrassment
CONCEPT_1_DESC: [Brief description of the concept]
CONCEPT_1_HOOKS: [Key elements to make it personal and funny]

CONCEPT_2_THEME: Social interaction mishap
CONCEPT_2_DESC: [Brief description of the concept]
CONCEPT_2_HOOKS: [Key elements to make it personal and funny]

CONCEPT_3_THEME: Hobby/Interest obsession
CONCEPT_3_DESC: [Brief description of the concept]
CONCEPT_3_HOOKS: [Key elements to make it personal and funny]

CONCEPT_4_THEME: Personality quirk revelation
CONCEPT_4_DESC: [Brief description of the concept]
CONCEPT_4_HOOKS: [Key elements to make it personal and funny]

Keep concepts harmless, humorous, and appropriate for a Discord community."""
        
        try:
            response = await self._safe_ai_completion(
                prompt=prompt,
                temperature=0.8,
                max_tokens=800,
                fallback_response=self._get_fallback_concepts_text()
            )
            
            concepts = self._parse_concepts_from_response(response)
            return concepts
            
        except Exception as e:
            self.logger.warning(f"AI concept generation failed: {e}")
            return self._get_fallback_concepts()
    
    def _parse_concepts_from_response(self, response: str) -> List[ContentConcept]:
        """Parse content concepts from AI response."""
        concepts = []
        
        # Extract concept blocks using regex
        import re
        concept_pattern = r'CONCEPT_(\d+)_THEME:\s*(.+?)\nCONCEPT_\1_DESC:\s*(.+?)\nCONCEPT_\1_HOOKS:\s*(.+?)(?=\n\n|\nCONCEPT_|\Z)'
        
        matches = re.findall(concept_pattern, response, re.DOTALL | re.IGNORECASE)
        
        for i, (num, theme, desc, hooks) in enumerate(matches):
            concept = ContentConcept(
                concept_id=f"concept_{num}",
                description=desc.strip(),
                relevance_score=0.0,  # Will be calculated in scoring step
                appropriateness_score=1.0,  # Assume appropriate since AI generated
                server_fit_score=0.0,  # Will be calculated in scoring step
                reasoning=f"Theme: {theme.strip()}",
                content_hooks={"theme": theme.strip(), "hooks": hooks.strip()}
            )
            concepts.append(concept)
        
        # If parsing failed, return fallback concepts
        if not concepts:
            return self._get_fallback_concepts()
        
        return concepts
    
    async def _score_concepts(
        self,
        concepts: List[ContentConcept],
        context_analysis: ContextAnalysis,
        persona: PersonaType
    ) -> List[ContentConcept]:
        """Score and rank content concepts."""
        
        scored_concepts = []
        
        for concept in concepts:
            try:
                # Calculate relevance score based on context
                relevance_score = self._calculate_relevance_score(concept, context_analysis)
                
                # Calculate server fit score
                server_fit_score = self._calculate_server_fit_score(concept, context_analysis)
                
                # Update concept with scores
                concept.relevance_score = relevance_score
                concept.server_fit_score = server_fit_score
                
                # Calculate overall score (weighted average)
                overall_score = (
                    relevance_score * 0.4 +
                    concept.appropriateness_score * 0.3 +
                    server_fit_score * 0.3
                )
                
                # Add reasoning for this concept's score
                concept.reasoning += f" | Relevance: {relevance_score:.2f}, Server Fit: {server_fit_score:.2f}, Overall: {overall_score:.2f}"
                
                scored_concepts.append((overall_score, concept))
                
            except Exception as e:
                self.logger.warning(f"Concept scoring failed for {concept.concept_id}: {e}")
                # Keep concept with default scores
                scored_concepts.append((0.5, concept))
        
        # Sort by score (highest first)
        scored_concepts.sort(key=lambda x: x[0], reverse=True)
        
        return [concept for score, concept in scored_concepts]
    
    def _calculate_relevance_score(self, concept: ContentConcept, context_analysis: ContextAnalysis) -> float:
        """Calculate how relevant a concept is to the user context."""
        
        theme = concept.content_hooks.get("theme", "").lower()
        relevance_factors = context_analysis.relevance_factors
        
        # Map themes to relevance factors
        theme_mappings = {
            "gaming": relevance_factors.get("gaming", 0.5),
            "tech": relevance_factors.get("gaming", 0.5),  # Tech maps to gaming factor
            "social": relevance_factors.get("social", 0.5),
            "interaction": relevance_factors.get("social", 0.5),
            "hobby": relevance_factors.get("hobby", 0.5),
            "interest": relevance_factors.get("hobby", 0.5),
            "personality": relevance_factors.get("personality", 0.5),
            "quirk": relevance_factors.get("personality", 0.5)
        }
        
        # Find best matching theme
        max_relevance = 0.3  # Minimum base relevance
        for theme_key, relevance in theme_mappings.items():
            if theme_key in theme:
                max_relevance = max(max_relevance, relevance)
        
        # Boost score if user interests align
        for interest in context_analysis.user_interests:
            if interest.lower() in theme or interest.lower() in concept.description.lower():
                max_relevance = min(max_relevance + 0.2, 1.0)
                break
        
        return max_relevance
    
    def _calculate_server_fit_score(self, concept: ContentConcept, context_analysis: ContextAnalysis) -> float:
        """Calculate how well a concept fits the server culture."""
        
        server_culture = context_analysis.server_culture_assessment["culture_type"]
        active_topics = context_analysis.active_topics
        
        # Base score based on server culture
        culture_scores = {
            "friendly": 0.8,
            "casual": 0.9,
            "meme-heavy": 0.8,
            "competitive": 0.7,
            "technical": 0.6,
            "creative": 0.7,
            "neutral": 0.6
        }
        
        base_score = culture_scores.get(server_culture, 0.6)
        
        # Check if concept aligns with active topics
        topic_boost = 0.0
        concept_text = (concept.description + " " + str(concept.content_hooks)).lower()
        
        for topic in active_topics:
            if topic.lower() in concept_text:
                topic_boost += 0.1
        
        return min(base_score + topic_boost, 1.0)
    
    def _get_persona_requirements(self, persona: PersonaType) -> Dict[str, Any]:
        """Get persona-specific requirements for content writing."""
        
        persona_configs = {
            PersonaType.SASSY_REPORTER: {
                "tone": "sassy",
                "style": "gossip columnist",
                "emojis": ["✨", "💅", "☕", "👀"],
                "phrases": ["Tea has been SPILLED!", "No cap!", "The dedication is real!"],
                "max_length": 150
            },
            PersonaType.INVESTIGATIVE_JOURNALIST: {
                "tone": "serious",
                "style": "news reporter",
                "emojis": ["📊", "🔍", "📋"],
                "phrases": ["Sources confirm", "Investigation reveals", "Breaking:"],
                "max_length": 200
            },
            PersonaType.GOSSIP_COLUMNIST: {
                "tone": "dramatic",
                "style": "tabloid gossip",
                "emojis": ["💋", "👑", "✨", "🍵"],
                "phrases": ["Darlings!", "The gossip desk", "Exclusively yours"],
                "max_length": 160
            },
            PersonaType.SPORTS_COMMENTATOR: {
                "tone": "energetic",
                "style": "sports announcer",
                "emojis": ["🏆", "📣", "🎯", "💪"],
                "phrases": ["LADIES AND GENTLEMEN!", "WHAT A PLAY!", "THE CROWD GOES WILD!"],
                "max_length": 180
            },
            PersonaType.CONSPIRACY_THEORIST: {
                "tone": "mysterious",
                "style": "conspiracy theorist",
                "emojis": ["👁️", "🔍", "🎭", "🛸"],
                "phrases": ["WAKE UP SHEEPLE!", "The truth is out there", "COINCIDENCE? I THINK NOT!"],
                "max_length": 170
            },
            PersonaType.WEATHER_ANCHOR: {
                "tone": "professional",
                "style": "weather reporter",
                "emojis": ["🌤️", "📡", "🌪️"],
                "phrases": ["Community forecast", "Current conditions", "Weather update"],
                "max_length": 150
            }
        }
        
        return persona_configs.get(persona, {
            "tone": "neutral",
            "style": "general",
            "emojis": ["📢"],
            "phrases": ["Breaking news:", "Sources say"],
            "max_length": 150
        })
    
    def _generate_planning_reasoning(
        self,
        selected_concept: ContentConcept,
        alternative_concepts: List[ContentConcept],
        context_analysis: ContextAnalysis
    ) -> str:
        """Generate reasoning summary for content planning decision."""
        
        if not selected_concept:
            return "No suitable concepts generated. Using fallback approach."
        
        reasoning = f"""Content Planning Decision:

Selected Concept: {selected_concept.concept_id}
Theme: {selected_concept.content_hooks.get('theme', 'Unknown')}
Relevance Score: {selected_concept.relevance_score:.2f}
Server Fit Score: {selected_concept.server_fit_score:.2f}

Selection Reasoning:
{selected_concept.reasoning}

Alternative concepts considered: {len(alternative_concepts)}
Context factors: User interests align with selected theme, server culture supports this content type."""
        
        return reasoning
    
    def _get_fallback_concepts_text(self) -> str:
        """Get fallback concepts text for AI parsing."""
        return """CONCEPT_1_THEME: Gaming mishap
CONCEPT_1_DESC: User had an embarrassing gaming moment
CONCEPT_1_HOOKS: Gaming failure, funny reactions

CONCEPT_2_THEME: Social interaction
CONCEPT_2_DESC: Awkward social moment in Discord
CONCEPT_2_HOOKS: Social mishap, community reactions

CONCEPT_3_THEME: Random obsession
CONCEPT_3_DESC: User obsessed with random topic
CONCEPT_3_HOOKS: Unusual interest, dedication

CONCEPT_4_THEME: Personality quirk
CONCEPT_4_DESC: Funny personality trait revealed
CONCEPT_4_HOOKS: Character trait, amusing behavior"""
    
    def _get_fallback_concepts(self) -> List[ContentConcept]:
        """Get hardcoded fallback concepts."""
        return [
            ContentConcept(
                concept_id="fallback_gaming",
                description="Gaming-related embarrassing moment",
                relevance_score=0.7,
                appropriateness_score=1.0,
                server_fit_score=0.6,
                reasoning="Fallback gaming concept",
                content_hooks={"theme": "gaming", "hooks": "funny failure"}
            ),
            ContentConcept(
                concept_id="fallback_social",
                description="Social interaction mishap",
                relevance_score=0.6,
                appropriateness_score=1.0,
                server_fit_score=0.7,
                reasoning="Fallback social concept",
                content_hooks={"theme": "social", "hooks": "awkward moment"}
            ),
            ContentConcept(
                concept_id="fallback_hobby",
                description="Obsession with random topic",
                relevance_score=0.5,
                appropriateness_score=1.0,
                server_fit_score=0.5,
                reasoning="Fallback hobby concept",
                content_hooks={"theme": "hobby", "hooks": "obsessive interest"}
            )
        ]
    
    def _get_fallback_plan(self, persona: PersonaType, content_guidelines: Dict[str, Any]) -> ContentPlan:
        """Generate fallback content plan."""
        fallback_concepts = self._get_fallback_concepts()
        
        return ContentPlan(
            selected_concept=fallback_concepts[0] if fallback_concepts else None,
            alternative_concepts=fallback_concepts[1:],
            persona_requirements=self._get_persona_requirements(persona),
            content_guidelines=content_guidelines,
            reasoning="Fallback plan due to planning failure. Using generic concepts."
        )