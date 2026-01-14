"""CLI command for vector search.

Usage:
    python -m src.rag.cli.search "python list comprehension" --view code --top-k 5
"""

import argparse
import sys

from src.rag.embedding import EmbeddingProviderFactory
from src.rag.generation import GeminiLLMClient
from src.rag.shared.config import load_config

from .formatters import ResponseFormatter
from .use_cases import SearchUseCase
from .validators import RequestValidator, ValidationError


def main(args: argparse.Namespace) -> int:
    """Execute search command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    try:
        # Load configuration
        config = load_config()

        # Validate query
        RequestValidator.validate_query(args.query)
        if args.view:
            RequestValidator.validate_view(args.view)
        if args.top_k:
            RequestValidator.validate_top_k(args.top_k)

        # Create embedding client
        embeddings_client = EmbeddingProviderFactory.create(config)

        # Create LLM client for query optimization (if --optimize flag)
        llm_client = None
        if getattr(args, "optimize", False):
            try:
                llm_client = GeminiLLMClient()
                print("[search] Query optimization enabled")
            except Exception as e:
                print(f"[search] Query optimization disabled: {e}")

        # Execute search use case
        use_case = SearchUseCase(embeddings_client, config, llm_client=llm_client)
        results = use_case.execute(
            query=args.query,
            view=args.view,
            language=args.language,
            top_k=args.top_k or 10,
            expand_context=not args.no_context,
            optimize_query=llm_client is not None,
        )

        # Format and display results
        if args.json:
            output = ResponseFormatter.format_search_results_json(
                results,
                show_context=not args.no_context,
            )
        else:
            output = ResponseFormatter.format_search_results_text(
                results,
                show_context=not args.no_context,
            )

        print(output)
        return 0

    except ValidationError as e:
        print(ResponseFormatter.format_error(e))
        return 1
    except Exception as e:
        print(ResponseFormatter.format_error(e))
        return 2


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for search command.

    Returns:
        Configured ArgumentParser
    """
    parser = argparse.ArgumentParser(
        description="Search OCR Vector DB using vector similarity",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic search
  python -m src.rag.cli.search "python list comprehension"

  # Search in code view only
  python -m src.rag.cli.search "async function" --view code

  # Search with language filter
  python -m src.rag.cli.search "list comprehension" --view code --language python

  # Get more results
  python -m src.rag.cli.search "machine learning" --top-k 20

  # JSON output
  python -m src.rag.cli.search "neural network" --json

  # No context expansion (faster)
  python -m src.rag.cli.search "quicksort" --no-context
        """,
    )

    parser.add_argument(
        "query",
        help="Search query string",
    )

    parser.add_argument(
        "--view",
        choices=["text", "code", "image", "caption", "table", "figure"],
        help="Filter by view type",
    )

    parser.add_argument(
        "--language",
        help="Filter by programming language (e.g., python, javascript)",
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Number of results to return (default: 10, max: 1000)",
    )

    parser.add_argument(
        "--no-context",
        action="store_true",
        help="Skip parent context expansion (faster)",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )

    parser.add_argument(
        "--optimize",
        action="store_true",
        help="Enable query optimization (extract keywords using LLM)",
    )

    return parser


if __name__ == "__main__":
    parser = create_parser()
    args = parser.parse_args()
    sys.exit(main(args))


__all__ = ["main", "create_parser"]
