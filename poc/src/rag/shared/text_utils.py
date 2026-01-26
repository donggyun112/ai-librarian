import re
from typing import List, Optional


class TextNormalizerUtil:
    """Utility for OCR/markdown text normalization and code detection."""

    # Ligature and smart quote normalization
    NORMALIZE_MAP = {
        "\uFB03": "ffi",
        "\uFB01": "fi",
        "\uFB02": "fl",
        "\u2019": "'",
        "\u2018": "'",
        "\u201C": '"',
        "\u201D": '"',
        "\u2013": "-",
        "\u2014": "-",
    }

    # OCR artifact cleanup: fullwidth -> halfwidth conversion
    # Using unicode escapes to prevent encoding issues during file write
    OCR_ARTIFACT_MAP = {
        "\u3000": " ",  # fullwidth space
        "\uff08": "(",  # fullwidth parentheses
        "\uff09": ")",
        "\uff0c": ",",  # fullwidth comma
        "\uff1a": ":",  # fullwidth colon
        "\uff1b": ";",  # fullwidth semicolon
        "\uff5b": "{",  # fullwidth braces
        "\uff5d": "}",
        "\uff3b": "[",  # fullwidth brackets
        "\uff3d": "]",
        "\uff0e": ".",  # fullwidth period
        "\uff01": "!",  # fullwidth exclamation
        "\uff1f": "?",  # fullwidth question
        "\uff1d": "=",  # fullwidth equals
        "\uff0b": "+",  # fullwidth plus
        "\uff0d": "-",  # fullwidth minus
        "\uff0a": "*",  # fullwidth asterisk
        "\uff0f": "/",  # fullwidth slash
        "\uff1c": "<",  # fullwidth angle brackets
        "\uff1e": ">",
    }

    # OCR error correction patterns (regex pattern -> replacement)
    # Only GENERAL rules that apply universally to code OCR
    OCR_FIX_PATTERNS = [
        # Fix import path comma->dot (common OCR confusion: . vs ,)
        (r"(from\s+[\w_]+),([\w_]+)", r"\1.\2"),  # from pkg,module -> from pkg.module
        (r"(import\s+[\w_]+),([\w_]+)", r"\1.\2"),  # import pkg,module -> import pkg.module
        
        # Normalize spacing around = in assignments (code readability)
        (r"(\w+)\s+=\s+'", r"\1='"),  # var = 'x' -> var='x' (compact form)
        
        # Remove standalone page numbers at end of line (very common in book OCR)
        (r"\s+\d{1,3}\s*$", ""),  # trailing page numbers
    ]

    CODE_HINT = re.compile(
        r"```|코드\s+\d+-\d+|;\s*$|{\s*$|^\s*(def|class|import|from|async|await|try|except|with|for|while|return|lambda|console\.log|function|const|let|var|=>|export\s+default|import\s+.+\s+from)\b",
        re.M,
    )
    PY_SIGNS = re.compile(r"^\s*(def|class|from|import|try|except|with|async|await|lambda)\b|:\s*$", re.M)
    JS_SIGNS = re.compile(
        r"^\s*(function|const|let|var|class|export|import)\b|=>|;\s*$|{\s*$",
        re.M,
    )

    def normalize(self, text: str) -> str:
        # Apply ligature and smart quote normalization
        for src, target in self.NORMALIZE_MAP.items():
            text = text.replace(src, target)
        # Apply OCR artifact cleanup (fullwidth -> halfwidth)
        for src, target in self.OCR_ARTIFACT_MAP.items():
            text = text.replace(src, target)
        text = re.sub(r"\u00A0", " ", text)  # non-breaking space
        text = re.sub(r"[ \t]+\n", "\n", text)  # trailing whitespace per line
        text = re.sub(r"\n{3,}", "\n\n", text)  # collapse excessive newlines
        
        # Apply OCR error correction patterns (regex-based)
        for pattern, replacement in self.OCR_FIX_PATTERNS:
            text = re.sub(pattern, replacement, text, flags=re.MULTILINE)
        
        return text.strip()

    @staticmethod
    def split_paragraph(text: str) -> List[str]:
        parts = re.split(r"\n{2,}", text)
        return [p.strip() for p in parts if p.strip()]

    def is_code_block(self, paragraph: str) -> bool:
        if "```" in paragraph:
            return True
        if len(self.CODE_HINT.findall(paragraph)) >= 1:
            return True
        if self.PY_SIGNS.search(paragraph) or self.JS_SIGNS.search(paragraph):
            return True
        symbols = sum(paragraph.count(x) for x in (";", "{", "}", "=>", "()", "[]", "):"))
        if symbols >= 2:
            return True
        if len(re.findall(r"(?m)^\s{4,}\S", paragraph)) >= 2:
            return True
        return False

    def guess_code_lang(self, paragraph: str) -> Optional[str]:
        py = len(self.PY_SIGNS.findall(paragraph))
        js = len(self.JS_SIGNS.findall(paragraph))
        if py >= js and py > 0:
            return "python"
        if js >= py and js > 0:
            return "javascript"
        if re.search(r"^\s*def\s+", paragraph, re.M) or re.search(r"^\s*class\s+\w+:\s*$", paragraph, re.M):
            return "python"
        if "console.log" in paragraph or "=>" in paragraph or re.search(r";\s*$", paragraph, re.M):
            return "javascript"
        return None

    @staticmethod
    def split_code_safely(code: str, max_chars: int = 900, overlap_lines: int = 10) -> List[str]:
        blocks = re.split(r"(?m)^(?=def\s+\w+\(|class\s+\w+:)", code)
        chunks: List[str] = []
        for block in blocks:
            if len(block) <= max_chars:
                if block.strip():
                    chunks.append(block)
                continue
            lines = block.splitlines()
            start = 0
            while start < len(lines):
                current, acc, i = [], 0, start
                while i < len(lines) and acc + len(lines[i]) + 1 <= max_chars:
                    current.append(lines[i])
                    acc += len(lines[i]) + 1
                    i += 1
                if not current:
                    current = [lines[start][:max_chars]]
                    i = start + 1
                chunk = "\n".join(current).strip()
                if chunk:
                    chunks.append(chunk)
                next_start = max(0, i - overlap_lines)
                if next_start <= start:
                    next_start = i
                start = next_start
        return chunks


__all__ = ["TextNormalizerUtil"]
