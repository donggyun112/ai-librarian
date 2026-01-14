"""Build domain Concepts from UnitizedSegments."""

import hashlib
import uuid
from typing import Dict, List

from src.rag.domain import Concept, Document, Fragment, View

from .chunking import TextChunker
from .models import RawSegment, UnitizedSegment


class ConceptBuilder:
    """
    Transform UnitizedSegments into domain Concepts and Fragments.

    This is the bridge between ingestion layer (RawSegment, UnitizedSegment)
    and domain layer (Concept, Fragment).

    Rules enforced:
    - HIER-002: Every Concept belongs to exactly one Document
    - HIER-003: Every Fragment belongs to exactly one Concept
    - FRAG-IMMUT-001: concept_id (parent_id) is set at creation and immutable
    """

    def build(
        self,
        unitized: List[UnitizedSegment],
        document: Document,
        source_basename: str,
    ) -> List[Concept]:
        """
        Build Concepts from UnitizedSegments.

        Args:
            unitized: List of UnitizedSegment objects from SegmentUnitizer
            document: Parent Document entity
            source_basename: Source file basename for generating concept IDs

        Returns:
            List of Concept entities with associated Fragments

        Raises:
            OrphanEntityError: If any Fragment created without valid concept_id
        """
        # Group segments by unit_id
        unit_groups: Dict[str, List[UnitizedSegment]] = {}
        orphan_segments: List[UnitizedSegment] = []

        for unit_seg in unitized:
            if unit_seg.unit_id:
                if unit_seg.unit_id not in unit_groups:
                    unit_groups[unit_seg.unit_id] = []
                unit_groups[unit_seg.unit_id].append(unit_seg)
            else:
                orphan_segments.append(unit_seg)

        concepts: List[Concept] = []
        order = 0

        # Create Concepts from grouped units
        for unit_id, segments in unit_groups.items():
            concept = self._create_concept_from_unit(
                unit_id=unit_id,
                segments=segments,
                document=document,
                order=order,
            )
            concepts.append(concept)
            order += 1

        # Create Concepts for orphan segments (no unit_id)
        if orphan_segments:
            concept = self._create_concept_from_orphans(
                orphan_segments=orphan_segments,
                document=document,
                source_basename=source_basename,
                order=order,
            )
            concepts.append(concept)

        return concepts

    def _create_concept_from_unit(
        self,
        unit_id: str,
        segments: List[UnitizedSegment],
        document: Document,
        order: int,
    ) -> Concept:
        """Create Concept from unitized segments with same unit_id."""
        # Generate document-scoped concept_id to prevent cross-document conflicts
        # Same content in different documents will have different concept IDs
        scoped_id = hashlib.md5(f"{document.id}|{unit_id}".encode("utf-8")).hexdigest()[:16]
        concept = Concept(
            id=scoped_id,  # Document-scoped concept_id
            document_id=document.id,
            order=order,
            metadata={"unit_type": "semantic_unit", "original_unit_id": unit_id},
        )
        concept.validate()  # Enforce HIER-002

        # Create Fragments for this Concept
        fragments: List[Fragment] = []
        for idx, unit_seg in enumerate(segments):
            fragment = self._create_fragment(
                concept_id=concept.id,
                segment=unit_seg,
                order=idx,
            )
            fragment.validate()  # Enforce HIER-003; embedding rules are checked later
            fragments.append(fragment)

        # Keep fragments on the concept instance for downstream processing.
        concept.fragments = fragments
        return concept

    def _create_concept_from_orphans(
        self,
        orphan_segments: List[UnitizedSegment],
        document: Document,
        source_basename: str,
        order: int,
    ) -> Concept:
        """Create Concept for segments without unit_id.

        Orphan text segments are chunked together to create more meaningful
        fragments for embedding, improving similarity scores.
        """
        # Generate deterministic concept_id from document_id + orphan content hash
        orphan_content = "".join(s.segment.content[:100] for s in orphan_segments[:5])
        content_hash = hashlib.md5(orphan_content.encode("utf-8", errors="ignore")).hexdigest()[:8]
        concept_id = f"{document.id[:8]}-orphans-{content_hash}"
        concept = Concept(
            id=concept_id,
            document_id=document.id,
            order=order,
            metadata={"unit_type": "orphans"},
        )
        concept.validate()

        # Separate text and non-text segments
        text_segments = [s for s in orphan_segments if s.segment.kind == "text"]
        non_text_segments = [s for s in orphan_segments if s.segment.kind != "text"]

        fragments: List[Fragment] = []
        idx = 0

        # Chunk text segments together for better embedding quality
        if text_segments:
            combined_text = "\n\n".join(s.segment.content for s in text_segments)
            chunker = TextChunker(chunk_size=1500, chunk_overlap=0)
            chunks = chunker.chunk(combined_text)

            for chunk in chunks:
                # Create a synthetic UnitizedSegment for the chunk
                synthetic_seg = UnitizedSegment(
                    unit_id=None,
                    role="chunked_text",
                    segment=RawSegment(
                        kind="text",
                        content=chunk,
                        language=None,
                        order=idx,
                        page=text_segments[0].segment.page if text_segments else None,
                        bbox=None,
                    ),
                )
                fragment = self._create_fragment(
                    concept_id=concept.id,
                    segment=synthetic_seg,
                    order=idx,
                )
                fragment.validate()
                fragments.append(fragment)
                idx += 1

        # Process non-text segments individually (code, image)
        for unit_seg in non_text_segments:
            fragment = self._create_fragment(
                concept_id=concept.id,
                segment=unit_seg,
                order=idx,
            )
            fragment.validate()
            fragments.append(fragment)
            idx += 1

        concept.fragments = fragments
        return concept

    def _create_fragment(
        self,
        concept_id: str,
        segment: UnitizedSegment,
        order: int,
    ) -> Fragment:
        """
        Create Fragment from UnitizedSegment.

        Args:
            concept_id: Parent Concept ID
            segment: UnitizedSegment to convert
            order: Order within Concept

        Returns:
            Fragment entity
        """
        # Map segment kind to View
        view = self._map_kind_to_view(segment.segment.kind)

        # Generate deterministic fragment_id from concept_id + order + content hash
        content_hash = hashlib.md5(
            segment.segment.content[:200].encode("utf-8", errors="ignore")
        ).hexdigest()[:8]
        fragment_id = f"{concept_id[:12]}-{order}-{content_hash}"

        fragment = Fragment(
            id=fragment_id,
            concept_id=concept_id,  # Set parent_id at creation (FRAG-IMMUT-001)
            content=segment.segment.content,
            view=view,
            language=segment.segment.language,
            order=order,
            metadata={
                "unit_role": segment.role,
                "original_kind": segment.segment.kind,
            },
        )
        return fragment

    @staticmethod
    def _map_kind_to_view(kind: str) -> View:
        """Map RawSegment kind to domain View."""
        mapping = {
            "text": View.TEXT,
            "code": View.CODE,
            "image": View.IMAGE,
        }
        return mapping.get(kind, View.TEXT)


__all__ = ["ConceptBuilder"]
