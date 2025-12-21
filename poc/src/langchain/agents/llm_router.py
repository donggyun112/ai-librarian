"""
LLM-based autonomous router that selects the best tool for a given question.

This router uses an LLM to analyze the question and decide which tool to use,
providing reasoning for its decision.
"""

from typing import Dict, Any, Optional, List
from enum import Enum
from pydantic import BaseModel, Field
import logging
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

from ...models.question import Question, QuestionType

logger = logging.getLogger(__name__)


class ToolChoice(str, Enum):
    """Available tools for answering questions."""

    VECTOR_DB = "vector_db"
    WEB_SEARCH = "web_search"
    LLM_DIRECT = "llm_direct"
    HYBRID = "hybrid"  # Use multiple tools


class RouterDecision(BaseModel):
    """LLM router's decision with reasoning."""

    model_config = {"use_enum_values": False}  # Keep enums as enums, not strings

    primary_tool: ToolChoice = Field(
        description="The primary tool to use for answering the question"
    )
    confidence: float = Field(
        description="Confidence score between 0.0 and 1.0",
        ge=0.0,
        le=1.0
    )
    reasoning: str = Field(
        description="Detailed explanation of why this tool was chosen"
    )
    fallback_tool: Optional[ToolChoice] = Field(
        default=None,
        description="Fallback tool to use if primary fails"
    )
    requires_multiple_tools: bool = Field(
        default=False,
        description="Whether this question requires multiple tools (hybrid approach)"
    )
    additional_tools: List[ToolChoice] = Field(
        default_factory=list,
        description="Additional tools to use in hybrid mode"
    )


