"""Text chunking utilities for ingestion layer.

Provides configurable text splitting with overlap for OCR content
to create appropriately sized fragments for embedding.
"""

from typing import List

from langchain_text_splitters import RecursiveCharacterTextSplitter


class TextChunker:
    """Text chunking with overlap for OCR content.
    
    Uses RecursiveCharacterTextSplitter to split text into chunks
    with configurable size and overlap for context preservation.
    
    Example:
        >>> chunker = TextChunker(chunk_size=1200, chunk_overlap=200)
        >>> chunks = chunker.chunk("long text content...")
        >>> len(chunks)  # Multiple chunks with overlap
    """
    
    def __init__(
        self,
        chunk_size: int = 600,
        chunk_overlap: int = 100,
        separators: List[str] = None,
    ):
        """Initialize TextChunker.
        
        Args:
            chunk_size: Maximum size of each chunk in characters
            chunk_overlap: Overlap between consecutive chunks
            separators: List of separators to use for splitting (priority order)
        """
        if separators is None:
            separators = ["\n\n", "\n", " ", ""]
        
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=separators,
            length_function=len,
        )
    
    def chunk(self, text: str) -> List[str]:
        """Split text into chunks with overlap.
        
        Args:
            text: Text content to chunk
            
        Returns:
            List of text chunks
        """
        if not text or not text.strip():
            return []
        
        chunks = self.splitter.split_text(text)
        return [c for c in chunks if c.strip()]


__all__ = ["TextChunker"]
