"""
Data models for the AI Research Project.

This module contains Pydantic models for:
- Question: User input and query processing
- Answer: System responses and metadata
- Document: PDF document representation and chunks
"""

from .question import Question, QuestionType
from .answer import Answer, AnswerSource, AnswerConfidence
from .document import Document, DocumentChunk

__all__ = [
    "Question",
    "QuestionType", 
    "Answer",
    "AnswerSource",
    "AnswerConfidence",
    "Document",
    "DocumentChunk",
]