class LLMRouter:
    """
    LLM-based router that autonomously selects the best tool for a question.

    This router uses an LLM to analyze the question characteristics and
    make an informed decision about which tool to use, with reasoning.
    """

    def __init__(self, openai_api_key: str, model: str = "gpt-4o-mini", temperature: float = 0.0):
        """
        Initialize the LLM router.

        Args:
            openai_api_key: OpenAI API key
            model: LLM model to use for routing decisions
            temperature: Temperature for LLM (0.0 for deterministic)
        """
        # Use structured output
        base_llm = ChatOpenAI(
            api_key=openai_api_key,
            model=model,
            temperature=temperature
        )

        # Create structured output LLM
        self.llm = base_llm.with_structured_output(RouterDecision)

        # Build the routing prompt
        self.prompt = self._build_routing_prompt()

        # Statistics
        self.stats = {
            'total_routings': 0,
            'tool_selections': {
                'vector_db': 0,
                'web_search': 0,
                'llm_direct': 0,
                'hybrid': 0
            },
            'average_confidence': 0.0,
            'routing_history': []
        }

    def _build_routing_prompt(self) -> ChatPromptTemplate:
        """Build the prompt template for routing decisions."""

        system_template = """You are an intelligent routing agent that selects the best tool to answer user questions.

Available Tools:
1. **vector_db**: For specific documents, technical details, and internal knowledge.
2. **web_search**: For recent events (2024+), news, and real-time info.
3. **llm_direct**: For general knowledge, explanations, and creative writing.
4. **hybrid**: ONLY for complex questions requiring multiple distinct sources.

Guidelines:
- Prefer SINGLE tool for speed.
- Use 'web_search' for "latest", "recent", "today", "2024".
- Use 'vector_db' for specific technical terms or "documents".
- Use 'llm_direct' for "explain", "write", "what is".
- Provide clear reasoning."""

        human_template = """Question: {question}

Select the BEST tool. If 'hybrid', specify additional tools.
Explain your reasoning concisely."""

        return ChatPromptTemplate.from_messages([
            ("system", system_template),
            ("human", human_template)
        ])

    def route(self, question: str, context: Optional[Dict[str, Any]] = None) -> RouterDecision:
        """
        Route a question to the most appropriate tool.

        Args:
            question: The question to route
            context: Optional context information

        Returns:
            RouterDecision with the selected tool and reasoning
        """
        start_time = datetime.now()
        logger.info(f"Routing question: {question[:50]}...")

        try:
            # Prepare the prompt
            formatted_prompt = self.prompt.format_messages(question=question)

            # Get LLM decision with structured output
            decision = self.llm.invoke(formatted_prompt)

            # Update statistics
            self._update_stats(decision, datetime.now() - start_time)

            logger.info(
                f"Routing decision: {decision.primary_tool.value} "
                f"(confidence: {decision.confidence:.2f}) - {decision.reasoning[:50]}..."
            )

            return decision

        except Exception as e:
            logger.error(f"Routing failed: {str(e)}")

            # Fallback decision
            fallback = RouterDecision(
                primary_tool=ToolChoice.LLM_DIRECT,
                confidence=0.5,
                reasoning=f"Routing error occurred, falling back to LLM direct: {str(e)}",
                fallback_tool=None,
                requires_multiple_tools=False
            )

            self._update_stats(fallback, datetime.now() - start_time)
            return fallback

    def route_with_reflection(self,
                            question: str,
                            previous_attempts: Optional[List[Dict[str, Any]]] = None) -> RouterDecision:
        """
        Route with reflection on previous attempts.

        This is useful for multi-step reasoning where the agent can learn
        from previous tool executions and adjust its strategy.

        Args:
            question: The question to route
            previous_attempts: List of previous routing attempts and their results

        Returns:
            RouterDecision with refined tool selection
        """
        if not previous_attempts:
            return self.route(question)

        # Build context from previous attempts
        reflection_context = self._build_reflection_context(previous_attempts)

        # Modified prompt with reflection
        reflection_prompt = ChatPromptTemplate.from_messages([
            ("system", self.prompt.messages[0].prompt.template),
            ("human", f"""Question: {question}

Previous Attempts:
{reflection_context}

Based on the previous attempts, select a DIFFERENT tool that might work better.
Explain what went wrong before and why the new tool choice is better.

{self.parser.get_format_instructions()}
""")
        ])

        try:
            formatted_prompt = reflection_prompt.format_messages(question=question)
            response = self.llm.invoke(formatted_prompt)
            decision = self.parser.parse(response.content)

            logger.info(f"Reflection routing: {decision.primary_tool.value} - {decision.reasoning[:50]}...")
            return decision

        except Exception as e:
            logger.error(f"Reflection routing failed: {str(e)}")
            return self.route(question)

    def _build_reflection_context(self, previous_attempts: List[Dict[str, Any]]) -> str:
        """Build context string from previous attempts."""
        context_parts = []

        for i, attempt in enumerate(previous_attempts, 1):
            tool = attempt.get('tool', 'unknown')
            success = attempt.get('success', False)
            result = attempt.get('result', 'No result')

            context_parts.append(
                f"Attempt {i}: Used {tool} - "
                f"{'Success' if success else 'Failed'} - {result}"
            )

        return "\n".join(context_parts)

    def _update_stats(self, decision: RouterDecision, processing_time):
        """Update routing statistics."""
        self.stats['total_routings'] += 1
        self.stats['tool_selections'][decision.primary_tool.value] += 1

        # Update average confidence
        total = self.stats['total_routings']
        current_avg = self.stats['average_confidence']
        self.stats['average_confidence'] = (
            (current_avg * (total - 1) + decision.confidence) / total
        )

        # Keep recent history (last 100)
        self.stats['routing_history'].append({
            'tool': decision.primary_tool.value,
            'confidence': decision.confidence,
            'reasoning': decision.reasoning,
            'timestamp': datetime.now().isoformat(),
            'processing_time_ms': processing_time.total_seconds() * 1000
        })

        if len(self.stats['routing_history']) > 100:
            self.stats['routing_history'].pop(0)

    def get_stats(self) -> Dict[str, Any]:
        """Get routing statistics."""
        return {
            'total_routings': self.stats['total_routings'],
            'tool_selections': self.stats['tool_selections'].copy(),
            'average_confidence': self.stats['average_confidence'],
            'recent_history': self.stats['routing_history'][-10:]  # Last 10
        }

    def reset_stats(self):
        """Reset routing statistics."""
        self.stats = {
            'total_routings': 0,
            'tool_selections': {
                'vector_db': 0,
                'web_search': 0,
                'llm_direct': 0,
                'hybrid': 0
            },
            'average_confidence': 0.0,
            'routing_history': []
        }
        logger.info("Router statistics reset")


def create_llm_router(openai_api_key: str, **kwargs) -> LLMRouter:
    """
    Factory function to create an LLM router.

    Args:
        openai_api_key: OpenAI API key
        **kwargs: Additional arguments for LLMRouter

    Returns:
        Configured LLMRouter instance
    """
    return LLMRouter(openai_api_key=openai_api_key, **kwargs)
