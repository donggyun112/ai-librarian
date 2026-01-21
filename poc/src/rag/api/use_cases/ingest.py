"""Ingestion use case orchestration.

Implements PKG-API-004: Orchestrate packages for ingestion use case.

Rules:
- DEP-API-ALLOW-002: MAY import ingestion
- DEP-API-ALLOW-003: MAY import embedding
- DEP-API-ALLOW-005: MAY import storage
- DEP-API-ALLOW-006: MAY import shared
- PKG-API-BAN-001: MUST NOT implement business logic directly
- PKG-API-BAN-002: MUST NOT access database directly
"""

import hashlib
import os
import uuid
from dataclasses import dataclass
from typing import List

from loguru import logger

from src.rag.domain import Concept, Document, Fragment
from src.rag.embedding import EmbeddingProviderFactory, EmbeddingValidator
from src.rag.ingestion import (
    BaseSegmentParser,
    GeminiVisionOcr,
    MarkdownParser,
    OcrParser,
    PdfParser,
    PyMuPdfParser,
    RawSegment,
    SemanticUnitGrouper,
    SegmentToConceptTransformer,
)
from .dto import IngestResult

from src.rag.shared.config import EmbeddingConfig
from src.rag.shared.text_utils import TextNormalizerUtil
from src.rag.storage import (
    CascadeDeleter,
    ConceptRepository,
    DbSchemaManager,
    DocumentRepository,
    EmbeddingRepository,
    FragmentRepository,
    ParentDocumentStore,
    VectorStoreWriter,
)
from langchain_core.documents import Document as LCDocument





