"""PyMuPDF-based PDF parser with Gemini Vision OCR support.

This module provides structured block-level PDF parsing using PyMuPDF (fitz),
with optional Gemini Vision API integration for OCR on image blocks.

Block types handled:
- type=0: Text blocks -> kind="text"
- type=1: Image blocks -> kind="image" (OCR via Gemini if enabled)
"""

import base64
import json
import os
import re
from typing import List, Optional, Protocol

import fitz  # PyMuPDF
import google.generativeai as genai
from loguru import logger

from src.rag.shared.text_utils import TextNormalizerUtil

from ..dto import RawSegment
from .base import BaseSegmentParser
from .ocr import OcrParser


class OcrProvider(Protocol):
    """Protocol for OCR providers."""

    def ocr_image(self, image_bytes: bytes, mime_type: str = "image/png") -> str:
        """Extract text from image bytes."""
        ...


class GeminiVisionOcr:
    """OCR using Google Gemini Vision API.

    Uses the Gemini generative model to extract text from images.
    Requires GOOGLE_API_KEY environment variable.

    Example:
        >>> ocr = GeminiVisionOcr()
        >>> text = ocr.ocr_image(image_bytes)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-2.0-flash",
    ) -> None:
        """Initialize Gemini Vision OCR.

        Args:
            api_key: Google API key. Falls back to GOOGLE_API_KEY env var.
            model: Gemini model to use for vision tasks.
        """
        key = api_key or os.getenv("GOOGLE_API_KEY")
        if not key:
            raise RuntimeError("GOOGLE_API_KEY is required for Gemini Vision OCR")

        genai.configure(api_key=key)
        self._model = genai.GenerativeModel(model)

    def ocr_image(self, image_bytes: bytes, mime_type: str = "image/png") -> str:
        """Extract text from image using Gemini Vision.

        Args:
            image_bytes: Raw image bytes
            mime_type: MIME type of image (image/png, image/jpeg, etc.)

        Returns:
            Extracted text from image
        """
        try:
            # Use explicit Part object (SDK recommended approach)
            # Avoids potential double base64 encoding issues with dict format
            image_part = genai.protos.Part(
                inline_data=genai.protos.Blob(
                    mime_type=mime_type,
                    data=image_bytes,
                )
            )

            response = self._model.generate_content(
                [
                    "You are an expert OCR system for technical programming documents. "
                    "Extract ALL text from this image with high accuracy. "
                    "Rules: "
                    "1. Preserve all characters exactly (supports multilingual content). "
                    "2. Recognize code blocks and maintain their formatting with indentation. "
                    "3. Merge lines within the same paragraph into continuous text. "
                    "4. Separate paragraphs with blank lines. "
                    "5. Do not add any commentary or formatting markers. "
                    "6. Return only the extracted text, nothing else.",
                    image_part,
                ]
            )
            
            # Check if response was blocked or has no candidates
            if not response.candidates:
                # Detailed diagnostic logging

                
                logger.warning("OCR: Gemini Vision returned no candidates")
                return ""
            
            # Safely access text from first candidate
            candidate = response.candidates[0]
            if not candidate.content or not candidate.content.parts:
                return ""
            
            text = "".join(part.text for part in candidate.content.parts if hasattr(part, 'text'))
            return text.strip()
        except Exception as e:
            logger.warning(f"OCR: Gemini Vision OCR failed: {e}")
            return ""


class PyMuPdfParser(BaseSegmentParser):
    """PyMuPDF-based structured PDF parser.

    Extracts content from PDF files using PyMuPDF's block-level API,
    providing structured access to text blocks, images, and layout info.

    Features:
    - Block-level text extraction with bbox coordinates
    - Image block detection with optional Gemini Vision OCR
    - Page number tracking
    - Preserves reading order

    Example:
        >>> parser = PyMuPdfParser(preprocessor, ocr=GeminiVisionOcr())
        >>> segments = parser.parse("document.pdf")
    """

    def __init__(
        self,
        preprocessor: TextNormalizerUtil,
        *,
        ocr: Optional[OcrProvider] = None,
        min_text_length: int = 10,
        enable_auto_ocr: bool = False,
        force_ocr: bool = False,
        use_cache: bool = True,
    ) -> None:
        """Initialize PyMuPDF parser.

        Args:
            preprocessor: Text preprocessor for normalization
            ocr: OCR provider for image blocks and page-level OCR (Gemini Vision)
            min_text_length: Minimum text length to include (filters noise)
            enable_auto_ocr: Enable Gemini Vision OCR fallback for sparse text PDFs
            force_ocr: Force OCR mode - render all pages as images and OCR
            use_cache: Enable OCR result caching (.pdf.ocr.md files)
        """
        super().__init__(preprocessor)
        self.ocr = ocr
        self.min_text_length = min_text_length
        self.enable_auto_ocr = enable_auto_ocr
        self.force_ocr = force_ocr
        self.use_cache = use_cache
        self.text_parser = OcrParser(preprocessor)

    def parse(self, path: str) -> List[RawSegment]:
        """Parse PDF file into structured segments.

        Implements Vision Invocation Policy from implementation_plan.md:
        1. Always try deterministic text extraction first
        2. Check text block existence
        3. Check text sufficiency (total_chars >= 100 AND alpha_ratio >= 0.3)
        4. Check code patterns (>= 2 patterns)
        5. Handle image-only documents (text_blocks == 0 AND image_blocks > 0)

        Args:
            path: Path to PDF file

        Returns:
            List of RawSegment objects with text, images, and metadata
        """
        try:
            doc = fitz.open(path)
        except Exception as e:
            logger.warning(f"Parse: Failed to open PDF: {e}")
            return []

        # === STEP 1: ?띿뒪??異붿텧 ?쒕룄 ===
        deterministic_segments, total_text_blocks, total_image_blocks = (
            self._extract_all_blocks(doc)
        )

        # === STEP 2: ?띿뒪??釉붾줉 議댁옱 ?щ? ===
        if total_text_blocks == 0:
            # === STEP 5: ?대?吏 以묒떖 臾몄꽌 泥섎━ (Rule 3) ===
            if total_image_blocks > 0 and self.ocr:
                return self._handle_image_only_document(doc, path)
            else:
                # 鍮??먯긽 臾몄꽌 - OCR ?대갚 ?뺤콉 ?뺤씤
                return self._handle_empty_document(doc, path, deterministic_segments)

        # === STEP 3: ?띿뒪??異⑸텇??寃??(Rule 1) ===
        if self._is_text_sufficient(deterministic_segments):
            logger.info(
                f"Policy: Text sufficient ({len(deterministic_segments)} segments), "
                "skipping Vision"
            )
            doc.close()
            return self._detect_code_blocks(deterministic_segments)

        # === STEP 4: 肄붾뱶 ?⑦꽩 寃??(Rule 2) ===
        if self._has_code_patterns(deterministic_segments):
            logger.info("Policy: Code patterns detected, preserving deterministic extraction")
            doc.close()
            return self._detect_code_blocks(deterministic_segments)

        # === ?띿뒪??遺議?- Vision ?몄텧 議곌굔 ?뺤씤 ===
        if self.force_ocr and self.ocr:
            return self._handle_force_ocr(doc, path)

        if self.enable_auto_ocr and self.ocr:
            return self._handle_auto_ocr(doc, path, deterministic_segments)

        # Vision 誘몄궗??- deterministic 寃곌낵 諛섑솚
        doc.close()
        return self._detect_code_blocks(deterministic_segments)

    def _extract_all_blocks(self, doc: fitz.Document) -> tuple[List[RawSegment], int, int]:
        """Extract all blocks from all pages with counts.

        Args:
            doc: PyMuPDF document object

        Returns:
            Tuple of (segments, total_text_blocks, total_image_blocks)
        """
        segments: List[RawSegment] = []
        total_text_blocks = 0
        total_image_blocks = 0
        order = 0

        for page_num in range(len(doc)):
            page = doc[page_num]
            page_segments, order, text_count, image_count = self._process_page(
                page, page_num, order
            )
            segments.extend(page_segments)
            total_text_blocks += text_count
            total_image_blocks += image_count

        # Merge adjacent text blocks to improve embedding quality
        merged_segments = self._merge_adjacent_text_blocks(segments)
        logger.info(f"Merge: {len(segments)} segments ??{len(merged_segments)} merged segments")

        return merged_segments, total_text_blocks, total_image_blocks

    def _merge_adjacent_text_blocks(
        self,
        segments: List[RawSegment],
        max_merge_chars: int = 1500,
        overlap_chars: int = 0,
    ) -> List[RawSegment]:
        """Merge adjacent text segments to create more meaningful chunks.

        Adjacent text segments on the same page are merged until they reach
        max_merge_chars. Code/image blocks act as boundaries.

        Args:
            segments: List of RawSegment objects
            max_merge_chars: Maximum characters per merged segment
            overlap_chars: Characters to overlap between chunks (default 0, Parent-Child ?꾪궎?띿쿂?먯꽌 遺덊븘??

        Returns:
            List of merged RawSegment objects
        """
        if not segments:
            return []

        merged: List[RawSegment] = []
        buffer: List[RawSegment] = []
        buffer_chars = 0
        current_page = None
        overlap_buffer: List[RawSegment] = []  # Segments to carry over for overlap

        for seg in segments:
            if seg.kind == "text":
                # Check if page changed - flush buffer (no overlap across pages)
                if current_page is not None and seg.page != current_page:
                    if buffer:
                        merged.append(self._flush_text_buffer(buffer))
                        buffer = []
                        buffer_chars = 0
                        overlap_buffer = []  # Reset overlap on page change

                current_page = seg.page
                buffer.append(seg)
                buffer_chars += len(seg.content)

                # Flush if exceeds max chars
                if buffer_chars >= max_merge_chars:
                    merged.append(self._flush_text_buffer(buffer))
                    # Keep trailing segments for overlap
                    overlap_buffer = self._get_overlap_segments(buffer, overlap_chars)
                    buffer = list(overlap_buffer)  # Start new buffer with overlap
                    buffer_chars = sum(len(s.content) for s in buffer)
            else:
                # Non-text block (code/image) - flush text buffer first
                if buffer:
                    merged.append(self._flush_text_buffer(buffer))
                    buffer = []
                    buffer_chars = 0
                    overlap_buffer = []
                    current_page = None
                merged.append(seg)

        # Flush remaining buffer
        if buffer:
            merged.append(self._flush_text_buffer(buffer))

        return merged

    def _get_overlap_segments(
        self, buffer: List[RawSegment], overlap_chars: int
    ) -> List[RawSegment]:
        """Get trailing segments from buffer for overlap.

        Args:
            buffer: Current buffer of segments
            overlap_chars: Target overlap character count

        Returns:
            List of segments to carry over (from end of buffer)
        """
        if not buffer or overlap_chars <= 0:
            return []

        # Work backwards from end of buffer
        overlap_segs: List[RawSegment] = []
        chars_collected = 0

        for seg in reversed(buffer):
            if chars_collected >= overlap_chars:
                break
            overlap_segs.insert(0, seg)
            chars_collected += len(seg.content)

        return overlap_segs

    def _flush_text_buffer(self, buffer: List[RawSegment]) -> RawSegment:
        """Combine buffered text segments into a single segment.

        Args:
            buffer: List of text RawSegment objects to merge

        Returns:
            Single merged RawSegment
        """
        if len(buffer) == 1:
            return buffer[0]

        # Combine content with paragraph breaks
        combined_content = "\n\n".join(seg.content for seg in buffer)

        # Use first segment's metadata
        first = buffer[0]
        return RawSegment(
            kind="text",
            content=combined_content,
            language=None,
            order=first.order,
            page=first.page,
            bbox=first.bbox,
        )

    def _handle_image_only_document(
        self, doc: fitz.Document, path: str
    ) -> List[RawSegment]:
        """Handle image-only documents (Rule 3).

        When text_blocks == 0 AND image_blocks > 0, invoke Vision OCR.

        Args:
            doc: PyMuPDF document object
            path: Path to PDF file

        Returns:
            OCR segments or empty list
        """
        logger.info("Policy: Image-only document detected, invoking Vision OCR")

        # Check cache first
        cache_path = path + ".ocr.json"
        if self.use_cache and os.path.exists(cache_path):
            logger.info(f"Cache: Loading OCR cache from {os.path.basename(cache_path)}")
            doc.close()
            return self._load_cache(cache_path)

        # Run OCR
        segments = self._ocr_all_pages(doc)
        doc.close()

        # Save to cache
        if self.use_cache and segments:
            self._save_cache(cache_path, segments)
            logger.info(f"Cache: Saved OCR cache to {os.path.basename(cache_path)}")

        return segments

    def _handle_empty_document(
        self, doc: fitz.Document, path: str, fallback: List[RawSegment]
    ) -> List[RawSegment]:
        """Handle empty or corrupted documents.

        When text_blocks == 0 AND image_blocks == 0.

        Args:
            doc: PyMuPDF document object
            path: Path to PDF file
            fallback: Fallback segments (likely empty)

        Returns:
            Fallback segments or OCR result if available
        """
        logger.info("Policy: Empty document detected (no text or image blocks)")

        # Try OCR fallback if enabled
        if self.enable_auto_ocr and self.ocr:
            logger.info("Policy: Attempting OCR fallback for empty document")
            try:
                segments = self._ocr_all_pages(doc)
                doc.close()
                if segments:
                    return segments
            except Exception as e:
                logger.warning(f"Parse: OCR fallback failed: {e}")

        doc.close()
        return fallback

    def _handle_force_ocr(self, doc: fitz.Document, path: str) -> List[RawSegment]:
        """Handle force_ocr mode.

        Args:
            doc: PyMuPDF document object
            path: Path to PDF file

        Returns:
            OCR segments
        """
        cache_path = path + ".ocr.json"

        # Check cache first
        if self.use_cache and os.path.exists(cache_path):
            logger.info(f"Cache: Loading OCR cache from {os.path.basename(cache_path)}")
            doc.close()
            return self._load_cache(cache_path)

        logger.info("Policy: force_ocr enabled, invoking Vision OCR")
        segments = self._ocr_all_pages(doc)
        doc.close()

        # Save to cache
        if self.use_cache and segments:
            self._save_cache(cache_path, segments)
            logger.info(f"Cache: Saved OCR cache to {os.path.basename(cache_path)}")

        return segments

    def _handle_auto_ocr(
        self, doc: fitz.Document, path: str, fallback: List[RawSegment]
    ) -> List[RawSegment]:
        """Handle enable_auto_ocr mode for sparse text.

        Args:
            doc: PyMuPDF document object
            path: Path to PDF file
            fallback: Fallback segments (deterministic extraction)

        Returns:
            OCR segments or fallback
        """
        logger.info("Policy: Sparse text detected, falling back to Vision OCR")

        try:
            segments = self._ocr_all_pages(doc)

            if segments:
                # Save to cache
                if self.use_cache:
                    cache_path = path + ".ocr.json"
                    self._save_cache(cache_path, segments)
                    logger.info(f"Cache: Saved OCR cache to {os.path.basename(cache_path)}")
                doc.close()
                return segments
        except Exception as e:
            logger.warning(f"Parse: Vision OCR fallback failed: {e}")

        doc.close()
        # Rule 4: Vision ?ㅽ뙣 ???먮낯 蹂댁〈
        return self._detect_code_blocks(fallback)

    def _process_page(
        self, page: fitz.Page, page_num: int, order: int
    ) -> tuple[List[RawSegment], int, int, int]:
        """Process a single PDF page.

        Args:
            page: PyMuPDF page object
            page_num: Page number (0-indexed)
            order: Current segment order counter

        Returns:
            Tuple of (segments list, updated order, text_block_count, image_block_count)
        """
        segments: List[RawSegment] = []
        blocks = page.get_text("dict", flags=11)["blocks"]

        text_block_count = 0
        image_block_count = 0

        for block in blocks:
            block_type = block.get("type", 0)
            bbox = (
                block.get("bbox", (0, 0, 0, 0))
                if "bbox" in block
                else (0, 0, 0, 0)
            )

            if block_type == 0:  # Text block
                text_block_count += 1
                text = self._extract_text_block(block)
                if text and len(text.strip()) >= self.min_text_length:
                    normalized = self.preprocessor.normalize(text)
                    segments.append(
                        RawSegment(
                            kind="text",
                            content=normalized,
                            language=None,
                            order=order,
                            page=page_num,
                            bbox=bbox,
                        )
                    )
                    order += 1

            elif block_type == 1:  # Image block
                image_block_count += 1
                segment = self._process_image_block(block, page_num, order, bbox)
                if segment:
                    segments.append(segment)
                    order += 1

        return segments, order, text_block_count, image_block_count

    def _extract_text_block(self, block: dict) -> str:
        """Extract text from a text block.

        Args:
            block: PyMuPDF block dict with 'lines' containing 'spans'

        Returns:
            Extracted text string
        """
        lines = []
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            line_text = "".join(span.get("text", "") for span in spans)
            if line_text.strip():
                lines.append(line_text)
        return "\n".join(lines)

    def _process_image_block(
        self,
        block: dict,
        page_num: int,
        order: int,
        bbox: tuple,
    ) -> Optional[RawSegment]:
        """Process an image block with optional OCR.

        Args:
            block: PyMuPDF image block dict
            page_num: Page number
            order: Segment order
            bbox: Bounding box coordinates

        Returns:
            RawSegment with OCR text or None if no text extracted
        """
        if not self.ocr:
            return None

        # Extract image bytes
        image_bytes = block.get("image")
        if not image_bytes:
            return None

        # Determine MIME type from extension
        ext = block.get("ext", "png").lower()
        mime_map = {
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "gif": "image/gif",
            "bmp": "image/bmp",
            "tiff": "image/tiff",
            "webp": "image/webp",
        }
        mime_type = mime_map.get(ext, "image/png")

        # Run OCR
        text = self.ocr.ocr_image(image_bytes, mime_type)
        if not text or len(text.strip()) < self.min_text_length:
            return None

        normalized = self.preprocessor.normalize(text)
        return RawSegment(
            kind="image",
            content=normalized,
            language="image",
            order=order,
            page=page_num,
            bbox=bbox,
        )

    def _detect_code_blocks(self, segments: List[RawSegment]) -> List[RawSegment]:
        """Detect and relabel code blocks within text segments.

        Uses heuristics to identify code-like content and updates
        the segment kind and language accordingly.

        Args:
            segments: List of RawSegment objects

        Returns:
            Updated list with code blocks properly labeled
        """
        result = []
        for seg in segments:
            if seg.kind == "text":
                # Use OcrParser's code detection logic
                sub_segments = self.text_parser.parse_text(seg.content, is_ocr=True)
                for sub in sub_segments:
                    result.append(
                        RawSegment(
                            kind=sub.kind,
                            content=sub.content,
                            language=sub.language,
                            order=seg.order,
                            page=seg.page,
                            bbox=seg.bbox,
                        )
                    )
            else:
                result.append(seg)
        return result

    def _is_text_sufficient(
        self,
        segments: List[RawSegment],
        min_total_chars: int = 100,
        min_alpha_ratio: float = 0.3,
    ) -> bool:
        """Check if extracted text is sufficient (Vision NOT needed).

        Deterministic check based on character count and alphanumeric ratio.

        Args:
            segments: Extracted segments
            min_total_chars: Minimum total characters (default 100)
            min_alpha_ratio: Minimum ratio of alphanumeric characters (default 0.3)

        Returns:
            True if text is sufficient, Vision should NOT be called
        """
        total_text = "".join(s.content for s in segments if s.kind == "text")
        total_chars = len(total_text.strip())

        if total_chars < min_total_chars:
            return False

        alpha_count = sum(1 for c in total_text if c.isalnum())
        ratio = alpha_count / max(1, len(total_text))

        return ratio >= min_alpha_ratio

    def _has_code_patterns(self, segments: List[RawSegment], min_patterns: int = 2) -> bool:
        """Check if segments contain code-like patterns.

        If code patterns are detected, deterministic extraction should be preserved
        and Vision should NOT be called.

        Args:
            segments: Extracted segments
            min_patterns: Minimum code patterns to detect (default 2)

        Returns:
            True if code patterns detected, Vision should NOT be called
        """
        code_patterns = [
            r'\bdef\s+\w+',           # Python function
            r'\bclass\s+\w+',         # Python/JS class
            r'\bimport\s+\w+',        # Python import
            r'\bfrom\s+\w+\s+import', # Python from import
            r'\bfunction\s+\w+',      # JavaScript function
            r'\bconst\s+\w+',         # JavaScript const
            r'\blet\s+\w+',           # JavaScript let
            r'\bvar\s+\w+',           # JavaScript var
            r'\basync\s+',            # async keyword
            r'\bawait\s+',            # await keyword
        ]

        all_text = " ".join(s.content for s in segments if s.kind == "text")
        pattern_count = sum(1 for p in code_patterns if re.search(p, all_text))

        return pattern_count >= min_patterns

    def _should_fallback_to_vision(self, segments: List[RawSegment]) -> bool:
        """Determine if Vision fallback is allowed based on deterministic policy.

        Vision is ONLY allowed when:
        1. Text is NOT sufficient (< 100 chars OR alpha_ratio < 0.3)
        2. AND no code patterns detected

        Args:
            segments: Extracted segments

        Returns:
            True if Vision fallback is allowed
        """
        # Rule 1: If text is sufficient, never fall back to Vision
        if self._is_text_sufficient(segments):
            return False

        # Rule 2: If code patterns exist, preserve deterministic output
        if self._has_code_patterns(segments):
            logger.info("Policy: Code patterns detected, preserving deterministic extraction")
            return False

        # Only allow fallback if both checks fail
        return True

    def _is_sparse(
        self,
        segments: List[RawSegment],
        min_total_chars: int = 500,
        min_alpha_ratio: float = 0.2,
    ) -> bool:
        """Legacy sparse check - now delegates to _should_fallback_to_vision.

        Kept for backward compatibility.
        """
        return self._should_fallback_to_vision(segments)

    def _ocr_all_pages(self, doc: fitz.Document) -> List[RawSegment]:
        """OCR all pages using Gemini Vision.

        Renders each page as an image and sends to Gemini Vision for OCR.

        Args:
            doc: PyMuPDF document object

        Returns:
            List of RawSegment from OCR text
        """
        if not self.ocr:
            logger.warning("Parse: No OCR provider available for page-level OCR")
            return []

        segments: List[RawSegment] = []
        order = 0

        for page_num in range(len(doc)):
            page = doc[page_num]

            # Render page as image (~150 DPI for good OCR quality)
            # fitz.Matrix(scale_x, scale_y) - 2x scale = ~144 DPI from 72 DPI base
            scale = 3.0  # 3x scale = ~216 DPI for better OCR quality
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
            image_bytes = pix.tobytes("png")

            # OCR via Gemini Vision
            try:
                text = self.ocr.ocr_image(image_bytes, "image/png")
                if text and len(text.strip()) >= self.min_text_length:
                    # Parse the OCR text to detect code blocks (with OCR line merging)
                    page_segments = self.text_parser.parse_text(text, is_ocr=True)
                    for seg in page_segments:
                        segments.append(
                            RawSegment(
                                kind=seg.kind,
                                content=seg.content,
                                language=seg.language,
                                order=order,
                                page=page_num,
                                bbox=None,
                            )
                        )
                        order += 1
            except Exception as e:
                logger.warning(f"Parse: Gemini Vision OCR failed for page {page_num}: {e}")

        return segments

    def _save_cache(self, cache_path: str, segments: List[RawSegment]) -> None:
        """Save OCR results to cache file.

        Format: JSON for exact reconstruction of segments.
        """
        try:
            # Use .json extension instead of .md
            json_path = cache_path.replace('.ocr.md', '.ocr.json')
            data = [
                {
                    "kind": seg.kind,
                    "content": seg.content,
                    "language": seg.language,
                    "order": seg.order,
                    "page": seg.page,
                }
                for seg in segments
            ]
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.info(f"Cache: Failed to save cache: {e}")

    def _load_cache(self, cache_path: str) -> List[RawSegment]:
        """Load OCR results from cache file.

        Loads JSON cache and reconstructs RawSegment objects.
        """
        try:
            # Check for JSON cache first
            json_path = cache_path.replace('.ocr.md', '.ocr.json')
            if os.path.exists(json_path):
                cache_path = json_path
            
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            segments = [
                RawSegment(
                    kind=item["kind"],
                    content=item["content"],
                    language=item.get("language"),
                    order=item["order"],
                    page=item.get("page"),
                    bbox=None,
                )
                for item in data
            ]
            return segments
        except Exception as e:
            logger.info(f"Cache: Failed to load cache: {e}")
            return []


__all__ = ["GeminiVisionOcr", "PyMuPdfParser", "OcrProvider"]
