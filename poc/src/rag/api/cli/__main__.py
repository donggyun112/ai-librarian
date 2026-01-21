"""CLI entry point for running as `python -m api.cli`.

Usage:
    python -m api.cli              # REPL (search mode)
    python -m api.cli --rag        # REPL (RAG mode)
    python -m api.cli search "query"  # Direct search
    python -m api.cli ingest /path    # Ingest documents
    python -m api.cli repl            # REPL mode (explicit)
    python -m api.cli quality         # Quality check
"""

import argparse
import sys

from src.rag.api.cli import ingest, quality, repl, search


def main() -> None:
    """Entry point for `python -m src.rag.api.cli`."""
    # Check for subcommands
    if len(sys.argv) > 1 and sys.argv[1] in ("ingest", "search", "repl", "quality"):
        parser = argparse.ArgumentParser(prog="python -m src.rag.api.cli")
        subparsers = parser.add_subparsers(dest="command", required=True)

        # Ingest
        ingest_parser = subparsers.add_parser("ingest", help="Ingest documents")
        ingest_parser.add_argument("files", nargs="+", help="Files to ingest")
        ingest_parser.add_argument("--force-ocr", action="store_true", help="Force OCR")

        # Search
        search_parser = subparsers.add_parser("search", help="Search documents")
        search_parser.add_argument("query", help="Search query")
        search_parser.add_argument(
            "--view",
            choices=["text", "code", "image", "caption", "table", "figure"],
        )
        search_parser.add_argument("--language", help="Language filter")
        search_parser.add_argument("--top-k", type=int, default=10)
        search_parser.add_argument("--no-context", action="store_true")
        search_parser.add_argument("--json", action="store_true")

        # REPL (explicit subcommand)
        repl_parser = subparsers.add_parser("repl", help="Interactive REPL mode")
        repl_parser.add_argument("--rag", action="store_true", help="Enable RAG mode")
        repl_parser.add_argument(
            "-v", "--verbose", action="store_true", help="Verbose output"
        )

        # Quality
        quality_parser = subparsers.add_parser("quality", help="Quality check")
        quality_parser.add_argument(
            "-v", "--verbose", action="store_true", help="Verbose output"
        )

        args = parser.parse_args()

        if args.command == "ingest":
            sys.exit(ingest.main(args))
        elif args.command == "search":
            sys.exit(search.main(args))
        elif args.command == "repl":
            sys.exit(repl.run_repl(args))
        elif args.command == "quality":
            sys.exit(quality.main(args))

    # Default: REPL mode (no subcommand provided)
    # Use repl's parser to handle repl-specific flags (--rag, etc.)
    parser = repl.create_parser()
    args = parser.parse_args()
    sys.exit(repl.run_repl(args))


if __name__ == "__main__":
    main()
