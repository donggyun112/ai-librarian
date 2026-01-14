"""Data models for generation layer.

Contains data classes for query optimization, LLM responses, and generated outputs.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.rag.retrieval import ExpandedResult


@dataclass
class OptimizedQuery:
    """Optimized query from QueryOptimizer.

    Attributes:
        original: Original user query
        keywords: Extracted search keywords
        rewritten: Search-optimized query string
        view_hint: Suggested view filter ("code", "text", etc.)
        language_hint: Suggested language filter ("python", "javascript", etc.)
    """

    original: str
    keywords: List[str]
    rewritten: str
    view_hint: Optional[str] = None
    language_hint: Optional[str] = None


@dataclass
class LLMResponse:
    """Response from LLM generation.

    Attributes:
        content: Generated text content
        model: Model name used for generation
        usage: Optional token usage information
    """

    content: str
    model: str
    usage: Optional[dict] = None


@dataclass
class GeneratedResponse:
    """Complete RAG response with source attribution.

    Attributes:
        query: Original user query
        answer: Generated answer text
        sources: Retrieved context sources
        model: LLM model used
        optimized_query: Query optimization result (if used)
        timestamp: Generation timestamp
    """

    query: str
    answer: str
    sources: List[ExpandedResult]
    model: str
    optimized_query: Optional[OptimizedQuery] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def format_with_sources(self) -> str:
        """Format response with source attribution.

        Returns:
            Formatted string with answer and source list
        """
        lines = [self.answer, "", "---", "Sources:"]
        for i, expanded in enumerate(self.sources, 1):
            source = expanded.result.metadata.get("source", "unknown")
            view = expanded.result.view.value
            similarity = f"{expanded.result.similarity:.2f}"
            lines.append(f"  [{i}] {source} ({view}, sim: {similarity})")
        return "\n".join(lines)


@dataclass
class ConversationTurn:
    """Single turn in a conversation."""

    query: str
    response: GeneratedResponse


@dataclass
class Conversation:
    """Multi-turn conversation state.

    Attributes:
        turns: List of conversation turns
        max_history: Maximum turns to keep in history
    """

    turns: List[ConversationTurn] = field(default_factory=list)
    max_history: int = 5

    def add_turn(self, query: str, response: GeneratedResponse) -> None:
        """Add a turn, maintaining max history."""
        self.turns.append(ConversationTurn(query=query, response=response))
        if len(self.turns) > self.max_history:
            self.turns = self.turns[-self.max_history :]

    def get_history_context(self) -> str:
        """Format conversation history for context.

        Returns:
            Formatted string of recent conversation turns
        """
        if not self.turns:
            return ""

        lines = ["Previous conversation:"]
        for turn in self.turns[-3:]:  # Last 3 turns
            lines.append(f"User: {turn.query}")
            lines.append(f"Assistant: {turn.response.answer[:200]}...")
        return "\n".join(lines)

    def clear(self) -> None:
        """Clear conversation history."""
        self.turns = []


__all__ = [
    "OptimizedQuery",
    "LLMResponse",
    "GeneratedResponse",
    "ConversationTurn",
    "Conversation",
]
