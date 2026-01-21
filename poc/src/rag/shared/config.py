import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv
from src.rag.shared.exceptions import ConfigurationError


PAGE_REGEX_DEFAULT = "(?mi)^\\s*(?:page|\\uD398\\uC774\\uC9C0)\\s*([0-9]{1,5})\\b"
SECTION_REGEX_DEFAULT = "(?m)^(?:#{1,3}\\s+.+|Chapter\\s+\\d+\\b|\\uC81C\\s*\\d+\\s*\\uC7A5\\b|\\d+\\.\\d+\\s+.+)"


@dataclass
class EmbeddingConfig:
    """Configuration for embedding pipeline."""

    pg_conn: str
    collection_name: str
    embedding_model: str
    embedding_dim: int
    embedding_provider: str
    gemini_model: str
    custom_schema_write: bool
    rate_limit_rpm: int
    max_chars_per_request: int
    max_items_per_request: int
    max_docs_to_embed: int
    parent_mode: str
    page_regex: str
    section_regex: str
    enable_auto_ocr: bool
    force_ocr: bool
    ocr_languages: str
    # PDF parser settings
    pdf_parser: str  # "pymupdf" | "pdfminer"
    enable_image_ocr: bool  # Enable Gemini Vision OCR for image blocks
    gemini_ocr_model: str  # Gemini model for OCR (e.g., "gemini-2.0-flash")
    # Semantic unit settings
    parent_context_limit: int  # Max chars for parent context synthesis
    text_unit_threshold: int  # Min chars for text-only semantic unit
    ivfflat_probes: Optional[int] = None
    hnsw_ef_search: Optional[int] = None
    hnsw_ef_construction: Optional[int] = None
    pg_pool_min_size: int = 0
    pg_pool_max_size: int = 4


@dataclass
class GenerationConfig:
    """Configuration for generation pipeline (RAG)."""

    llm_provider: str  # LLM provider: "openai" | "gemini"
    llm_model: str  # LLM model name (e.g., "gpt-4o", "gemini-2.0-flash")
    temperature: float  # Generation temperature (0-1)
    max_tokens: int  # Maximum output tokens
    enable_conversation: bool  # Enable multi-turn conversation

def _parse_int(value: Optional[str], default: int = 0) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _parse_optional_int(value: Optional[str]) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return value.lower() in ("1", "true", "yes", "y", "on")


def _get_embedding_model_for_provider(provider: str) -> str:
    """Get embedding model name based on provider.

    Each provider uses its own environment variable:
    - openai: OPENAI_EMBEDDING_MODEL (default: text-embedding-3-small)
    - gemini: Uses gemini_model field separately
    - voyage: VOYAGE_MODEL (default: voyage-3)
    """
    if provider == "openai":
        return os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    if provider == "gemini":
        # gemini uses gemini_model field
        return ""
    # voyage (default)
    return os.getenv("VOYAGE_MODEL", "voyage-3")


def load_config() -> EmbeddingConfig:
    """Load configuration from environment variables."""
    load_dotenv()

    embedding_provider = os.getenv("EMBEDDING_PROVIDER", "openai").lower()
    
    pg_conn = os.getenv("PG_CONN","").strip()
    if not pg_conn:
            raise ConfigurationError("PG_CONN env var is required for PGVector search/ingest.")
    
    collection_name = os.getenv("COLLECTION_NAME","").strip()
    if not collection_name:
        raise ConfigurationError("COLLECTION_NAME env var is required for PGVector search/ingest.")
    
    embedding_dim = _parse_int(os.getenv("EMBEDDING_DIM"), 1536)
    if os.getenv("EMBEDDING_DIM") in (None, "") and embedding_provider == "gemini":
        embedding_dim = 768
    pg_pool_min_size = max(0, _parse_int(os.getenv("PG_POOL_MIN_SIZE"), 0))
    pg_pool_max_size = max(1, _parse_int(os.getenv("PG_POOL_MAX_SIZE"), 4))
    if pg_pool_max_size < pg_pool_min_size:
        pg_pool_max_size = pg_pool_min_size

    config = EmbeddingConfig(
        pg_conn=pg_conn,
        collection_name=collection_name,
        embedding_model=_get_embedding_model_for_provider(embedding_provider),
        embedding_dim=embedding_dim,
        embedding_provider=embedding_provider,
        gemini_model=os.getenv("GEMINI_EMBED_MODEL", "text-embedding-004"),
        custom_schema_write=_parse_bool(os.getenv("CUSTOM_SCHEMA_WRITE", "true"), True),
        rate_limit_rpm=_parse_int(os.getenv("RATE_LIMIT_RPM"), 0),
        max_chars_per_request=_parse_int(os.getenv("MAX_CHARS_PER_REQUEST"), 0),
        max_items_per_request=_parse_int(os.getenv("MAX_ITEMS_PER_REQUEST"), 0),
        max_docs_to_embed=_parse_int(os.getenv("MAX_DOCS_TO_EMBED"), 0),
        parent_mode=os.getenv("PARENT_MODE", "unit").lower(),
        page_regex=os.getenv("PAGE_REGEX", PAGE_REGEX_DEFAULT),
        section_regex=os.getenv("SECTION_REGEX", SECTION_REGEX_DEFAULT),
        enable_auto_ocr=_parse_bool(os.getenv("ENABLE_AUTO_OCR", "false"), False),
        force_ocr=_parse_bool(os.getenv("FORCE_OCR", "false"), False),
        ocr_languages=os.getenv("OCR_LANGS", "kor+eng"),
        pdf_parser=os.getenv("PDF_PARSER", "pymupdf").lower(),
        enable_image_ocr=_parse_bool(os.getenv("ENABLE_IMAGE_OCR", "true"), True),
        gemini_ocr_model=os.getenv("GEMINI_OCR_MODEL", "gemini-2.0-flash"),
        parent_context_limit=_parse_int(os.getenv("PARENT_CONTEXT_LIMIT"), 2000),
        text_unit_threshold=_parse_int(os.getenv("TEXT_UNIT_THRESHOLD"), 500),
        ivfflat_probes=_parse_optional_int(os.getenv("IVFFLAT_PROBES")),
        hnsw_ef_search=_parse_optional_int(os.getenv("HNSW_EF_SEARCH")),
        hnsw_ef_construction=_parse_optional_int(os.getenv("HNSW_EF_CONSTRUCTION")),
        pg_pool_min_size=pg_pool_min_size,
        pg_pool_max_size=pg_pool_max_size,
    )
    return config


def load_generation_config() -> GenerationConfig:
    """Load generation configuration from environment variables."""
    load_dotenv()

    llm_provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    
    # Get model based on provider
    if llm_provider == "openai":
        default_model = "gpt-4o"
    else:
        default_model = "gemini-2.0-flash"
    
    llm_model = os.getenv("LLM_MODEL", default_model)

    return GenerationConfig(
        llm_provider=llm_provider,
        llm_model=llm_model,
        temperature=float(os.getenv("LLM_TEMPERATURE", "0.7")),
        max_tokens=_parse_int(os.getenv("LLM_MAX_TOKENS"), 2048),
        enable_conversation=_parse_bool(
            os.getenv("ENABLE_CONVERSATION", "false"), False
        ),
    )


__all__ = ["EmbeddingConfig", "load_config", "GenerationConfig", "load_generation_config"]
