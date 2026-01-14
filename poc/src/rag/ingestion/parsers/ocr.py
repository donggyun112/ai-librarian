"""OCR and plain text parser."""

import re
from typing import List

from src.rag.shared.text_utils import TextNormalizerUtil

from ..chunking import TextChunker
from ..dto import RawSegment
from .base import BaseSegmentParser


class OcrParser(BaseSegmentParser):
    """Parse plain text files and OCR output."""

    def _merge_ocr_lines(self, raw: str, min_paragraph_len: int = 150) -> str:
        """Aggressively merge OCR lines into proper paragraphs.

        OCR output often treats each visual line as a separate paragraph,
        even separating them with double newlines. This method merges
        consecutive short lines into paragraphs.

        Strategy:
        - Split by any newline(s)
        - Merge consecutive short text lines (< min_paragraph_len)
        - Only break on: code blocks, headings, or sufficiently long text

        Args:
            raw: Raw OCR text with line breaks
            min_paragraph_len: Minimum length to consider a line as standalone paragraph

        Returns:
            Text with short lines merged into paragraphs
        """
        # Split by any newlines (single or multiple)
        lines = re.split(r'\n+', raw)
        
        merged_paragraphs = []
        current_buffer = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check if this line should start a new paragraph
            is_code = self._looks_like_code(line)
            is_heading = self._looks_like_heading(line)
            is_long_enough = len(line) >= min_paragraph_len
            
            if is_code or is_heading:
                # Flush buffer and add line separately
                if current_buffer:
                    merged_paragraphs.append(' '.join(current_buffer))
                    current_buffer = []
                merged_paragraphs.append(line)
            elif is_long_enough:
                # Long line - add to buffer then flush
                current_buffer.append(line)
                merged_paragraphs.append(' '.join(current_buffer))
                current_buffer = []
            else:
                # Short line - accumulate in buffer
                current_buffer.append(line)
                # Flush if buffer gets long enough
                combined = ' '.join(current_buffer)
                if len(combined) >= min_paragraph_len:
                    merged_paragraphs.append(combined)
                    current_buffer = []
        
        # Flush remaining buffer
        if current_buffer:
            merged_paragraphs.append(' '.join(current_buffer))
        
        return '\n\n'.join(merged_paragraphs)

    def _looks_like_code(self, line: str) -> bool:
        """Check if line looks like code."""
        code_patterns = [
            r'^肄붾뱶\s+\d+-\d+',  # Korean code markers: 肄붾뱶 1-2, 肄붾뱶 3-15
            r'^(from|import)\s+\w+',  # Python imports
            r'^(def|class|async)\s+\w+',  # Python definitions
            r'^\s*(if|for|while|try|with)\s+.*:$',  # Python control flow
            r'^(const|let|var|function)\s+',  # JavaScript
            r'[{}\[\]();]=',  # Brackets and operators
            r'^\s*#\s*\w+',  # Comments at start
        ]
        return any(re.search(p, line) for p in code_patterns)

    def _looks_like_heading(self, line: str) -> bool:
        """Check if line looks like a heading."""
        # Numbered headings like "1.2 ?쒕ぉ" or "Chapter 1"
        if re.match(r'^[\d\.]+\s+\S', line) and len(line) < 100:
            return True
        # All caps short lines
        if line.isupper() and len(line) < 50:
            return True
        # Markdown headings
        if line.startswith('#'):
            return True
        return False

    def parse_text(self, raw: str, is_ocr: bool = False, chunk_size: int = 1200, chunk_overlap: int = 200) -> List[RawSegment]:
        """
        Parse raw text into segments.

        Args:
            raw: Raw text content
            is_ocr: If True, merge lines and split into chunks with overlap
            chunk_size: Size of each chunk for OCR text (default 1200)
            chunk_overlap: Overlap between chunks for OCR text (default 200)

        Returns:
            List of RawSegment objects (text or code)
        """
        raw = self.preprocessor.normalize(raw)
        
        # For OCR text: merge lines aggressively and split into chunks
        if is_ocr:
            merged = self._merge_ocr_lines(raw)
            if merged.strip():
                chunker = TextChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
                chunks = chunker.chunk(merged)
                # Detect code blocks in each chunk
                segments = []
                for i, chunk in enumerate(chunks):
                    if self.preprocessor.is_code_block(chunk):
                        lang = self.preprocessor.guess_code_lang(chunk)
                        segments.append(RawSegment("code", chunk, lang, i))
                    else:
                        segments.append(RawSegment("text", chunk, None, i))
                return segments
            return []

        # Normal mode: split by paragraphs
        paragraphs = self.preprocessor.split_paragraph(raw)
        segments: List[RawSegment] = []
        for idx, paragraph in enumerate(paragraphs):
            if self.preprocessor.is_code_block(paragraph):
                lang = self.preprocessor.guess_code_lang(paragraph)
                segments.append(RawSegment("code", paragraph, lang, idx))
            else:
                segments.append(RawSegment("text", paragraph, None, idx))
        return segments

    def parse(self, path: str) -> List[RawSegment]:
        """
        Parse a plain text file.

        Args:
            path: Path to text file

        Returns:
            List of RawSegment objects
        """
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            raw = handle.read()
        return self.parse_text(raw)


__all__ = ["OcrParser"]

