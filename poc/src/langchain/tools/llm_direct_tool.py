"""
LangChain tool for direct LLM queries.
"""

from typing import Dict, List, Any, Optional
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
import logging
from datetime import datetime

from ...models.question import QuestionType

logger = logging.getLogger(__name__)


class LLMDirectInput(BaseModel):
    """Input schema for direct LLM tool."""
    query: str = Field(description="Query to send directly to LLM")
    question_type: Optional[str] = Field(default=None, description="Type of question for prompt optimization")
    creativity_level: float = Field(default=0.7, description="Creativity level (0.0 to 1.0)")


class LLMDirectTool(BaseTool):
    """LangChain tool for direct LLM queries."""
    
    name: str = "llm_direct"
    description: str = """
    Get direct answers from a large language model (LLM).
    Use this tool when you need:
    - Creative or opinion-based responses
    - General knowledge questions
    - Recommendations and advice
    - Analysis and explanations that don't require specific documents
    - Hypothetical scenarios or brainstorming
    
    Input should be a clear question or request for the LLM to respond to.
    """
    args_schema: type[BaseModel] = LLMDirectInput
    llm: ChatOpenAI
    prompts: Dict[str, Any]
    default_prompt: Any
    
    def __init__(self, openai_api_key: str, **kwargs):
        llm = ChatOpenAI(
            api_key=openai_api_key,
            model="gpt-4o-mini",
            temperature=0.7
        )
        prompts, default_prompt = self._create_prompts()
        super().__init__(
            llm=llm,
            prompts=prompts,
            default_prompt=default_prompt,
            **kwargs
        )
        
    def _create_prompts(self):
        """Create different prompt templates for different question types."""
        
        prompts = {
            "factual": ChatPromptTemplate.from_messages([
                ("system", """당신은 정확하고 신뢰할 수 있는 정보를 제공하는 AI 어시스턴트입니다.
                사실에 기반한 정확한 답변을 제공하고, 불확실한 정보는 명시해주세요.
                답변은 구조적이고 이해하기 쉽게 작성해주세요."""),
                ("human", "{query}")
            ]),
            
            "general": ChatPromptTemplate.from_messages([
                ("system", """당신은 도움이 되고 친근한 AI 어시스턴트입니다.
                일반적인 질문에 대해 실용적이고 유용한 답변을 제공해주세요.
                추천이나 조언을 요청받으면 다양한 관점을 제시해주세요."""),
                ("human", "{query}")
            ]),
            
            "creative": ChatPromptTemplate.from_messages([
                ("system", """당신은 창의적이고 혁신적인 아이디어를 제공하는 AI 어시스턴트입니다.
                창의적 사고와 다양한 관점을 활용하여 독창적인 답변을 제공해주세요.
                브레인스토밍이나 아이디어 제안 시 여러 옵션을 제시해주세요."""),
                ("human", "{query}")
            ]),
            
            "complex": ChatPromptTemplate.from_messages([
                ("system", """당신은 복잡한 주제를 명확하게 설명하는 전문 AI 어시스턴트입니다.
                복잡한 질문을 단계별로 분석하고, 포괄적이면서도 이해하기 쉬운 답변을 제공해주세요.
                필요시 여러 관점에서 접근하여 균형잡힌 답변을 제시해주세요."""),
                ("human", "{query}")
            ]),
            
            "current_events": ChatPromptTemplate.from_messages([
                ("system", """당신은 최신 정보와 트렌드에 대해 답변하는 AI 어시스턴트입니다.
                하지만 실시간 정보에는 제한이 있음을 명시하고, 일반적인 패턴이나 
                원리를 바탕으로 도움이 되는 답변을 제공해주세요."""),
                ("human", "{query}")
            ])
        }
        
        # Default prompt
        default_prompt = ChatPromptTemplate.from_messages([
            ("system", """당신은 도움이 되고 지식이 풍부한 AI 어시스턴트입니다.
            질문에 대해 정확하고 유용한 답변을 제공해주세요.
            불확실한 정보는 명시하고, 가능한 한 구체적이고 실용적인 답변을 제공해주세요."""),
            ("human", "{query}")
        ])
        
        return prompts, default_prompt
        
    def _run(self, query: str, question_type: Optional[str] = None, creativity_level: float = 0.7) -> Dict[str, Any]:
        """Execute direct LLM query."""
        try:
            logger.info(f"Executing LLM direct query: {query[:50]}...")
            
            # Adjust LLM temperature based on creativity level
            self.llm.temperature = creativity_level
            
            # Select appropriate prompt
            if question_type and question_type.lower() in self.prompts:
                prompt = self.prompts[question_type.lower()]
            else:
                prompt = self.default_prompt
            
            # Create chain and execute
            chain = prompt | self.llm
            
            start_time = datetime.now()
            response = chain.invoke({"query": query})
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            logger.info(f"LLM direct query completed in {processing_time:.0f}ms")
            
            return {
                "success": True,
                "content": response.content,
                "model": self.llm.model_name,
                "processing_time": processing_time,
                "metadata": {
                    "question_type": question_type or "general",
                    "creativity_level": creativity_level,
                    "temperature": self.llm.temperature,
                    "prompt_type": question_type or "default",
                    "response_timestamp": datetime.now().isoformat()
                },
                "token_usage": {
                    "prompt_tokens": getattr(response.response_metadata, 'token_usage', {}).get('prompt_tokens', 0),
                    "completion_tokens": getattr(response.response_metadata, 'token_usage', {}).get('completion_tokens', 0),
                    "total_tokens": getattr(response.response_metadata, 'token_usage', {}).get('total_tokens', 0)
                } if hasattr(response, 'response_metadata') else {}
            }
            
        except Exception as e:
            logger.error(f"LLM direct query failed: {str(e)}")
            return {
                "success": False,
                "message": f"LLM direct query error: {str(e)}",
                "content": "",
                "processing_time": 0
            }
    
    async def _arun(self, query: str, question_type: Optional[str] = None, creativity_level: float = 0.7) -> Dict[str, Any]:
        """Async execution (fallback to sync for now)."""
        return self._run(query, question_type, creativity_level)