"""Interactive CLI for running search queries and RAG.

Usage:
    python -m src.rag.api.cli       # Search mode
    python -m src.rag.api.cli --rag # RAG mode (with LLM generation)
"""

import argparse
import sys
from typing import Optional

from loguru import logger

from src.rag.embedding import EmbeddingProviderFactory
from src.rag.shared.config import load_config, load_generation_config
from src.rag.shared.exceptions import ConfigurationError, DatabaseNotConfiguredError

from ..formatters import ResponseFormatter
from ..use_cases import RAGUseCase, SearchUseCase
from ..validators import RequestValidator, ValidationError


def print_help(rag_mode: bool) -> None:
    base_commands = (
        "\nCommands:\n"
        "  :help                 Show this help\n"
        "  :quit / :q / exit     Quit\n"
        "  :show                 Show current settings\n"
        "  :view <type|none>     Set view filter (text/code/image/caption/table/figure)\n"
        "  :lang <name|none>     Set language filter (python/javascript/etc.)\n"
        "  :topk <int>           Set top-k results\n"
    )

    search_commands = (
        "  :context <on|off>     Toggle parent context\n"
        "  :json <on|off>        Toggle JSON output\n"
    )

    rag_commands = (
        "  :rag <on|off>         Toggle RAG mode (LLM generation)\n"
        "  :sources              Show sources from last response\n"
        "  :conversation <on|off> Toggle multi-turn conversation\n"
        "  :clear-history        Clear conversation history\n"
    )

    if rag_mode:
        logger.info(base_commands + rag_commands + "\nEnter any text to ask a question.\n")
    else:
        logger.info(base_commands + search_commands + rag_commands + "\nEnter any text to run a search.\n")


def parse_toggle(value: str) -> bool:
    return value.lower() in ("1", "true", "yes", "y", "on")


def show_settings(
    view: Optional[str],
    language: Optional[str],
    top_k: int,
    show_context: bool,
    as_json: bool,
    rag_mode: bool,
    use_conversation: bool,
) -> None:
    settings = [
        "Current settings:",
        f"  rag_mode:    {'on' if rag_mode else 'off'}",
        f"  view:        {view or '<none>'}",
        f"  language:    {language or '<none>'}",
        f"  top_k:       {top_k}",
    ]
    if not rag_mode:
        settings.append(f"  context:     {'on' if show_context else 'off'}")
        settings.append(f"  json:        {'on' if as_json else 'off'}")
    else:
        settings.append(f"  conversation: {'on' if use_conversation else 'off'}")
    logger.info("\n".join(settings))


