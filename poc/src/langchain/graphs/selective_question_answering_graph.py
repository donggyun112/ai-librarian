"""
선택적 질문 답변 그래프 - 외부 라우팅 결정을 지원하는 LangGraph 워크플로우
"""

from typing import Dict, List, Any, Optional, Literal
from datetime import datetime
import logging
import uuid

from langgraph.graph import StateGraph, END

from ..schemas.question_answer_schema import QuestionState, AnswerState
from ..tools.vector_search_tool import VectorSearchTool
from ..tools.web_search_tool import WebSearchTool
from ..tools.llm_direct_tool import LLMDirectTool
from ...models.question import Question, QuestionType
from ...models.answer import Answer, AnswerConfidence
from ...services.vector_store import VectorStore
from ...services.embedding_service import EmbeddingService
from ...services.routing_service import RoutingService, RoutingDecision, DataSource, RoutingStrategy

logger = logging.getLogger(__name__)


class SelectiveQuestionAnsweringGraph:
    """
    선택적 질문 답변을 위한 LangGraph 워크플로우.
    
    외부에서 라우팅 결정을 받아 지정된 데이터소스만 실행하거나,
    자동 라우팅을 통해 최적의 소스를 선택할 수 있습니다.
    """
    
    def __init__(self, 
                 vector_store: VectorStore,
                 embedding_service: EmbeddingService,
                 openai_api_key: str,
                 routing_service: Optional[RoutingService] = None):
        """
        선택적 질문 답변 그래프 초기화.
        
        Args:
            vector_store: Vector store for document search
            embedding_service: Embedding service for query processing
            openai_api_key: OpenAI API key
            routing_service: 라우팅 서비스 (선택사항)
        """
        self.vector_store = vector_store
        self.embedding_service = embedding_service
        self.openai_api_key = openai_api_key
        self.routing_service = routing_service or RoutingService()
        
        # Initialize tools
        self.tools = {
            'vector_search': VectorSearchTool(vector_store=vector_store, embedding_service=embedding_service),
            'web_search': WebSearchTool(),
            'llm_direct': LLMDirectTool(openai_api_key=openai_api_key)
        }
        
        # Build the graph
        self.graph = self._build_graph()
        
    def _build_graph(self) -> StateGraph:
        """선택적 실행을 위한 LangGraph 워크플로우 구성."""
        
        # Create state graph
        workflow = StateGraph(QuestionState)
        
        # Add nodes
        workflow.add_node("analyze_question", self._analyze_question_node)
        workflow.add_node("apply_routing_decision", self._apply_routing_decision_node)
        workflow.add_node("execute_vector_search", self._execute_vector_search_node)
        workflow.add_node("execute_web_search", self._execute_web_search_node)
        workflow.add_node("execute_llm_direct", self._execute_llm_direct_node)
        workflow.add_node("integrate_results", self._integrate_results_node)
        workflow.add_node("finalize_answer", self._finalize_answer_node)
        
        # Set entry point
        workflow.set_entry_point("analyze_question")
        
        # Add edges
        workflow.add_edge("analyze_question", "apply_routing_decision")
        
        # Conditional routing from apply_routing_decision
        workflow.add_conditional_edges(
            "apply_routing_decision",
            self._should_execute_sources,
            {
                "vector_only": "execute_vector_search",
                "web_only": "execute_web_search", 
                "llm_only": "execute_llm_direct",
                "multiple_sources": "execute_vector_search"  # Start with vector for multiple sources
            }
        )
        
        # Vector search paths
        workflow.add_conditional_edges(
            "execute_vector_search",
            self._next_after_vector_search,
            {
                "web_search": "execute_web_search",
                "llm_direct": "execute_llm_direct",
                "integrate": "integrate_results",
                "finalize": "finalize_answer"
            }
        )
        
        # Web search paths
        workflow.add_conditional_edges(
            "execute_web_search", 
            self._next_after_web_search,
            {
                "llm_direct": "execute_llm_direct",
                "integrate": "integrate_results",
                "finalize": "finalize_answer"
            }
        )
        
        # LLM direct paths
        workflow.add_conditional_edges(
            "execute_llm_direct",
            self._next_after_llm_direct,
            {
                "integrate": "integrate_results",
                "finalize": "finalize_answer"
            }
        )
        
        # Final paths
        workflow.add_edge("integrate_results", "finalize_answer")
        workflow.add_edge("finalize_answer", END)
        
        return workflow.compile()
    
    def _analyze_question_node(self, state: QuestionState) -> QuestionState:
        """질문 분석 노드."""
        logger.info(f"Analyzing question: {state['question_content'][:50]}...")
        
        # Create Question object for analysis
        question = Question(
            content=state['question_content'],
            id=state['question_id']
        )
        
        # 기본 분석 (기존 로직 유지)
        keywords = self._extract_keywords(question.content)
        question_type = self._classify_question_type(question.content)
        complexity_score = self._calculate_complexity(question.content)
        context_needed = self._requires_context(question.content)
        
        # Update state
        state.update({
            'keywords': keywords,
            'question_type': question_type,
            'complexity_score': complexity_score,
            'context_needed': context_needed,
            'question_object': question
        })
        
        logger.info(f"Question analysis complete - Type: {question_type}, Complexity: {complexity_score:.2f}")
        return state
    
    def _apply_routing_decision_node(self, state: QuestionState) -> QuestionState:
        """라우팅 결정 적용 노드."""
        logger.info("Applying routing decision...")
        
        question = state['question_object']
        
        # 외부에서 라우팅 결정이 제공된 경우
        if state.get('external_routing_decision'):
            routing_decision = state['external_routing_decision']
            logger.info(f"Using external routing decision: {routing_decision.primary_source.value}")
        else:
            # 자동 라우팅 결정
            preferred_sources = state.get('preferred_sources')
            strategy = state.get('preferred_strategy')
            
            # DataSource enum으로 변환
            if preferred_sources:
                preferred_sources = [DataSource(source) for source in preferred_sources]
            if strategy:
                strategy = RoutingStrategy(strategy)
            
            routing_decision = self.routing_service.decide_routing(
                question=question,
                preferred_sources=preferred_sources,
                strategy=strategy
            )
            logger.info(f"Auto routing decision: {routing_decision.primary_source.value}")
        
        # 상태 업데이트
        state.update({
            'routing_decision': routing_decision,
            'selected_sources': [source.value for source in routing_decision.sources],
            'routing_strategy': routing_decision.strategy.value,
            'source_confidences': routing_decision.confidence_scores,
            'routing_reasoning': routing_decision.reasoning,
            'routing_timestamp': datetime.now()
        })
        
        logger.info(f"Routing applied: {len(routing_decision.sources)} sources selected")
        return state
    
    def _execute_vector_search_node(self, state: QuestionState) -> QuestionState:
        """Vector search 실행 노드."""
        if DataSource.VECTOR_DB.value not in state['selected_sources']:
            logger.info("Vector search not selected, skipping")
            return state
            
        logger.info("Executing vector search...")
        start_time = datetime.now()
        
        try:
            result = self.tools['vector_search']._run(
                query=state['question_content'],
                top_k=5,
                similarity_threshold=0.7
            )
            
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            state['agent_execution_times']['vector_search'] = processing_time
            state['vector_search_result'] = result
            
            logger.info(f"Vector search completed in {processing_time:.0f}ms")
            
        except Exception as e:
            logger.error(f"Vector search failed: {str(e)}")
            state['vector_search_result'] = {
                'success': False,
                'message': f"Vector search error: {str(e)}"
            }
        
        return state
    
    def _execute_web_search_node(self, state: QuestionState) -> QuestionState:
        """Web search 실행 노드."""
        if DataSource.WEB_SEARCH.value not in state['selected_sources']:
            logger.info("Web search not selected, skipping")
            return state
            
        logger.info("Executing web search...")
        start_time = datetime.now()
        
        try:
            # Focus on recent info for current events
            focus_recent = state['question_type'] == QuestionType.CURRENT_EVENTS
            
            result = self.tools['web_search']._run(
                query=state['question_content'],
                max_results=5,
                focus_recent=focus_recent
            )
            
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            state['agent_execution_times']['web_search'] = processing_time
            state['web_search_result'] = result
            
            logger.info(f"Web search completed in {processing_time:.0f}ms")
            
        except Exception as e:
            logger.error(f"Web search failed: {str(e)}")
            state['web_search_result'] = {
                'success': False,
                'message': f"Web search error: {str(e)}"
            }
        
        return state
    
    def _execute_llm_direct_node(self, state: QuestionState) -> QuestionState:
        """LLM direct 실행 노드."""
        if DataSource.LLM_DIRECT.value not in state['selected_sources']:
            logger.info("LLM direct not selected, skipping")
            return state
            
        logger.info("Executing LLM direct query...")
        start_time = datetime.now()
        
        try:
            # Determine creativity level based on question type
            creativity_level = 0.3 if state['question_type'] == QuestionType.FACTUAL else 0.7
            
            result = self.tools['llm_direct']._run(
                query=state['question_content'],
                question_type=state['question_type'].value if state['question_type'] else None,
                creativity_level=creativity_level
            )
            
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            state['agent_execution_times']['llm_direct'] = processing_time
            state['llm_direct_result'] = result
            
            logger.info(f"LLM direct query completed in {processing_time:.0f}ms")
            
        except Exception as e:
            logger.error(f"LLM direct query failed: {str(e)}")
            state['llm_direct_result'] = {
                'success': False,
                'message': f"LLM direct query error: {str(e)}"
            }
        
        return state
    
    def _integrate_results_node(self, state: QuestionState) -> QuestionState:
        """결과 통합 노드."""
        routing_strategy = state.get('routing_strategy')
        
        if routing_strategy != RoutingStrategy.HYBRID.value:
            logger.info("Single source strategy, skipping integration")
            return state
            
        logger.info("Integrating multiple source results...")
        
        # Collect successful results
        successful_results = []
        
        if state.get('vector_search_result', {}).get('success'):
            successful_results.append(('vector_db', state['vector_search_result']))
            
        if state.get('web_search_result', {}).get('success'):
            successful_results.append(('web_search', state['web_search_result']))
            
        if state.get('llm_direct_result', {}).get('success'):
            successful_results.append(('llm_direct', state['llm_direct_result']))
        
        if len(successful_results) <= 1:
            logger.info("Only one successful result, no integration needed")
            return state
        
        # Apply integration strategy
        integrated_answer = self._integrate_multiple_results(successful_results, state)
        state['final_answer'] = integrated_answer
        
        logger.info(f"Results integrated from {len(successful_results)} sources")
        return state
    
    def _finalize_answer_node(self, state: QuestionState) -> QuestionState:
        """답변 최종화 노드."""
        logger.info("Finalizing answer...")
        
        if state.get('final_answer'):
            # Already integrated
            return state
        
        # Select best single-source answer
        best_result = self._select_best_single_answer(state)
        
        if best_result:
            state['final_answer'] = best_result
        else:
            # Fallback answer
            state['final_answer'] = {
                'success': False,
                'content': "죄송합니다. 선택된 데이터소스에서 답변을 생성할 수 없습니다.",
                'source_type': 'unknown',
                'confidence': {'relevance': 0.0, 'completeness': 0.0, 'accuracy': 0.0, 'reliability': 0.0}
            }
        
        # Calculate total processing time
        total_time = sum(state.get('agent_execution_times', {}).values())
        state['total_processing_time'] = total_time
        
        # Store individual source results for UI display
        state['individual_source_results'] = {
            'vector_search': state.get('vector_search_result'),
            'web_search': state.get('web_search_result'),
            'llm_direct': state.get('llm_direct_result')
        }
        
        logger.info(f"Answer finalized with total processing time: {total_time:.0f}ms")
        return state
    
    # Conditional edge functions
    def _should_execute_sources(self, state: QuestionState) -> str:
        """선택된 소스에 따른 실행 경로 결정."""
        selected_sources = state.get('selected_sources', [])
        
        if len(selected_sources) == 1:
            source = selected_sources[0]
            if source == DataSource.VECTOR_DB.value:
                return "vector_only"
            elif source == DataSource.WEB_SEARCH.value:
                return "web_only"
            elif source == DataSource.LLM_DIRECT.value:
                return "llm_only"
        
        return "multiple_sources"
    
    def _next_after_vector_search(self, state: QuestionState) -> str:
        """Vector search 후 다음 단계 결정."""
        selected_sources = state.get('selected_sources', [])
        
        if DataSource.WEB_SEARCH.value in selected_sources and not state.get('web_search_result'):
            return "web_search"
        elif DataSource.LLM_DIRECT.value in selected_sources and not state.get('llm_direct_result'):
            return "llm_direct"
        elif len(selected_sources) > 1:
            return "integrate"
        else:
            return "finalize"
    
    def _next_after_web_search(self, state: QuestionState) -> str:
        """Web search 후 다음 단계 결정."""
        selected_sources = state.get('selected_sources', [])
        
        if DataSource.LLM_DIRECT.value in selected_sources and not state.get('llm_direct_result'):
            return "llm_direct"
        elif len(selected_sources) > 1:
            return "integrate"
        else:
            return "finalize"
    
    def _next_after_llm_direct(self, state: QuestionState) -> str:
        """LLM direct 후 다음 단계 결정."""
        selected_sources = state.get('selected_sources', [])
        
        if len(selected_sources) > 1:
            return "integrate"
        else:
            return "finalize"
    
    # Helper methods (기존 로직 재사용)
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text."""
        import re
        words = re.findall(r'\b[가-힣a-zA-Z]+\b', text.lower())
        return [word for word in words if len(word) > 2][:10]
    
    def _classify_question_type(self, text: str) -> QuestionType:
        """Classify question type."""
        text_lower = text.lower()
        
        if any(keyword in text_lower for keyword in ['최근', '최신', '2024', '현재', 'latest', 'recent']):
            return QuestionType.CURRENT_EVENTS
        
        if any(keyword in text_lower for keyword in ['정의', '의미', '설명', '차이', 'what is', 'explain']):
            return QuestionType.FACTUAL
        
        if len(text.split()) > 20 or '그리고' in text_lower or 'and' in text_lower:
            return QuestionType.COMPLEX
        
        return QuestionType.GENERAL
    
    def _calculate_complexity(self, text: str) -> float:
        """Calculate question complexity score."""
        factors = {
            'length': min(len(text.split()) / 20, 1.0) * 0.4,
            'questions': min(text.count('?'), 3) / 3 * 0.3,
            'conjunctions': len([w for w in ['그리고', '하지만', 'and', 'but'] if w in text.lower()]) / 5 * 0.3
        }
        return sum(factors.values())
    
    def _requires_context(self, text: str) -> bool:
        """Check if question requires context."""
        context_indicators = ['설명', '어떻게', '차이', '예시', 'explain', 'how', 'difference', 'example']
        return any(indicator in text.lower() for indicator in context_indicators)
    
    def _integrate_multiple_results(self, results: List, state: QuestionState) -> Dict[str, Any]:
        """다중 소스 결과 통합."""
        # 간단한 통합 전략: 가장 높은 신뢰도의 결과 선택
        source_confidences = state.get('source_confidences', {})
        
        best_source, best_result = max(results, key=lambda x: source_confidences.get(x[0], 0))
        
        return {
            'success': True,
            'content': best_result.get('content', ''),
            'source_type': 'hybrid',
            'primary_source': best_source,
            'confidence': {
                'relevance': 0.8,
                'completeness': 0.7,
                'accuracy': 0.8,
                'reliability': 0.7
            },
            'metadata': {
                'integration_strategy': 'best_confidence',
                'sources_used': [source for source, _ in results],
                'total_sources': len(results)
            }
        }
    
    def _select_best_single_answer(self, state: QuestionState) -> Optional[Dict[str, Any]]:
        """단일 소스에서 최적 답변 선택."""
        results = []
        
        for source in ['vector_search', 'web_search', 'llm_direct']:
            result = state.get(f'{source}_result')
            if result and result.get('success'):
                confidence = state['source_confidences'].get(source.replace('_search', '_db').replace('_direct', ''), 0)
                results.append((source, result, confidence))
        
        if not results:
            return None
        
        # Select result with highest confidence
        best_source, best_result, _ = max(results, key=lambda x: x[2])
        
        return {
            'success': True,
            'content': best_result.get('content', ''),
            'source_type': best_source.replace('_search', '_db').replace('_direct', ''),
            'confidence': {
                'relevance': 0.8,
                'completeness': 0.7,
                'accuracy': 0.8,
                'reliability': 0.7
            },
            'metadata': {
                'source': best_source,
                'original_result': best_result
            }
        }
    
    def run_with_routing(self, 
                        question_content: str,
                        routing_decision: Optional[RoutingDecision] = None,
                        preferred_sources: Optional[List[str]] = None,
                        preferred_strategy: Optional[str] = None) -> Dict[str, Any]:
        """
        라우팅 결정과 함께 질문 답변 실행.
        
        Args:
            question_content: 질문 내용
            routing_decision: 외부 라우팅 결정 (선택사항)
            preferred_sources: 선호하는 데이터소스 목록 (선택사항)
            preferred_strategy: 선호하는 전략 (선택사항)
            
        Returns:
            답변 결과
        """
        # Initialize state
        initial_state = QuestionState(
            question_id=str(uuid.uuid4()),
            question_content=question_content,
            question_type=None,
            keywords=[],
            complexity_score=0.0,
            context_needed=False,
            routing_strategy=None,
            source_confidences={},
            recommended_sources=[],
            requires_hybrid=False,
            vector_search_result=None,
            web_search_result=None,
            llm_direct_result=None,
            final_answer=None,
            processing_start_time=datetime.now(),
            routing_timestamp=None,
            agent_execution_times={},
            total_processing_time=None,
            # 추가 필드
            external_routing_decision=routing_decision,
            preferred_sources=preferred_sources,
            preferred_strategy=preferred_strategy,
            selected_sources=[],
            routing_reasoning=""
        )
        
        try:
            # Execute graph
            logger.info(f"Starting selective question answering for: {question_content[:50]}...")
            final_state = self.graph.invoke(initial_state)
            
            logger.info("Selective question answering completed successfully")
            return {
                'success': True,
                'answer': final_state.get('final_answer'),
                'individual_source_results': final_state.get('individual_source_results', {}),
                'routing_info': {
                    'selected_sources': final_state.get('selected_sources', []),
                    'routing_strategy': final_state.get('routing_strategy'),
                    'source_confidences': final_state.get('source_confidences', {}),
                    'routing_reasoning': final_state.get('routing_reasoning', ''),
                    'routing_timestamp': final_state.get('routing_timestamp')
                },
                'metadata': {
                    'question_id': final_state['question_id'],
                    'question_type': final_state.get('question_type'),
                    'total_processing_time': final_state.get('total_processing_time'),
                    'agent_execution_times': final_state.get('agent_execution_times')
                }
            }
            
        except Exception as e:
            logger.error(f"Selective question answering failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'answer': {
                    'content': "죄송합니다. 시스템 오류로 인해 답변을 생성할 수 없습니다.",
                    'source_type': 'error'
                }
            }
