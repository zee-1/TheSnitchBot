"""
Leak Writer - CoT Step 3
Writes final leak content based on selected concept and persona requirements.
"""

from typing import Dict, Any
import random
from .base import BaseLeakChain, ContentPlan, LeakContent
from src.models.server import PersonaType
from src.core.logging import get_logger
from src.ai.llm_client import TaskType

logger = get_logger(__name__)


class LeakWriter(BaseLeakChain):
    """Writes final leak content based on planned concept."""
    
    task_type = TaskType.FINAL  # Final content generation
    
    async def process(self, *args, **kwargs) -> LeakContent:
        """Process method required by BaseLeakChain interface."""
        # Delegate to write_leak method
        return await self.write_leak(*args, **kwargs)
    
    async def write_leak(
        self,
        content_plan: ContentPlan,
        persona: PersonaType,
        format_requirements: Dict[str, Any],
        target_name: str = "User"
    ) -> LeakContent:
        """
        Write final leak content based on content plan.
        
        Args:
            content_plan: Selected content concept and plan
            persona: Bot persona for writing style
            format_requirements: Format and length requirements
            target_name: Name of the target user
            
        Returns:
            LeakContent with final formatted content
        """
        try:
            self.logger.info(f"Starting leak writing for {target_name}")
            
            if not content_plan.selected_concept:
                return self._get_fallback_content(target_name, persona)
            
            # Generate main content using AI
            main_content = await self._generate_main_content(
                content_plan, persona, target_name, format_requirements
            )
            
            # Generate reliability percentage
            reliability_percentage = self._generate_reliability_percentage()
            
            # Generate source attribution
            source_attribution = self._generate_source_attribution(persona)
            
            # Generate writing reasoning
            reasoning = self._generate_writing_reasoning(
                content_plan, main_content, reliability_percentage
            )
            
            leak_content = LeakContent(
                content=main_content,
                reliability_percentage=reliability_percentage,
                source_attribution=source_attribution,
                content_length=len(main_content),
                reasoning=reasoning
            )
            
            self.logger.info(f"Leak writing completed. Content length: {len(main_content)} characters")
            return leak_content
            
        except Exception as e:
            self.logger.error(f"Leak writing failed: {e}")
            return self._get_fallback_content(target_name, persona)
    
    async def _generate_main_content(
        self,
        content_plan: ContentPlan,
        persona: PersonaType,
        target_name: str,
        format_requirements: Dict[str, Any]
    ) -> str:
        """Generate main leak content using AI."""
        
        concept = content_plan.selected_concept
        persona_req = content_plan.persona_requirements
        max_length = persona_req.get("max_length", 150)
        
        prompt = f"""Write a humorous, harmless "leak" about {target_name} using the following specifications:

CONTENT CONCEPT:
- Theme: {concept.content_hooks.get('theme', 'general')}
- Description: {concept.description}
- Content hooks: {concept.content_hooks.get('hooks', 'general humor')}

PERSONA REQUIREMENTS:
- Tone: {persona_req.get('tone', 'neutral')}
- Style: {persona_req.get('style', 'general')}
- Suggested phrases: {', '.join(persona_req.get('phrases', []))}
- Emojis to use: {', '.join(persona_req.get('emojis', []))}

CONTENT GUIDELINES:
- Maximum length: {max_length} characters
- Must be completely harmless and appropriate for all audiences
- Focus on embarrassing but innocent scenarios
- Include specific details that make it feel "leaked" but obviously fake
- Make it server-relevant and community-friendly
- Use natural language and current slang where appropriate

WRITING STYLE FOR {persona.value if hasattr(persona, 'value') else str(persona)}:
{self._get_persona_style_guide(persona)}

Write ONLY the leak content itself. Do not include explanations or metadata."""
        
        try:
            content = await self._safe_ai_completion(
                prompt=prompt,
                temperature=0.9,
                max_tokens=2048,
                fallback_response=self._get_fallback_content_text(target_name, persona)
            )
            
            # Clean and validate content
            content = self._clean_content(content, max_length)
            
            return content
            
        except Exception as e:
            self.logger.warning(f"AI content generation failed: {e}")
            return self._get_fallback_content_text(target_name, persona)
    
    def _get_persona_style_guide(self, persona) -> str:
        """Get detailed style guide for each persona."""
        
        # Handle both enum and string cases
        if hasattr(persona, 'value'):
            persona_key = persona
        else:
            # Convert string to enum if needed
            try:
                from src.models.server import PersonaType
                persona_key = PersonaType(str(persona))
            except (ValueError, AttributeError):
                # Fallback for unknown persona
                return "Write in a neutral, friendly tone with light humor."
        
        style_guides = {
            PersonaType.SASSY_REPORTER: """
Write like a sassy gossip columnist who knows all the tea. Use phrases like "Tea has been SPILLED!" 
and "No cap, bestie!" Include emojis like ✨💅☕👀. Be playful and slightly dramatic but never mean.
Example tone: "BREAKING: Sources confirm [target] was caught doing [embarrassing thing]. The secondhand 
embarrassment is REAL! 💅✨"
            """.strip(),
            
            PersonaType.INVESTIGATIVE_JOURNALIST: """
Write like a serious news reporter uncovering important intel. Use professional language with phrases 
like "Sources confirm" and "Investigation reveals." Include emojis sparingly: 📊🔍📋. 
Maintain journalistic credibility while being obviously satirical.
Example tone: "CLASSIFIED REPORT: Multiple witnesses confirm [target] has been conducting secret 
operations involving [silly activity]. Further investigation pending."
            """.strip(),
            
            PersonaType.GOSSIP_COLUMNIST: """
Write like a dramatic tabloid gossip columnist. Use phrases like "Darlings!" and "Exclusively yours!" 
Include glamorous emojis: 💋👑✨🍵. Be theatrical and over-the-top.
Example tone: "Darlings! 💅 The gossip desk has EXCLUSIVELY learned that [target] has been secretly 
[embarrassing activity]. The drama! ✨"
            """.strip(),
            
            PersonaType.SPORTS_COMMENTATOR: """
Write like an energetic sports announcer calling a game. Use ALL CAPS for excitement and phrases 
like "LADIES AND GENTLEMEN!" and "WHAT A PLAY!" Include sports emojis: 🏆📣🎯💪.
Example tone: "LADIES AND GENTLEMEN! [Target] with the CHAMPIONSHIP MOVE! Sources confirm they've 
been [silly activity]! THE CROWD GOES WILD! 🏆"
            """.strip(),
            
            PersonaType.CONSPIRACY_THEORIST: """
Write like someone uncovering a grand conspiracy. Use phrases like "WAKE UP SHEEPLE!" and 
"The truth is out there!" Include mysterious emojis: 👁️🔍🎭🛸. Be dramatically paranoid about silly things.
Example tone: "WAKE UP SHEEPLE! 👁️ [Target] is CLEARLY part of the [silly thing] ILLUMINATI! 
The evidence is EVERYWHERE! COINCIDENCE? I THINK NOT!"
            """.strip(),
            
            PersonaType.WEATHER_ANCHOR: """
Write like a professional weather reporter giving forecasts. Use meteorological language and phrases 
like "Community forecast" and "Current conditions." Include weather emojis: 🌤️📡🌪️.
Example tone: "Community forecast shows [target] with a high probability of [silly activity]. 
Current conditions suggest continued [embarrassing behavior]. 🌤️"
            """.strip()
        }
        
        return style_guides.get(persona_key, "Write in a neutral, friendly tone with light humor.")
    
    def _clean_content(self, content: str, max_length: int) -> str:
        """Clean and validate generated content."""
        
        # Remove any quotes or metadata that might have been included
        content = content.strip().strip('"\'`')
        
        # Remove any leading "Leak:" or similar prefixes
        prefixes_to_remove = ['leak:', 'content:', 'result:', 'output:']
        content_lower = content.lower()
        for prefix in prefixes_to_remove:
            if content_lower.startswith(prefix):
                content = content[len(prefix):].strip()
                break
        
        # Truncate if too long
        if len(content) > max_length:
            # Try to truncate at a sentence boundary
            sentences = content.split('. ')
            truncated = sentences[0]
            for sentence in sentences[1:]:
                if len(truncated + '. ' + sentence) <= max_length - 3:
                    truncated += '. ' + sentence
                else:
                    break
            content = truncated + ('...' if len(truncated) < len(content) else '')
        
        # Ensure it's not empty
        if not content or len(content.strip()) < 10:
            return "Sources report suspicious activity involving snacks and questionable life choices. 🤐"
        
        return content
    
    def _generate_reliability_percentage(self) -> int:
        """Generate a humorous reliability percentage."""
        
        # Generate weighted towards "suspicious" but not too high percentages
        ranges = [
            (range(12, 30), 0.3),   # Very suspicious
            (range(30, 50), 0.4),   # Moderately suspicious  
            (range(50, 75), 0.25),  # Somewhat suspicious
            (range(75, 99), 0.05)   # Too reliable to be fun
        ]
        
        # Choose range based on weights
        rand = random.random()
        cumulative = 0
        
        for r, weight in ranges:
            cumulative += weight
            if rand <= cumulative:
                return random.choice(r)
        
        return random.randint(23, 67)  # Fallback
    
    def _generate_source_attribution(self, persona: PersonaType) -> str:
        """Generate persona-appropriate source attribution."""
        
        source_options = {
            PersonaType.SASSY_REPORTER: [
                "Anonymous Bestie",
                "Tea Spillers Anonymous", 
                "Someone Who Knows Someone",
                "The Gossip Network",
                "Confidential Sass Squad"
            ],
            PersonaType.INVESTIGATIVE_JOURNALIST: [
                "Anonymous Whistleblower",
                "Classified Intelligence",
                "Deep Throat 2.0",
                "Investigative Sources",
                "Protected Witness"
            ],
            PersonaType.GOSSIP_COLUMNIST: [
                "Little Bird in Designer Shoes",
                "Fabulous Insider",
                "Glamorous Informant",
                "Society Circle Source",
                "Diamond-Wearing Witness"
            ],
            PersonaType.SPORTS_COMMENTATOR: [
                "Locker Room Leak",
                "Stadium Insider",
                "Championship Source",
                "Athletic Intelligence",
                "Game Film Evidence"
            ],
            PersonaType.CONSPIRACY_THEORIST: [
                "Deep State Operative",
                "Underground Network",
                "Shadow Government Files",
                "Illuminati Defector",
                "Anonymous Truth Seeker"
            ],
            PersonaType.WEATHER_ANCHOR: [
                "Meteorological Intel",
                "Weather Station Alpha",
                "Atmospheric Conditions Report",
                "Climate Data Source",
                "Environmental Monitoring"
            ]
        }
        
        options = source_options.get(persona, ["Anonymous Source", "Confidential Tipster"])
        return random.choice(options)
    
    def _generate_writing_reasoning(
        self,
        content_plan: ContentPlan,
        final_content: str,
        reliability_percentage: int
    ) -> str:
        """Generate reasoning summary for the writing process."""
        
        concept = content_plan.selected_concept
        
        reasoning = f"""Leak Writing Process:

Selected Concept: {concept.concept_id}
Theme: {concept.content_hooks.get('theme', 'general')}
Final Content Length: {len(final_content)} characters
Reliability Score: {reliability_percentage}%

Writing Strategy: Focused on {concept.content_hooks.get('theme', 'general')} theme with 
persona-appropriate tone and style. Content designed to be obviously satirical while 
maintaining community-friendly humor."""
        
        return reasoning
    
    def _get_fallback_content_text(self, target_name: str, persona) -> str:
        """Generate fallback content when AI fails."""
        
        # Handle both enum and string cases
        if hasattr(persona, 'value'):
            persona_key = persona
        else:
            # Convert string to enum if needed
            try:
                from src.models.server import PersonaType
                persona_key = PersonaType(str(persona))
            except (ValueError, AttributeError):
                # Use default persona for fallback
                from src.models.server import PersonaType
                persona_key = PersonaType.SASSY_REPORTER
        
        fallback_templates = {
            PersonaType.SASSY_REPORTER: [
                f"Tea Alert! ☕ Sources say {target_name} was caught having STRONG opinions about pineapple on pizza. The dedication to controversial food takes is real! 💅✨",
                f"BREAKING: {target_name} allegedly spent 20 minutes explaining why their favorite show is actually underrated. No cap, the passion is admirable! 👀☕"
            ],
            PersonaType.INVESTIGATIVE_JOURNALIST: [
                f"CLASSIFIED REPORT: Investigation reveals {target_name} maintains detailed knowledge of obscure internet memes from 2019. Sources remain anonymous for safety reasons.",
                f"Breaking investigation: Multiple witnesses confirm {target_name} has been conducting secret research on the optimal way to organize their digital music library."
            ],
            PersonaType.GOSSIP_COLUMNIST: [
                f"Darlings! 💅 The gossip desk exclusively reports {target_name} was spotted passionately defending their favorite fictional character in a heated discussion. The drama! ✨",
                f"EXCLUSIVE: Fashion sources confirm {target_name} has strong opinions about sock and sandal combinations. The style choices! 👑💋"
            ],
            PersonaType.SPORTS_COMMENTATOR: [
                f"LADIES AND GENTLEMEN! {target_name.upper()} WITH THE CHAMPIONSHIP DEDICATION! Sources confirm they've been perfecting their signature snack combination! WHAT COMMITMENT! 🏆📣",
                f"BREAKING SPORTS NEWS! {target_name} has been caught practicing their victory dance for completing daily tasks! THE ENERGY IS UNMATCHED! 💪🎯"
            ],
            PersonaType.CONSPIRACY_THEORIST: [
                f"WAKE UP SHEEPLE! 👁️ {target_name} is CLEARLY part of the Secret Society of People Who Remember Obscure Song Lyrics! The evidence is in their flawless karaoke performances! 🎭",
                f"THE TRUTH IS OUT THERE! Deep sources reveal {target_name} has insider knowledge about which snacks pair best with different moods! COINCIDENCE? I THINK NOT! 🛸"
            ],
            PersonaType.WEATHER_ANCHOR: [
                f"Community forecast shows {target_name} with a high probability of strong opinions about optimal room temperature. Current conditions suggest continued thermostat advocacy. 🌤️",
                f"Weather update: {target_name} demonstrates consistent patterns of having the perfect playlist for every occasion. Forecast calls for continued musical coordination. 📡"
            ]
        }
        
        templates = fallback_templates.get(persona_key, [
            f"Sources report {target_name} has been spotted having passionate discussions about their favorite comfort food combinations.",
            f"Anonymous tip confirms {target_name} maintains surprisingly strong opinions about proper coffee brewing methods."
        ])
        
        return random.choice(templates)
    
    def _get_fallback_content(self, target_name: str, persona) -> LeakContent:
        """Generate complete fallback content when everything fails."""
        
        content_text = self._get_fallback_content_text(target_name, persona)
        
        return LeakContent(
            content=content_text,
            reliability_percentage=random.randint(15, 55),
            source_attribution="Anonymous Backup Source",
            content_length=len(content_text),
            reasoning="Fallback content generation due to AI failure. Using persona-specific templates."
        )