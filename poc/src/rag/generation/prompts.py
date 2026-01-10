"""Prompt template management for RAG generation.

Handles system prompts, context assembly, and RAG prompt formatting.
"""

from dataclasses import dataclass
from typing import List

from retrieval import ExpandedResult


@dataclass
class PromptContext:
    """Assembled context for LLM prompt.

    Attributes:
        query: User query
        retrieved_content: Formatted context from search results
        source_citations: List of source citations
    """

    query: str
    retrieved_content: str
    source_citations: List[str]


class PromptTemplate:
    """Manages prompt templates for RAG generation.

    Handles:
    - System prompt for RAG behavior
    - Context assembly from search results
    - Final prompt formatting
    """

    SYSTEM_PROMPT = """You are a helpful assistant that answers questions based on the provided context.

RULES:
1. Only answer based on the provided context - do not use external knowledge
2. If the context doesn't contain enough information, clearly say "I don't have enough information to answer this question based on the provided context"
3. Always cite sources using [Source N] format when referencing specific information
4. Be concise but comprehensive
5. For code questions, include relevant code snippets from the context
6. If the question is in Korean, answer in Korean. If in English, answer in English."""

    RAG_TEMPLATE = """Context:
{context}

---
Question: {query}

Answer based on the context above. Include source citations [Source N] where appropriate."""

    KEYWORD_EXTRACTION_PROMPT = """Extract 3-5 key search terms from this question.
Return ONLY a JSON object in this exact format, nothing else:
{{"keywords": ["term1", "term2", "term3"], "view": "code|text|null", "language": "python|javascript|null"}}

Rules:
- keywords: Important technical terms, API names, function names, concepts
- view: "code" if asking about code/implementation, "text" if asking about concepts/explanations, null if unclear
- language: Programming language if specified or implied, null otherwise

Question: {query}"""

    @classmethod
    def build_context(cls, results: List[ExpandedResult]) -> PromptContext:
        """Build prompt context from expanded search results.

        Args:
            results: Search results with parent context

        Returns:
            PromptContext with formatted content and citations
        """
        context_parts = []
        citations = []

        for i, expanded in enumerate(results, 1):
            result = expanded.result

            # Source citation
            source = result.metadata.get("source", "unknown")
            citations.append(f"[{i}] {source}")

            # Build context entry
            entry = f"[Source {i}: {source}]\n"

            # Add parent context if available (broader context)
            if expanded.parent_content:
                # Truncate parent content to avoid overwhelming
                parent_preview = expanded.parent_content[:800]
                if len(expanded.parent_content) > 800:
                    parent_preview += "..."
                entry += f"Context:\n{parent_preview}\n\n"

            # Add matched content (specific match)
            view_label = result.view.value.upper()
            if result.language:
                view_label += f" ({result.language})"
            entry += f"Matched Content [{view_label}]:\n{result.content}\n"

            # Add related images if any
            related_images = getattr(expanded, 'related_images', None)
            if related_images:
                entry += "\nRelated Images:\n"
                for img in related_images:
                    entry += f"  - {getattr(img, 'alt_text', 'Image') or 'Image'}: {getattr(img, 'image_path', 'N/A')}\n"


            context_parts.append(entry)

        return PromptContext(
            query="",  # Set by caller
            retrieved_content="\n" + ("=" * 40 + "\n").join([""] + context_parts),
            source_citations=citations,
        )

    @classmethod
    def format_rag_prompt(cls, query: str, context: PromptContext) -> str:
        """Format the final RAG prompt.

        Args:
            query: User query
            context: Assembled prompt context

        Returns:
            Formatted prompt string
        """
        return cls.RAG_TEMPLATE.format(
            context=context.retrieved_content,
            query=query,
        )

    @classmethod
    def format_keyword_prompt(cls, query: str) -> str:
        """Format prompt for keyword extraction.

        Args:
            query: User query

        Returns:
            Formatted prompt for keyword extraction
        """
        return cls.KEYWORD_EXTRACTION_PROMPT.format(query=query)


__all__ = ["PromptTemplate", "PromptContext"]
