"""CLI command for embedding quality checks.

Usage:
    python -m src.rag.cli.quality --metrics
    python -m src.rag.cli.quality --golden eval_queries.jsonl
"""

import argparse
import json
import sys
from typing import Any, Dict, List, Tuple

from src.rag.embedding import EmbeddingProviderFactory
from src.rag.shared.config import load_config
from src.rag.storage import EmbeddingMetricsService

from .use_cases import SearchUseCase
from .validators import RequestValidator, ValidationError


def load_golden_queries(path: str) -> List[Dict[str, Any]]:
    queries: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            queries.append(json.loads(text))
    return queries


def evaluate_queries(
    queries: List[Dict[str, Any]],
    use_case: SearchUseCase,
) -> Tuple[int, int, List[str]]:
    total = 0
    passed = 0
    failures: List[str] = []

    for idx, entry in enumerate(queries, 1):
        query = entry.get("query")
        if not query:
            failures.append(f"[{idx}] missing 'query'")
            continue

        view = entry.get("view")
        language = entry.get("language")
        top_k = int(entry.get("top_k", 10))
        expand_context = bool(entry.get("expand_context", True))
        expect_parent_ids = entry.get("expect_parent_ids") or []
        expect_contains = entry.get("expect_contains") or []

        try:
            RequestValidator.validate_query(query)
            if view:
                RequestValidator.validate_view(view)
            RequestValidator.validate_top_k(top_k)
        except ValidationError as exc:
            failures.append(f"[{idx}] invalid query config: {exc}")
            continue

        results = use_case.execute(
            query=query,
            view=view,
            language=language,
            top_k=top_k,
            expand_context=expand_context,
        )
        total += 1

        matched = False
        if expect_parent_ids:
            for result in results:
                if result.result.parent_id in expect_parent_ids:
                    matched = True
                    break

        if not matched and expect_contains:
            for result in results:
                content = result.result.content or ""
                parent = result.parent_content or ""
                if any(token in content or token in parent for token in expect_contains):
                    matched = True
                    break

        if matched:
            passed += 1
        else:
            failures.append(f"[{idx}] query='{query}' did not match expectations")

    return passed, total, failures


def print_metrics_summary(metrics) -> None:
    print("Embedding Metrics")
    print("=" * 80)
    if metrics.errors:
        for err in metrics.errors:
            print(f"[error] {err}")
        return

    print(f"Total embeddings:       {metrics.total_embeddings}")
    print(f"Missing doc_id:         {metrics.missing_doc_id}")
    print(f"Missing parent_id:      {metrics.missing_parent_id}")
    print(f"Missing fragment_id:    {metrics.missing_fragment_id}")
    print(f"Short content (<min):   {metrics.short_content}")
    print(f"Duplicate doc_id groups:{metrics.duplicate_doc_id_groups}")

    print("\nTop views:")
    for view, count in metrics.view_counts:
        print(f"  {view:12} {count}")

    print("\nTop languages:")
    for lang, count in metrics.lang_counts:
        print(f"  {lang:12} {count}")


def print_short_samples(samples: List[Tuple[str, str, str, str]]) -> None:
    if not samples:
        return
    print("\nShort-content samples:")
    for frag_id, parent_id, view, content in samples:
        preview = content.replace("\n", " ")[:120]
        print(f"- fragment={frag_id} parent={parent_id} view={view} | {preview}")


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Embedding quality checks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Golden query file format (JSONL):
  {"query": "example", "view": "text", "top_k": 10,
   "expect_parent_ids": ["..."], "expect_contains": ["keyword"]}
        """,
    )
    parser.add_argument(
        "--metrics",
        action="store_true",
        help="Print DB summary metrics (default if no other option)",
    )
    parser.add_argument(
        "--golden",
        help="Run golden query evaluation from JSONL file",
    )
    parser.add_argument(
        "--min-content-len",
        type=int,
        default=10,
        help="Minimum content length for short-content checks",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Limit for view/lang distribution rows",
    )
    parser.add_argument(
        "--sample-short",
        type=int,
        default=0,
        help="Show N short-content samples",
    )
    return parser


def main(args: argparse.Namespace) -> int:
    config = load_config()

    ran_any = False
    failed = False

    if args.metrics or not args.golden:
        ran_any = True
        service = EmbeddingMetricsService(config)
        metrics = service.summarize(limit=args.limit, min_content_len=args.min_content_len)
        print_metrics_summary(metrics)
        if metrics.errors:
            failed = True
        if args.sample_short and not metrics.errors:
            samples = service.sample_short_content(
                min_content_len=args.min_content_len,
                limit=args.sample_short,
            )
            print_short_samples(samples)

    if args.golden:
        ran_any = True
        try:
            queries = load_golden_queries(args.golden)
        except Exception as exc:
            print(f"[error] failed to load golden file: {exc}")
            return 2

        embeddings_client = EmbeddingProviderFactory.create(config)
        use_case = SearchUseCase(embeddings_client, config)
        passed, total, failures = evaluate_queries(queries, use_case)
        print("\nGolden Query Results")
        print("=" * 80)
        print(f"Passed: {passed}/{total}")
        if failures:
            failed = True
            for msg in failures:
                print(f"[fail] {msg}")

    if not ran_any:
        print("[error] no checks were run")
        return 2
    return 1 if failed else 0


if __name__ == "__main__":
    parser = create_parser()
    sys.exit(main(parser.parse_args()))


__all__ = ["main", "create_parser"]
