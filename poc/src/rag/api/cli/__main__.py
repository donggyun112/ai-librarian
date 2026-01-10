"""CLI entry point for running as `python -m api.cli`.

Usage:
    python -m api.cli              # REPL (search mode)
    python -m api.cli --rag        # REPL (RAG mode)
    python -m api.cli search "query"  # Direct search
    python -m api.cli ingest /path    # Ingest documents
"""

import sys

from .repl import run_repl, create_parser


def main():
    """Entry point for `python -m api.cli`."""
    parser = create_parser()
    args = parser.parse_args()
    sys.exit(run_repl(args))


if __name__ == "__main__":
    main()
