"""PDF text extraction with pdfminer.six (legacy parser).

NOTE: This is a legacy parser. For OCR support, use PyMuPdfParser instead.
OCR is handled by Gemini Vision API, not ocrmypdf.
"""

import warnings
from typing import List, Optional

from pdfminer.high_level import extract_text as pdfminer_extract_text

from src.rag.shared.text_utils import TextNormalizerUtil

from ..dto import RawSegment
from .base import BaseSegmentParser
from .ocr import OcrParser


class PdfExtractor:
    """Extract text from PDF using pdfminer.six."""

    def extract(self, pdf_path: str) -> Optional[str]:
        """
        Extract text from PDF file using pdfminer.six.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Extracted text or None if extraction fails
        """
        try:
            text = pdfminer_extract_text(pdf_path)
            if text and text.strip():
                return text
        except Exception:
            pass
        return None

    @staticmethod
    def is_low_text_density(text: str, min_len: int = 500, min_ratio: float = 0.2) -> bool:
        """
        Check if extracted text has low density (likely needs OCR).

        Args:
            text: Extracted text
            min_len: Minimum text length to consider valid
            min_ratio: Minimum ratio of alphanumeric characters

        Returns:
            True if text density is low
        """
        if not text or len(text.strip()) < min_len:
            return True
        letters = sum(ch.isalnum() for ch in text)
        ratio = letters / max(1, len(text))
        return ratio < min_ratio


class PdfParser(BaseSegmentParser):
    """Legacy PDF parser using pdfminer.six.

    NOTE: This parser does NOT support OCR. For scanned PDFs or images,
    use PyMuPdfParser with Gemini Vision OCR instead.

    Set PDF_PARSER=pymupdf in environment to use the recommended parser.
    """

    def __init__(
        self,
        preprocessor: TextNormalizerUtil,
        *,
        enable_auto_ocr: bool = False,
        force_ocr: bool = False,
        ocr_languages: str = "kor+eng",
    ) -> None:
        super().__init__(preprocessor)
        self.extractor = PdfExtractor()
        self.text_parser = OcrParser(preprocessor)

        # Warn if OCR is requested but not available in legacy parser
        if enable_auto_ocr or force_ocr:
            warnings.warn(
                "PdfParser (pdfminer) does not support OCR. "
                "Use PDF_PARSER=pymupdf with ENABLE_IMAGE_OCR=true for OCR support.",
                UserWarning,
            )

    def parse(self, path: str) -> List[RawSegment]:
        """
        Parse a PDF file into segments.

        Args:
            path: Path to PDF file

        Returns:
            List of RawSegment objects
        """
        text = self.extractor.extract(path)
        if not text:
            return []
        return self.text_parser.parse_text(text)


__all__ = ["PdfExtractor", "PdfParser"]
