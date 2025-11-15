"""
LangGraph state schemas for question answering workflow.
"""

from typing import Dict, List, Optional, Any, Literal
from typing_extensions import TypedDict
from datetime import datetime
from pydantic import BaseModel, Field

from ...models.question import QuestionType
from ...models.answer import AnswerConfidence


class QuestionState(TypedDict):
    """State schema for question processing in LangGraph."""
    
    # Question data
    question_id: str
    question_content: str
    question_type: Optional[QuestionType]
    keywords: List[str]
    complexity_score: float
    context_needed: bool
    
    # Routing information
    routing_strategy: Optional[str]
    source_confidences: Dict[str, float]
    recommended_sources: List[str]
    requires_hybrid: bool
    
    # Agent results
    vector_search_result: Optional[Dict[str, Any]]
    web_search_result: Optional[Dict[str, Any]]
    llm_direct_result: Optional[Dict[str, Any]]
    
    # Final answer
    final_answer: Optional[Dict[str, Any]]
    
    # Metadata
    processing_start_time: datetime
    routing_timestamp: Optional[datetime]
    agent_execution_times: Dict[str, float]
    total_processing_time: Optional[float]


class AnswerState(BaseModel):
    """Enhanced answer state for LangChain compatibility."""
    
    content: str = Field(description="Answer content")
    source_type: Literal["vector_db", "web_search", "llm_direct", "hybrid"] = Field(
        description="Type of answer source"
    )
    confidence: AnswerConfidence = Field(description="Answer confidence metrics")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    sources: List[Dict[str, Any]] = Field(default_factory=list, description="Source references")
    
    # LangChain specific fields
    agent_name: str = Field(description="Name of the agent that generated this answer")
    processing_time: float = Field(description="Processing time in milliseconds")
    token_usage: Optional[Dict[str, int]] = Field(default=None, description="Token usage statistics")
    
    class Config:
        arbitrary_types_allowed = True


class GraphMetadata(BaseModel):
    """Metadata for graph execution."""
    
    execution_id: str = Field(description="Unique execution identifier")
    start_time: datetime = Field(description="Execution start time")
    end_time: Optional[datetime] = Field(default=None, description="Execution end time")
    total_duration: Optional[float] = Field(default=None, description="Total execution time in seconds")
    
    # Node execution tracking
    nodes_executed: List[str] = Field(default_factory=list, description="List of executed nodes")
    node_execution_times: Dict[str, float] = Field(default_factory=dict, description="Node execution times")
    
    # Error handling
    errors: List[Dict[str, Any]] = Field(default_factory=list, description="Execution errors")
    warnings: List[str] = Field(default_factory=list, description="Execution warnings")
    
    # Performance metrics
    total_tokens_used: Optional[int] = Field(default=None, description="Total tokens used across all agents")
    estimated_cost: Optional[float] = Field(default=None, description="Estimated API cost in USD")