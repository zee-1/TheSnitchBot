# Chain of Thoughts Implementation Plan for Leak Command

## Executive Summary

This document outlines a comprehensive plan to implement Chain of Thoughts (CoT) reasoning in the leak command to improve relevance and introduce randomized user selection. The current implementation suffers from irrelevant content generation and predictable user targeting patterns.

## Current State Analysis

### Existing Leak Command Structure
- Location: `src/discord_bot/commands/leak.py`
- Current AI Generation Method: Single prompt with context injection
- User Selection: Currently selects from all active users randomly (good)
- Content Quality Issues:
  - Lacks structured reasoning for relevance
  - Generic responses not tailored to server context
  - No multi-step thinking process for content generation

### Current Prompt Strategy Problems
1. **Single-shot prompting**: The current 220-line prompt tries to do everything at once
2. **Context overload**: Too much information passed without structured processing
3. **No reasoning chain**: AI jumps directly to final output without intermediate steps
4. **Relevance filtering**: No mechanism to ensure content matches server culture

## Chain of Thoughts (CoT) Methodology

### What is Chain of Thoughts?
CoT is an AI reasoning technique where complex problems are broken down into intermediate reasoning steps, allowing the model to:
- Show its working process
- Make more logical connections
- Produce more accurate and relevant outputs
- Allow for debugging and improvement of reasoning

### CoT for Leak Command Application
Instead of one massive prompt, we'll implement a 3-step reasoning chain:

1. **Analysis Step**: Understand server context and target user
2. **Planning Step**: Generate relevant leak concepts with reasoning
3. **Execution Step**: Craft the final humorous content

## Implementation Plan

### Phase 1: Core CoT Architecture

#### 1.1 Create CoT Chain Classes
Create new chain classes in `src/ai/chains/` directory:

```
src/ai/chains/leak_chains/
├── __init__.py
├── context_analyzer.py     # Step 1: Analyze server context
├── content_planner.py      # Step 2: Plan relevant content
└── leak_writer.py          # Step 3: Write final leak
```

#### 1.2 Context Analyzer Chain
**Purpose**: Analyze server culture, user patterns, and recent activity

**Inputs**:
- Target user's recent messages (last 10)
- Server conversation patterns
- Active topics and themes
- Server persona configuration

**Outputs**:
- User communication style analysis
- Active conversation topics
- Server culture assessment
- Relevance factors for content generation

**Example Reasoning Process**:
```
Step 1: Analyzing target user's messages...
- User frequently mentions gaming topics (5/10 messages)
- Uses casual/friendly tone
- Often interacts with specific users: [UserA, UserB]
- Recent activity focused on: [specific game/topic]

Step 2: Analyzing server context...
- Server culture: Gaming-focused community
- Active topics: [Topic1, Topic2, Topic3]
- Communication style: Casual, meme-heavy
- Persona setting: Sassy Reporter

Step 3: Determining relevance factors...
- Gaming content will resonate (HIGH)
- References to UserA/UserB interactions (MEDIUM)
- Current trending topics match user interests (HIGH)
```

#### 1.3 Content Planner Chain
**Purpose**: Generate multiple content concepts with reasoning

**Inputs**:
- Context analysis from Step 1
- Server persona requirements
- Content guidelines and restrictions

**Outputs**:
- 3-5 leak concept ideas with relevance scores
- Reasoning for each concept's appropriateness
- Selected best concept with justification

**Example Reasoning Process**:
```
Based on analysis, generating leak concepts:

Concept 1: Gaming-related embarrassment
- Relevance: HIGH (matches user's main interest)
- Appropriateness: HIGH (harmless gaming humor)
- Server fit: HIGH (gaming community)
- Reasoning: User frequently discusses gaming, server appreciates gaming humor

Concept 2: Interaction with UserA
- Relevance: MEDIUM (recent interactions observed)
- Appropriateness: HIGH (friendly banter)
- Server fit: MEDIUM (community knows these users)
- Reasoning: Recent friendly exchanges provide safe humor material

Concept 3: Random food obsession
- Relevance: LOW (no food discussion in recent messages)
- Appropriateness: HIGH (harmless)
- Server fit: LOW (not relevant to server context)
- Reasoning: Generic template, lacks personalization

Selected Concept: Concept 1 (Gaming-related embarrassment)
Justification: Highest relevance score, matches user interests and server culture
```

#### 1.4 Leak Writer Chain
**Purpose**: Craft the final humorous content based on selected concept

**Inputs**:
- Selected concept from Step 2
- Persona-specific writing style requirements
- Content length and format guidelines

**Outputs**:
- Final formatted leak content
- Reliability percentage
- Source attribution

### Phase 2: Random User Selection Enhancement

#### 2.1 Current User Selection Analysis
The current implementation already selects users randomly from active users, which is good. However, we can improve the selection criteria:

