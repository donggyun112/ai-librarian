"""
AI Research Project - LangChain/LangGraph RAG System

This package contains the core components for the LangChain/LangGraph-based
Retrieval-Augmented Generation (RAG) system.
"""

from .models.question import Question, QuestionType
from .models.answer import Answer, AnswerSource, AnswerConfidence, AnswerConfidenceLevel
from .models.document import Document, DocumentChunk
from .services.vector_store import VectorStore
from .services.embedding_service import EmbeddingService
from .langchain.services.langchain_answer_service import LangChainAnswerService
from .langchain.graphs.question_answering_graph import QuestionAnsweringGraph
from .utils.config import get_config

__version__ = "2.0.0"
__author__ = "AI Research Team"

__all__ = [
    # Models
    'Question', 'QuestionType',
    'Answer', 'AnswerSource', 'AnswerConfidence', 'AnswerConfidenceLevel',
    'Document', 'DocumentChunk',
    
    # Services
    'VectorStore',
    'EmbeddingService',
    
    # LangChain/LangGraph
    'LangChainAnswerService',
    'QuestionAnsweringGraph',
    
    # Utils
    'get_config',
    
    # Version
    '__version__',
    '__author__'
]