def run_repl(args: argparse.Namespace) -> int:
    try:
        config = load_config()
        gen_config = load_generation_config()
        embeddings_client = EmbeddingProviderFactory.create(config)
    except ConfigurationError as e:
        logger.error(f"Configuration error: {e}")
        logger.error("Please set PG_CONN and COLLECTION_NAME environment variables.")
        return 1

    verbose = args.verbose

    # Initialize use cases
    search_use_case = SearchUseCase(embeddings_client, config, verbose=verbose)
    rag_use_case: Optional[RAGUseCase] = None

    # Settings
    view = args.view
    language = args.language
    top_k = args.top_k
    show_context = not args.no_context
    as_json = args.json
    rag_mode = args.rag
    use_conversation = gen_config.enable_conversation

    # Last RAG response for :sources command
    last_rag_response = None

    # Initialize RAG use case if starting in RAG mode
    if rag_mode:
        try:
            rag_use_case = RAGUseCase(embeddings_client, config, gen_config,verbose=verbose)
            logger.info("OCR Vector DB RAG REPL (LLM-powered)")
        except Exception as e:
            logger.warning(f"Failed to initialize RAG: {e}")
            logger.warning("Falling back to search mode")
            rag_mode = False

    if not rag_mode:
        logger.info("OCR Vector DB Search REPL")

    logger.info("Type :help for commands.")

    while True:
        try:
            prompt = "RAG> " if rag_mode else "> "
            line = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            logger.info("")
            break

        if not line:
            continue

        cmd = line.split()
        head = cmd[0].lower()

        # Common commands
        if head in (":quit", ":q", "exit"):
            break

        if head == ":help":
            print_help(rag_mode)
            continue

        if head == ":show":
            show_settings(view, language, top_k, show_context, as_json, rag_mode, use_conversation)
            continue

        if head == ":view":
            if len(cmd) < 2:
                logger.warning("usage: :view <type|none>")
                continue
            value = cmd[1].lower()
            view = None if value == "none" else value
            logger.info(f"view set to {view or '<none>'}")
            continue

        if head == ":lang":
            if len(cmd) < 2:
                logger.warning("usage: :lang <name|none>")
                continue
            value = cmd[1]
            language = None if value.lower() == "none" else value
            logger.info(f"language set to {language or '<none>'}")
            continue

        if head == ":topk":
            if len(cmd) < 2 or not cmd[1].isdigit():
                logger.warning("usage: :topk <int>")
                continue
            top_k = int(cmd[1])
            logger.info(f"top_k set to {top_k}")
            continue

        # Search-only commands
        if head == ":context":
            if len(cmd) < 2:
                logger.warning("usage: :context <on|off>")
                continue
            show_context = parse_toggle(cmd[1])
            logger.info(f"context {'on' if show_context else 'off'}")
            continue

        if head == ":json":
            if len(cmd) < 2:
                logger.warning("usage: :json <on|off>")
                continue
            as_json = parse_toggle(cmd[1])
            logger.info(f"json {'on' if as_json else 'off'}")
            continue

        # RAG commands
        if head == ":rag":
            if len(cmd) < 2:
                logger.warning("usage: :rag <on|off>")
                continue
            new_rag_mode = parse_toggle(cmd[1])
            if new_rag_mode and not rag_use_case:
                try:
                    rag_use_case = RAGUseCase(embeddings_client, config, gen_config,verbose=verbose)
                except Exception as e:
                    logger.error(f"Failed to initialize RAG: {e}")
                    continue
            rag_mode = new_rag_mode
            logger.info(f"RAG mode {'on' if rag_mode else 'off'}")
            continue

        if head == ":sources":
            if last_rag_response and last_rag_response.sources:
                sources_output = ["\nSources from last response:"]
                for i, expanded in enumerate(last_rag_response.sources, 1):
                    source = expanded.result.metadata.get("source", "unknown")
                    view_type = expanded.result.view.value
                    sim = f"{expanded.result.similarity:.3f}"
                    sources_output.append(f"  [{i}] {source} ({view_type}, sim: {sim})")
                logger.info("\n".join(sources_output))
            else:
                logger.info("No previous RAG response")
            continue

        if head == ":conversation":
            if len(cmd) < 2:
                logger.warning("usage: :conversation <on|off>")
                continue
            use_conversation = parse_toggle(cmd[1])
            logger.info(f"conversation {'on' if use_conversation else 'off'}")
            continue

        if head == ":clear-history":
            if rag_use_case:
                rag_use_case.clear_conversation()
            logger.info("conversation history cleared")
            continue

        # Execute query
        query = line
        try:
            RequestValidator.validate_query(query)
            if view:
                RequestValidator.validate_view(view)
            RequestValidator.validate_top_k(top_k)
        except ValidationError as exc:
            logger.warning(ResponseFormatter.format_error(exc))
            continue

        if rag_mode and rag_use_case:
            # RAG mode: generate answer with LLM
            try:
                response = rag_use_case.execute(
                    query=query,
                    view=view,
                    language=language,
                    top_k=top_k,
                    use_conversation=use_conversation,
                )
                last_rag_response = response
                logger.info(f"\n{response.format_with_sources()}\n")
            except Exception as e:
                logger.error(f"RAG failed: {e}")
        else:
            # Search mode: show results
            try:
                results = search_use_case.execute(
                    query=query,
                    view=view,
                    language=language,
                    top_k=top_k,
                    expand_context=show_context,
                )
            except DatabaseNotConfiguredError as exc:
                logger.error(f"Search unavailable: {exc}")
                continue
            except Exception as exc:
                logger.error(f"Search failed: {exc}")
                continue

            if as_json:
                output = ResponseFormatter.format_search_results_json(
                    results,
                    show_context=show_context,
                )
            else:
                output = ResponseFormatter.format_search_results_text(
                    results,
                    show_context=show_context,
                )
            logger.info(output)

    return 0


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Interactive search/RAG REPL")
    parser.add_argument(
        "--rag",
        action="store_true",
        help="Start in RAG mode (LLM-powered answers)",
    )
    parser.add_argument(
        "--view",
        choices=["text", "code", "image", "caption", "table", "figure"],
        help="Default view filter",
    )
    parser.add_argument(
        "--language",
        help="Default language filter (python/javascript/etc.)",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Default number of results (default: 5)",
    )
    parser.add_argument(
        "--no-context",
        action="store_true",
        help="Disable parent context expansion by default",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON by default",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        dest="verbose",
        help="Enable verbose logging (shows rewritten queries, filters)",
    )
    return parser


if __name__ == "__main__":
    parser = create_parser()
    sys.exit(run_repl(parser.parse_args()))


__all__ = ["run_repl", "create_parser"]