#### 2.2 Enhanced Random Selection Algorithm
```python
class EnhancedUserSelector:
    def __init__(self, min_recent_messages=2, exclude_recent_targets=True):
        self.min_recent_messages = min_recent_messages
        self.exclude_recent_targets = exclude_recent_targets
        
    async def select_random_users(self, recent_messages, command_user_id, server_id):
        """
        Select random users with improved criteria
        """
        # Step 1: Build candidate pool
        candidates = self._build_candidate_pool(recent_messages, command_user_id)
        
        # Step 2: Apply filters
        filtered_candidates = self._apply_selection_filters(candidates, server_id)
        
        # Step 3: Random selection
        if len(filtered_candidates) < 10:
            return random.sample(filtered_candidates, len(filtered_candidates))
        else:
            return random.sample(filtered_candidates, 10)
    
    def _build_candidate_pool(self, recent_messages, command_user_id):
        """Build pool of potential targets"""
        user_activity = {}
        
        for msg in recent_messages:
            if (not msg.author.bot and 
                str(msg.author.id) != command_user_id and
                len(msg.content.strip()) > 10):  # Exclude very short messages
                
                user_id = str(msg.author.id)
                if user_id not in user_activity:
                    user_activity[user_id] = {
                        'message_count': 0,
                        'user_obj': msg.author,
                        'recent_messages': []
                    }
                
                user_activity[user_id]['message_count'] += 1
                user_activity[user_id]['recent_messages'].append(msg.content)
        
        # Filter users with minimum activity
        candidates = [
            user_data for user_data in user_activity.values()
            if user_data['message_count'] >= self.min_recent_messages
        ]
        
        return candidates
    
    def _apply_selection_filters(self, candidates, server_id):
        """Apply additional filtering logic"""
        # Could add filters like:
        # - Exclude users targeted in last N uses
        # - Prefer users with moderate activity (not too high, not too low)
        # - Consider time since last message
        
        return candidates
```

### Phase 3: Integration and Testing

#### 3.1 Modify Existing Leak Command
Update `src/discord_bot/commands/leak.py` to use the new CoT chains:

```python
async def _generate_ai_leak_with_cot(self, target_name: str, target_user_id: str, ctx: CommandContext, recent_messages: list) -> str:
    """Generate AI-powered leak using Chain of Thoughts approach."""
    
    # Step 1: Context Analysis
    context_analyzer = ContextAnalyzer(ctx.ai_service)
    context_analysis = await context_analyzer.analyze_context(
        target_user_id=target_user_id,
        target_name=target_name,
        recent_messages=recent_messages,
        server_config=ctx.server_config
    )
    
    # Step 2: Content Planning
    content_planner = ContentPlanner(ctx.ai_service)
    content_plan = await content_planner.plan_content(
        context_analysis=context_analysis,
        persona=ctx.server_config.persona,
        content_guidelines=self._get_content_guidelines()
    )
    
    # Step 3: Final Content Writing
    leak_writer = LeakWriter(ctx.ai_service)
    final_content = await leak_writer.write_leak(
        content_plan=content_plan,
        persona=ctx.server_config.persona,
        format_requirements=self._get_format_requirements()
    )
    
    return final_content
```

#### 3.2 Testing Strategy
1. **Unit Tests**: Test each CoT chain independently
2. **Integration Tests**: Test the full chain together
3. **A/B Testing**: Compare old vs new approach
4. **Quality Metrics**: Track relevance improvements

### Phase 4: Monitoring and Optimization

#### 4.1 Metrics to Track
- **Relevance Score**: User reactions and engagement with leaks
- **Response Time**: Performance impact of multi-step process
- **Error Rates**: Chain failure points
- **User Satisfaction**: Feedback and usage patterns

#### 4.2 Optimization Opportunities
- **Caching**: Cache context analysis for repeated users
- **Parallel Processing**: Run some chain steps in parallel
- **Response Recycling**: Reuse successful reasoning patterns

## Technical Implementation Details

### File Structure Changes
```
src/ai/chains/leak_chains/
├── __init__.py
├── base.py                 # Base class for leak chains
├── context_analyzer.py     # CoT Step 1
├── content_planner.py      # CoT Step 2
├── leak_writer.py          # CoT Step 3
└── user_selector.py        # Enhanced user selection

src/discord_bot/commands/
└── leak.py                 # Updated to use CoT chains

tests/ai/chains/leak_chains/
├── test_context_analyzer.py
├── test_content_planner.py
├── test_leak_writer.py
└── test_integration.py
```

### Configuration Updates
Add CoT-specific settings to server configuration:
```python
# In ServerConfig model
class LeakCommandConfig:
    enable_cot: bool = True
    cot_timeout_seconds: int = 30
    max_context_messages: int = 50
    min_user_activity_threshold: int = 2
    exclude_recent_targets_hours: int = 24
```

### Error Handling Strategy
- **Chain Failure Fallback**: If any CoT step fails, fall back to current implementation
- **Timeout Protection**: Each chain step has timeout limits
- **Graceful Degradation**: Reduce complexity if performance suffers

## Expected Benefits

1. **Improved Relevance**: Multi-step reasoning ensures content matches server culture
2. **Better Personalization**: Dedicated analysis step provides deeper user context
3. **Debugging Capability**: Can inspect reasoning at each step
4. **Scalable Quality**: Framework can be improved and extended
5. **Reduced Generic Content**: Structured planning reduces template-based responses

## Implementation Timeline

- **Week 1**: Create base CoT infrastructure and Context Analyzer
- **Week 2**: Implement Content Planner and Leak Writer chains  
- **Week 3**: Integrate with existing leak command and test
- **Week 4**: A/B testing, optimization, and documentation

## Risk Mitigation

1. **Performance Impact**: Implement caching and timeouts
2. **Increased Complexity**: Maintain fallback to current system
3. **AI API Costs**: Monitor token usage and optimize prompts
4. **Quality Regression**: Implement quality metrics and monitoring

This plan provides a comprehensive approach to implementing Chain of Thoughts reasoning in the leak command while maintaining the random user selection approach and improving overall content relevance and quality.