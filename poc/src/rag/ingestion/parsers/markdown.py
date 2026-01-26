"""Markdown parser with fence and image extraction."""

import re
from typing import List, Optional

from src.rag.shared.text_utils import TextNormalizerUtil

from ..dto import RawSegment
from .base import BaseSegmentParser


class MarkdownParser(BaseSegmentParser):
    """Parse Markdown files into segments (text, code, images)."""

    MD_FENCE_RE = re.compile(r"^\s*```\s*([A-Za-z0-9_+-]*)\s*$")
    MD_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
    PAGE_BREAK_LINE_RE = re.compile(r"^\s*-{3,}\s*Page Break\s*-{3,}\s*$", re.I)

    def _norm_lang(self, tag: Optional[str]) -> Optional[str]:
        """Normalize language tags."""
        if not tag:
            return None
        tag = tag.strip().lower()
        if tag in ("py", "python", "python3"):
            return "python"
        if tag in ("js", "javascript", "node", "jsx", "ts", "tsx", "typescript"):
            return "javascript"
        return tag

    def parse_text(self, raw: str) -> List[RawSegment]:
        """
        Parse Markdown text into segments.

        Args:
            raw: Raw Markdown content

        Returns:
            List of RawSegment objects (text, code, image)
        """
        segments: List[RawSegment] = []
        order = 0
        in_fence = False
        fence_lang: Optional[str] = None
        fence_buf: List[str] = []
        text_buf: List[str] = []

        def flush_text_buf() -> None:
            nonlocal order
            if not text_buf:
                return
            text = "\n".join(text_buf)
            text_buf.clear()
            pos = 0
            for match in self.MD_IMAGE_RE.finditer(text):
                pre = text[pos : match.start()]
                if pre.strip():
                    normalized = self.preprocessor.normalize(pre)
                    if normalized:
                        segments.append(RawSegment("text", normalized, None, order))
                        order += 1
                alt = (match.group(1) or "").strip()
                url = (match.group(2) or "").strip()
                payload = (alt + "\n" + url).strip()
                segments.append(RawSegment("image", payload, "image", order))
                order += 1
                pos = match.end()
            tail = text[pos:]
            if tail.strip():
                normalized_tail = self.preprocessor.normalize(tail)
                if normalized_tail:
                    segments.append(RawSegment("text", normalized_tail, None, order))
                    order += 1

        for line in raw.splitlines():
            fence_match = self.MD_FENCE_RE.match(line)
            if fence_match:
                if not in_fence:
                    flush_text_buf()
                    fence_lang = self._norm_lang((fence_match.group(1) or "").strip())
                    in_fence = True
                    fence_buf = []
                else:
                    code = "\n".join(fence_buf)
                    lang = fence_lang or self._norm_lang(
                        self.preprocessor.guess_code_lang(code) or "unknown"
                    )
                    segments.append(RawSegment("code", code, lang, order))
                    order += 1
                    in_fence = False
                    fence_lang = None
                    fence_buf = []
                continue

            if in_fence:
                fence_buf.append(line)
                continue

            text_buf.append(line)

        if in_fence and fence_buf:
            code = "\n".join(fence_buf)
            lang = fence_lang or self._norm_lang(
                self.preprocessor.guess_code_lang(code) or "unknown"
            )
            segments.append(RawSegment("code", code, lang, order))
            order += 1
        flush_text_buf()
        return segments

    def parse(self, path: str) -> List[RawSegment]:
        """
        Parse a Markdown file.

        Args:
            path: Path to Markdown file

        Returns:
            List of RawSegment objects
        """
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            raw = handle.read()
        return self.parse_text(raw)


__all__ = ["MarkdownParser"]
