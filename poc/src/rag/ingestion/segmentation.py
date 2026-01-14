"""Semantic unit grouping for segments."""

import hashlib
from typing import List

from .dto import RawSegment, UnitizedSegment


class SemanticUnitGrouper:
    """
    Group segments into semantic units that preserve Python/JS adjacency.

    A semantic unit groups related content together (e.g., explanatory text + code).
    """

    def __init__(
        self,
        attach_pre_text: bool = True,
        attach_post_text: bool = False,
        bridge_text_max: int = 0,
        max_pre_text_chars: int = 4000,
        text_unit_threshold: int = 500,
    ):
        """
        Initialize SemanticUnitGrouper.

        Args:
            attach_pre_text: Attach text before Python code to the same unit
            attach_post_text: Attach text after JavaScript code to the same unit
            bridge_text_max: Maximum text segments to bridge between Python and JS
            max_pre_text_chars: Maximum characters of pre-text to buffer
            text_unit_threshold: Min chars for text-only semantic unit (prevents orphans)
        """
        self.attach_pre_text = attach_pre_text
        self.attach_post_text = attach_post_text
        self.bridge_text_max = bridge_text_max
        self.max_pre_text_chars = max_pre_text_chars
        self.text_unit_threshold = text_unit_threshold

    def unitize(self, segments: List[RawSegment]) -> List[UnitizedSegment]:
        """
        Group segments into semantic units.

        Args:
            segments: List of RawSegment objects

        Returns:
            List of UnitizedSegment objects with unit_id assignments
        """
        output: List[UnitizedSegment] = []
        text_buffer: List[RawSegment] = []
        text_buffer_chars = 0
        i, total = 0, len(segments)

        while i < total:
            segment = segments[i]
            if segment.kind == "text":
                text_buffer.append(segment)
                text_buffer_chars += len(segment.content)
                # Check if we exceed max_pre_text_chars - flush as text-only unit if threshold met
                while text_buffer_chars > self.max_pre_text_chars and text_buffer:
                    # If accumulated text exceeds threshold, create a text-only semantic unit
                    if text_buffer_chars >= self.text_unit_threshold:
                        text_unit_id = self._generate_text_unit_id(text_buffer)
                        for buffered in text_buffer:
                            output.append(UnitizedSegment(text_unit_id, "text_unit", buffered))
                        text_buffer.clear()
                        text_buffer_chars = 0
                    else:
                        old = text_buffer.pop(0)
                        text_buffer_chars -= len(old.content)
                        output.append(UnitizedSegment(None, "other", old))
                i += 1
                continue

            if segment.kind == "code" and segment.language == "python":
                # Generate deterministic unit_id from content hash
                unit_id = self._generate_unit_id(segment, text_buffer if self.attach_pre_text else [])
                if self.attach_pre_text and text_buffer:
                    for buffered in text_buffer:
                        output.append(UnitizedSegment(unit_id, "pre_text", buffered))
                    text_buffer.clear()
                    text_buffer_chars = 0
                else:
                    while text_buffer:
                        output.append(UnitizedSegment(None, "other", text_buffer.pop(0)))
                    text_buffer_chars = 0

                while i < total and segments[i].kind == "code" and segments[i].language == "python":
                    output.append(UnitizedSegment(unit_id, "python", segments[i]))
                    i += 1

                bridged = 0
                while (
                    bridged < self.bridge_text_max
                    and i < total
                    and segments[i].kind == "text"
                ):
                    output.append(UnitizedSegment(unit_id, "bridge_text", segments[i]))
                    i += 1
                    bridged += 1

                if i < total and segments[i].kind == "code" and segments[i].language == "javascript":
                    while i < total and segments[i].kind == "code" and segments[i].language == "javascript":
                        output.append(UnitizedSegment(unit_id, "javascript", segments[i]))
                        i += 1

                    if self.attach_post_text:
                        while i < total and segments[i].kind == "text":
                            if (
                                i + 1 < total
                                and segments[i + 1].kind == "code"
                                and segments[i + 1].language == "python"
                            ):
                                text_buffer.append(segments[i])
                                text_buffer_chars += len(segments[i].content)
                                i += 1
                                break
                            output.append(UnitizedSegment(unit_id, "post_text", segments[i]))
                            i += 1
                continue

            if segment.kind == "code" and segment.language == "javascript":
                while text_buffer:
                    output.append(UnitizedSegment(None, "other", text_buffer.pop(0)))
                    text_buffer_chars = 0
                output.append(UnitizedSegment(None, "other", segment))
                i += 1
                continue

            while text_buffer:
                output.append(UnitizedSegment(None, "other", text_buffer.pop(0)))
                text_buffer_chars = 0
            output.append(UnitizedSegment(None, "other", segment))
            i += 1

        # Handle remaining text buffer - create text-only unit if threshold met
        if text_buffer:
            if text_buffer_chars >= self.text_unit_threshold:
                text_unit_id = self._generate_text_unit_id(text_buffer)
                for buffered in text_buffer:
                    output.append(UnitizedSegment(text_unit_id, "text_unit", buffered))
            else:
                for buffered in text_buffer:
                    output.append(UnitizedSegment(None, "other", buffered))
        return output

    def _generate_unit_id(
        self,
        code_segment: RawSegment,
        pre_text_segments: List[RawSegment],
    ) -> str:
        """Generate deterministic unit_id from content hash.

        Uses the code content and first 200 chars of pre-text to create
        a stable, reproducible unit identifier.

        Args:
            code_segment: The Python code segment
            pre_text_segments: Pre-text segments to include in hash

        Returns:
            16-character hex string as unit_id
        """
        # Combine pre-text (limited) and code content for hash
        pre_text = "".join(s.content[:100] for s in pre_text_segments[-2:])  # Last 2 segments
        content = f"{pre_text}|{code_segment.content[:500]}"
        return hashlib.md5(content.encode("utf-8", errors="ignore")).hexdigest()[:16]

    def _generate_text_unit_id(self, text_segments: List[RawSegment]) -> str:
        """Generate deterministic unit_id for text-only units.

        Uses the combined text content to create a stable identifier.

        Args:
            text_segments: List of text segments to include in hash

        Returns:
            16-character hex string as unit_id prefixed with 'txt-'
        """
        content = "".join(s.content[:200] for s in text_segments[:5])  # First 5 segments
        return "txt-" + hashlib.md5(content.encode("utf-8", errors="ignore")).hexdigest()[:12]


__all__ = ["SemanticUnitGrouper"]
