"""CLI entry point for running as `python -m src.rag.api.cli`.

Usage:
    python -m src.rag.api.cli                       # REPL (search mode, default)
    python -m src.rag.api.cli --rag                 # REPL (RAG mode)
    python -m src.rag.api.cli repl --json --view code   # Explicit REPL with options
    python -m src.rag.api.cli search "query"        # Direct search
    python -m src.rag.api.cli ingest /path          # Ingest documents

Design:
    - Both default execution and explicit `repl` subcommand share the same options
      by delegating to `repl.create_parser()` to avoid duplication.
"""

import argparse
import sys

from src.rag.api.cli import ingest, repl, search


def _add_repl_arguments(parser: argparse.ArgumentParser) -> None:
    """Add REPL arguments to parser by copying from repl.create_parser().
    
    This ensures the explicit `repl` subcommand and default execution path
    have identical CLI interfaces without duplicating option definitions.
    """
    repl_parser = repl.create_parser()
    for action in repl_parser._actions:
        # Skip the help action (already added by default)
        if action.dest == "help":
            continue
        # Copy the action to our parser
        parser._add_action(action)


def main() -> None:
    """Entry point for `python -m src.rag.api.cli`."""
    # Check for explicit subcommands
    if len(sys.argv) > 1 and sys.argv[1] in ("ingest", "search", "repl"):
        parser = argparse.ArgumentParser(prog="python -m src.rag.api.cli")
        subparsers = parser.add_subparsers(dest="command", required=True)

        # Ingest subcommand
        ingest_parser = subparsers.add_parser("ingest", help="Ingest documents")
        ingest_parser.add_argument("files", nargs="+", help="Files to ingest")
        ingest_parser.add_argument("--force-ocr", action="store_true", help="Force OCR")

        # Search subcommand
        search_parser = subparsers.add_parser("search", help="Search documents")
        search_parser.add_argument("query", help="Search query")
        search_parser.add_argument("--top-k", type=int, default=10)
        search_parser.add_argument("--no-context", action="store_true")
        search_parser.add_argument("--json", action="store_true")

        # REPL subcommand - delegates to repl module's parser for consistency
        repl_subparser = subparsers.add_parser(
            "repl", 
            help="Interactive search/RAG REPL"
        )
        _add_repl_arguments(repl_subparser)

        args = parser.parse_args()

        if args.command == "ingest":
            sys.exit(ingest.main(args))
        elif args.command == "search":
            sys.exit(search.main(args))
        elif args.command == "repl":
            sys.exit(repl.run_repl(args))

    # Default: REPL mode (no subcommand provided)
    # Use repl's parser to handle repl-specific flags
    parser = repl.create_parser()
    args = parser.parse_args()
    sys.exit(repl.run_repl(args))


if __name__ == "__main__":
    main()
