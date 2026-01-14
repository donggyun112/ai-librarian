"""CLI command for document ingestion.

Usage:
    python -m src.rag.cli.ingest file1.txt file2.md --view text --top-k 5
"""

import argparse
import glob
import sys
from typing import List

from src.rag.shared.config import load_config

from .formatters import ResponseFormatter
from .use_cases import IngestUseCase
from .validators import RequestValidator, ValidationError


def expand_file_patterns(patterns: List[str]) -> List[str]:
    """Expand glob patterns to file paths.

    Args:
        patterns: List of file patterns (e.g., ["*.txt", "docs/*.md"])

    Returns:
        List of expanded file paths
    """
    files: List[str] = []
    for pattern in patterns:
        matches = glob.glob(pattern, recursive=True)
        if matches:
            files.extend(matches)
        else:
            # Not a glob pattern, treat as literal path
            files.append(pattern)

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for f in files:
        if f not in seen:
            seen.add(f)
            unique.append(f)

    return unique


def main(args: argparse.Namespace) -> int:
    """Execute ingest command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    try:
        # Load configuration
        config = load_config()

        # Expand file patterns
        file_paths = expand_file_patterns(args.files)

        # Validate files
        RequestValidator.validate_file_paths(file_paths)

        print(f"[ingest] Processing {len(file_paths)} file(s)")

        # Execute ingestion use case
        # --force-ocr flag disables OCR cache and enables force OCR mode
        disable_cache = getattr(args, "force_ocr", False)
        if disable_cache:
            print("[cache] Cache disabled (--force-ocr)")
            config.force_ocr = True  # Enable force OCR mode in config

        use_case = IngestUseCase(config, disable_cache=disable_cache)

        result = use_case.execute(file_paths)

        # Format and display results
        summary = ResponseFormatter.format_ingest_summary(
            total_documents=result.documents_processed,
            total_concepts=result.concepts_created,
            total_fragments=result.fragments_created,
            total_embeddings=result.embeddings_generated,
        )
        print(summary)

        return 0

    except ValidationError as e:
        print(ResponseFormatter.format_error(e))
        return 1
    except Exception as e:
        print(ResponseFormatter.format_error(e))
        return 2


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for ingest command.

    Returns:
        Configured ArgumentParser
    """
    parser = argparse.ArgumentParser(
        description="Ingest documents into OCR Vector DB",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Ingest single file
  python -m src.rag.cli.ingest document.txt

  # Ingest multiple files
  python -m src.rag.cli.ingest file1.txt file2.md

  # Ingest with glob pattern
  python -m src.rag.cli.ingest docs/*.md

  # Dry run (parse only, no DB writes)
  python -m src.rag.cli.ingest *.txt --dry-run
        """,
    )

    parser.add_argument(
        "files",
        nargs="+",
        help="File paths or glob patterns to ingest",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse files without writing to database",
    )

    parser.add_argument(
        "--force-ocr",
        action="store_true",
        help="Force OCR even if cache exists (bypass .pdf.ocr.md cache)",
    )

    return parser


if __name__ == "__main__":
    parser = create_parser()
    args = parser.parse_args()
    sys.exit(main(args))


__all__ = ["main", "create_parser"]