class IngestUseCase:
    """Orchestrates the document ingestion pipeline.

    Implements PKG-API-004 (orchestration).

    Pipeline:
    1. Parse files (ingestion layer)
    2. Create concepts and fragments (ingestion layer)
    3. Validate fragments (embedding layer)
    4. Generate embeddings (embedding layer)
    5. Store to database (storage layer)

    Example:
        >>> use_case = IngestUseCase(config)
        >>> result = use_case.execute(["file1.txt", "file2.md"])
    """

    def __init__(self, config: EmbeddingConfig, disable_cache: bool = False) -> None:
        self.config = config
        self.disable_cache = disable_cache
        self.preprocessor = TextNormalizerUtil()
        self.validator = EmbeddingValidator()
        self.unitizer = SemanticUnitGrouper(text_unit_threshold=config.text_unit_threshold)
        self.concept_builder = SegmentToConceptTransformer()
        self.md_parser = MarkdownParser(self.preprocessor)
        self.ocr_parser = OcrParser(self.preprocessor)
        self.pdf_parser = self._create_pdf_parser()

        self.doc_repo = DocumentRepository(config)
        self.concept_repo = ConceptRepository(config)
        self.fragment_repo = FragmentRepository(config)
        self.embedding_repo = EmbeddingRepository(config)
        self.schema_manager = DbSchemaManager(config)

        # Cascade deleter for re-ingest cleanup
        self.cascade_deleter = CascadeDeleter(
            document_repo=self.doc_repo,
            concept_repo=self.concept_repo,
            fragment_repo=self.fragment_repo,
            embedding_repo=self.embedding_repo,
        )

        # Embedding generation and storage
        self.embeddings_client = EmbeddingProviderFactory.create(config)
        self.vector_writer = VectorStoreWriter(config)
        self.parent_store = ParentDocumentStore(config)
        self.vector_store = self.vector_writer.create_store(self.embeddings_client)

        # Ensure database tables exist
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        """Ensure all required database tables exist."""
        logger.info("Ensuring database tables...")
        self.schema_manager.apply_db_level_tuning()
        self.schema_manager.ensure_extension_vector()
        self.doc_repo.ensure_table()
        self.concept_repo.ensure_table()
        self.fragment_repo.ensure_table()
        self.schema_manager.ensure_parent_docstore()
        if self.config.custom_schema_write:
            self.schema_manager.ensure_custom_schema(self.config.embedding_dim)
        logger.info("Database tables ready")

    def execute(self, file_paths: List[str]) -> IngestResult:
        """Execute ingestion pipeline.

        Args:
            file_paths: List of file paths to ingest

        Returns:
            IngestResult with statistics

        Note:
            Uses "prepare-then-commit" pattern to prevent data loss on mid-operation failures.
            All parsing/embedding is done first, then old data is deleted and new data saved.
        """
        total_concepts = 0
        total_fragments = 0
        total_embeddings = 0

        for file_path in file_paths:
            logger.info(f"Processing: {file_path}")

            # ═══════════════════════════════════════════════════════════════
            # PHASE 1: PREPARE (all operations that can fail)
            # ═══════════════════════════════════════════════════════════════

            # 1. Parse file based on extension
            segments = self._parse_file(file_path)
            logger.info(f"Parsed {len(segments)} segments")

            # 2. Create Document entity with deterministic ID (based on file path)
            doc_id = hashlib.md5(file_path.encode("utf-8")).hexdigest()
            document = Document(
                id=doc_id,
                source_path=file_path,
                metadata={"filename": os.path.basename(file_path)},
            )

            # 3. Unitize segments (group related content)
            unitized = self.unitizer.unitize(segments)
            logger.info(f"Created {len(unitized)} semantic units")

            # 4. Build Concepts and Fragments (in memory)
            concepts = self.concept_builder.build(unitized, document, os.path.basename(file_path))
            logger.info(f"Built {len(concepts)} concepts")

            # 5. Prepare all embeddings in memory (most likely to fail: API calls)
            prepared_data = []  # List of (concept, valid_fragments, lc_docs, embeddings)
            for concept in concepts:
                valid_fragments = []
                lc_docs = []

                for fragment in concept.fragments:
                    if not self.validator.is_eligible(fragment):
                        logger.info(f"Fragment filtered: {fragment.content[:50]}...")
                        continue

                    valid_fragments.append(fragment)

                    # Prepare LangChain Document
                    frag_doc_id = fragment.compute_doc_id()
                    lc_doc = LCDocument(
                        page_content=fragment.content,
                        metadata={
                            "doc_id": frag_doc_id,
                            "fragment_id": fragment.id,
                            "parent_id": fragment.concept_id,
                            "view": fragment.view.value,
                            "lang": fragment.language,
                            **(fragment.metadata or {}),
                        }
                    )
                    lc_docs.append(lc_doc)

                prepared_data.append((concept, valid_fragments, lc_docs))

            # ═══════════════════════════════════════════════════════════════
            # PHASE 2: COMMIT (delete old, save new - fast DB operations only)
            # ═══════════════════════════════════════════════════════════════
            # If we reach here, all preparation succeeded. Now safe to delete old data.

            if self.doc_repo.exists(doc_id):
                logger.info(f"Cleaning up existing data for doc_id: {doc_id[:8]}...")
                self.cascade_deleter.delete_document(doc_id)

            # Save Document
            self.doc_repo.save(document)

            # Save Concepts, Fragments, and Embeddings
            for concept, valid_fragments, lc_docs in prepared_data:
                self.concept_repo.save(concept)
                total_concepts += 1

                # Save parent document for context expansion
                self._save_parent(concept)

                # Save fragments
                for fragment in valid_fragments:
                    self.fragment_repo.save(fragment)
                    total_fragments += 1

                # Batch embed and store to PGVector
                if lc_docs:
                    embedded = self.vector_writer.upsert_batch(self.vector_store, lc_docs)
                    total_embeddings += embedded

        # Ensure indexes after all data is inserted
        self.schema_manager.ensure_indexes()

        return IngestResult(
            documents_processed=len(file_paths),
            concepts_created=total_concepts,
            fragments_created=total_fragments,
            embeddings_generated=total_embeddings,
        )

    def _create_pdf_parser(self) -> BaseSegmentParser:
        """Create PDF parser based on config.pdf_parser setting.

        Supports:
        - "pymupdf": PyMuPDF with optional Gemini Vision OCR (default)
        - "pdfminer": Legacy pdfminer.six parser (no OCR support)

        Returns:
            BaseSegmentParser instance (PyMuPdfParser or PdfParser)
        """
        # Use legacy pdfminer parser if configured
        if self.config.pdf_parser == "pdfminer":
            logger.info("PDF parser: pdfminer (legacy, no OCR support)")
            return PdfParser(
                self.preprocessor,
                enable_auto_ocr=self.config.enable_auto_ocr,
                force_ocr=self.config.force_ocr,
                ocr_languages=self.config.ocr_languages,
            )

        # Default: PyMuPDF with Gemini Vision OCR
        ocr = None
        if self.config.enable_image_ocr:
            try:
                ocr = GeminiVisionOcr(model=self.config.gemini_ocr_model)
                logger.info(f"Gemini Vision OCR enabled (model: {self.config.gemini_ocr_model})")
            except RuntimeError as e:
                logger.warning(f"Gemini Vision OCR disabled: {e}")

        # use_cache is enabled by default, disabled when force_ocr is set via CLI
        use_cache = not getattr(self, 'disable_cache', False)
        logger.info("PDF parser: pymupdf")
        return PyMuPdfParser(
            self.preprocessor,
            ocr=ocr,
            enable_auto_ocr=self.config.enable_auto_ocr,
            force_ocr=self.config.force_ocr,
            use_cache=use_cache,
        )

    def _parse_file(self, file_path: str) -> List[RawSegment]:
        """Parse file based on extension.

        Args:
            file_path: Path to file

        Returns:
            List of RawSegment objects
        """
        ext = os.path.splitext(file_path)[1].lower()

        if ext in (".md", ".markdown"):
            parser = self.md_parser
        elif ext == ".pdf":
            parser = self.pdf_parser
        else:
            # Default: plain text
            parser = self.ocr_parser

        return parser.parse(file_path)

    def _save_parent(self, concept: Concept) -> None:
        """Save concept as parent document for context retrieval.

        Implements SEARCH-SEP-003: Parent documents provide context.

        Args:
            concept: Concept entity with fragments attached
        """
        content = self._synthesize_parent_content(concept)
        metadata = {
            "document_id": concept.document_id,
            "order": concept.order,
        }
        self.parent_store.upsert_parent(concept.id, content, metadata)

    def _synthesize_parent_content(self, concept: Concept) -> str:
        """Synthesize parent content from fragments.

        Combines ALL view fragments (text, code, image) to create parent document.
        Implements ARCHITECTURE.md 5.5: "모든 View의 Fragment 수집 (text, code, image)"
        Limits to config.parent_context_limit characters to avoid token overflow.

        Args:
            concept: Concept entity with fragments attached

        Returns:
            Synthesized parent content string
        """
        fragments = getattr(concept, "fragments", None) or concept.metadata.get("fragments", [])
        if not fragments:
            return concept.content or ""

        # Collect ALL fragments, grouped by view for readability
        # Order: text first, then code, then others (image, table, etc.)
        view_order = {"text": 0, "code": 1, "image": 2, "table": 3, "figure": 4}
        sorted_fragments = sorted(
            fragments,
            key=lambda f: (view_order.get(f.view.value, 99), f.order),
        )

        # Build content with view markers for code blocks
        parts = []
        for f in sorted_fragments:
            if f.view.value == "code":
                lang = f.language or ""
                parts.append(f"```{lang}\n{f.content}\n```")
            else:
                parts.append(f.content)

        # Join and limit to configured parent_context_limit
        limit = self.config.parent_context_limit
        return "\n\n".join(parts)[:limit]


__all__ = ["IngestUseCase", "IngestResult"]
