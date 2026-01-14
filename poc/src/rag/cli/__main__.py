"""CLI entry point for running as `python -m src.rag.cli`.

Usage:
    python -m src.rag.cli              # REPL (search mode)
    python -m src.rag.cli --rag        # REPL (RAG mode)
    python -m src.rag.cli search "query"  # Direct search
    python -m src.rag.cli ingest /path    # Ingest documents
"""

import sys

from .repl import create_parser, run_repl


def main():
    """Entry point for `python -m src.rag.cli`."""
    parser = create_parser()
    args = parser.parse_args()
    sys.exit(run_repl(args))


if __name__ == "__main__":
    main()
