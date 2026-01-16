"""Validators for embedding eligibility.

Implements domain rules:
- FRAG-LEN-001: Fragments < 10 chars MUST NOT be embedded
- EMBED-BAN-001~006: Forbidden content types

Supports both Korean and English language content.
"""

import re
from typing import Optional

from src.rag.domain import Fragment


class EmbeddingValidator:
    """
    Validate whether a Fragment is eligible for embedding.

    Rules enforced:
    - FRAG-LEN-001: Minimum 10 characters
    - EMBED-BAN-003: Reject boilerplate text
    - EMBED-BAN-004: Reject page numbers/headers/footers
    - EMBED-BAN-006: Reject pure reference text

    Supports both Korean and English language patterns.
    """

    MIN_LENGTH = 10  # FRAG-LEN-001

    # Copyright-related patterns (Korean + English)
    COPYRIGHT_PATTERNS = [
        r"^(?i:copyright|COPYRIGHT|저작권)\s+©?\s*\d{4}",
        r"^(?i:all\s+rights\s+reserved|ALL\s+RIGHTS\s+RESERVED|저작권\s*소유|무단\s*전재)",
    ]

    # Page number patterns (Korean + English)
    PAGE_NUMBER_PATTERNS = [
        r"^\s*(?i:page|PAGE|페이지|쪽)\s*\d+\s*$",
        r"^\s*\d+\s*(?i:page|PAGE|페이지|쪽)\s*$",
        r"^\s*\d+\s*$",  # Pure numbers
    ]

    # Reference text patterns (Korean + English)
    REFERENCE_PATTERNS = [
        # English: "See Figure 3", "Refer to Table 1"
        r"^(?i:see|refer\s+to|reference)\s+(?i:figure|table|section|chapter|appendix)\s+\d+",
        # Korean: "그림 3 참조", "표 1 참고", "3장 참조"
        r"(그림|표|도표|사진|이미지|그래프|차트|코드)\s*\d+\s*(참조|참고|보기|확인)",
        r"(장|절)?\s*\d+\s*(장|절|항)\s*(참조|참고|보기)",
        r"(위|아래|다음|이전)\s*(장|절)?\s*(예제|예시|설명|제목|코드|그림|표)\s*(참조|참고)",
    ]

    # Korean-specific patterns for technical books
    KOREAN_SPECIFIC_PATTERNS = [
        r"^\s*\[.*?\]\s*$",  # [주석], [Note], etc.
        r"^(주|참고|(?i:note|tip|warning|caution))\s*[:]\s*.{0,20}$",  # Short annotations
        r"^\s*(다음|위|아래)\s*(과|와)?\s*(같이|같은|처럼)\s*$",  # "다음과 같이" alone
        r"^\s*\d+\.\s*$",  # List numbers like "1."
    ]

    # Reference action verbs (must appear with target object to be filtered)
    REFERENCE_VERBS_EN = ["see", "refer", "reference"]
    REFERENCE_VERBS_KO = ["참조", "참고", "보기", "확인"]
    
    # Reference target objects (filtered only when paired with action verb)
    REFERENCE_TARGETS_EN = ["figure", "table", "section", "chapter", "appendix"]
    REFERENCE_TARGETS_KO = ["그림", "표", "도표", "장", "절", "항"]
    def __init__(self) -> None:
        # Combine all pattern categories into a single regex
        all_patterns = (
            self.COPYRIGHT_PATTERNS +
            self.PAGE_NUMBER_PATTERNS +
            self.REFERENCE_PATTERNS +
            self.KOREAN_SPECIFIC_PATTERNS
        )
        self._boilerplate_re = re.compile(
            "|".join(all_patterns),
            re.MULTILINE  # (?i) is applied per-pattern in the pattern strings
        )

    def is_eligible(self, fragment: Fragment) -> bool:
        """
        Check if fragment meets all requirements for embedding.

        Args:
            fragment: Fragment to validate

        Returns:
            True if fragment should be embedded, False otherwise
        """
        # FRAG-LEN-001: Minimum length check
        if len(fragment.content) < self.MIN_LENGTH:
            return False

        # EMBED-BAN-003: Reject boilerplate
        if self._is_boilerplate(fragment.content):
            return False

        # EMBED-BAN-006: Reject pure reference text
        if self._is_pure_reference(fragment.content):
            return False

        return True

    def _is_boilerplate(self, content: str) -> bool:
        """Check if content is boilerplate text.

        Detects copyright notices, page numbers, and other non-content text
        in both Korean and English.
        """
        # Check against known patterns
        if self._boilerplate_re.search(content):
            return True

        # Check for repetitive patterns
        lines = content.strip().split("\n")
        if len(lines) > 0:
            # If all lines are identical, likely boilerplate
            unique_lines = set(line.strip() for line in lines if line.strip())
            if len(unique_lines) == 1 and len(lines) > 2:
                return True

        return False

    def _is_pure_reference(self, content: str) -> bool:
        """Check if content is just a reference to something else.

        Must have BOTH action verb AND target object to be filtered.
        This prevents filtering standalone terms like "肄붾뱶 1-1" or "洹몃┝ 2".
        """
        content_stripped = content.strip()

        # Only check very short text (<15 chars) to prevent false positives
        # Example: "洹몃┝ 3 李몄“" (7 chars) is a pure reference -> filter
        # Example: "肄붾뱶 1-1" (6 chars) is a valid heading -> keep
        # Example: "See Figure 3" (12 chars) is a pure reference -> filter
        if len(content_stripped) < 15:
            content_lower = content_stripped.lower()

            # Check English: must have both verb AND target
            has_en_verb = any(v in content_lower for v in self.REFERENCE_VERBS_EN)
            has_en_target = any(t in content_lower for t in self.REFERENCE_TARGETS_EN)
            if has_en_verb and has_en_target:
                return True

            # Check Korean: must have both verb AND target
            has_ko_verb = any(v in content_stripped for v in self.REFERENCE_VERBS_KO)
            has_ko_target = any(t in content_stripped for t in self.REFERENCE_TARGETS_KO)
            if has_ko_verb and has_ko_target:
                return True

        return False

    def get_ineligibility_reason(self, fragment: Fragment) -> Optional[str]:
        """
        Get human-readable reason why fragment is not eligible.

        Args:
            fragment: Fragment to check

        Returns:
            Reason string if ineligible, None if eligible
        """
        if len(fragment.content) < self.MIN_LENGTH:
            return f"FRAG-LEN-001: Content too short ({len(fragment.content)} < {self.MIN_LENGTH} chars)"

        if self._is_boilerplate(fragment.content):
            return "EMBED-BAN-003: Detected as boilerplate text"

        if self._is_pure_reference(fragment.content):
            return "EMBED-BAN-006: Pure reference text"

        return None


__all__ = ["EmbeddingValidator"]
