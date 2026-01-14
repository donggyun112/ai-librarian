"""Response formatting for CLI output.

Formats search results and other outputs for human-readable display.
"""

import json
from typing import List

from src.rag.retrieval.dto import ExpandedResult


class ResponseFormatter:
    """Formats CLI responses for display."""

    @staticmethod
    def format_search_results_text(
        results: List[ExpandedResult],
        show_context: bool = True,
    ) -> str:
        """Format search results as human-readable text.

        Args:
            results: List of search results with context
            show_context: Whether to include parent context

        Returns:
            Formatted text string
        """
        if not results:
            return "[No results found]"

        lines = []
        lines.append(f"[Found {len(results)} results]\n")

        for i, expanded in enumerate(results, 1):
            result = expanded.result
            lines.append("=" * 80)
            lines.append(f"Result {i}/{len(results)}")
            lines.append(f"Similarity: {result.similarity:.4f}")
            lines.append(f"View: {result.view.value}")
            if result.language:
                lines.append(f"Language: {result.language}")
            lines.append(f"Parent ID: {result.parent_id}")
            lines.append(f"Fragment ID: {result.fragment_id}")
            lines.append("-" * 80)
            lines.append("Content:")
            lines.append(result.content)

            if show_context and expanded.parent_content:
                lines.append("-" * 80)
                lines.append("Parent Context:")
                lines.append(
                    expanded.parent_content[:500] + "..."
                    if len(expanded.parent_content) > 500
                    else expanded.parent_content
                )

            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def format_search_results_json(
        results: List[ExpandedResult],
        show_context: bool = True,
    ) -> str:
        """Format search results as JSON.

        Args:
            results: List of search results with context
            show_context: Whether to include parent context

        Returns:
            JSON string
        """
        output = []
        for expanded in results:
            result = expanded.result
            item = {
                "fragment_id": result.fragment_id,
                "parent_id": result.parent_id,
                "view": result.view.value,
                "language": result.language,
                "content": result.content,
                "similarity": result.similarity,
                "metadata": result.metadata,
            }
            if show_context:
                item["parent_content"] = expanded.parent_content
                item["parent_metadata"] = expanded.parent_metadata

            output.append(item)

        return json.dumps(output, indent=2, ensure_ascii=False)

    @staticmethod
    def format_ingest_summary(
        total_documents: int,
        total_concepts: int,
        total_fragments: int,
        total_embeddings: int,
    ) -> str:
        """Format ingestion summary as text.

        Args:
            total_documents: Number of documents processed
            total_concepts: Number of concepts created
            total_fragments: Number of fragments created
            total_embeddings: Number of embeddings generated

        Returns:
            Formatted summary string
        """
        lines = []
        lines.append("=" * 80)
        lines.append("Ingestion Summary")
        lines.append("=" * 80)
        lines.append(f"Documents processed: {total_documents}")
        lines.append(f"Concepts created:    {total_concepts}")
        lines.append(f"Fragments created:   {total_fragments}")
        lines.append(f"Embeddings generated: {total_embeddings}")
        lines.append("=" * 80)
        return "\n".join(lines)

    @staticmethod
    def format_error(error: Exception) -> str:
        """Format error message.

        Args:
            error: Exception to format

        Returns:
            Formatted error string
        """
        return f"[ERROR] {type(error).__name__}: {str(error)}"


__all__ = ["ResponseFormatter"]
