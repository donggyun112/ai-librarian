"""
LangGraph workflow for question answering system.
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

logger = logging.getLogger(__name__)


class QuestionAnsweringGraph:
    """
    LangGraph workflow for intelligent question answering.
    
    This graph orchestrates multiple agents and tools to provide
    the best possible answer based on question analysis and routing.
    """
    
    def __init__(self, 
                 vector_store: VectorStore,
                 embedding_service: EmbeddingService,
                 openai_api_key: str,
                 vector_db_threshold: float = 0.7,
                 web_search_threshold: float = 0.6,
                 llm_direct_threshold: float = 0.5):
        """
        Initialize the question answering graph.
        
        Args:
            vector_store: Vector store for document search
            embedding_service: Embedding service for query processing
            openai_api_key: OpenAI API key
            vector_db_threshold: Threshold for vector DB confidence
            web_search_threshold: Threshold for web search confidence
            llm_direct_threshold: Threshold for LLM direct confidence
        """
        self.vector_store = vector_store
        self.embedding_service = embedding_service
        self.openai_api_key = openai_api_key
        self.thresholds = {
            'vector_db': vector_db_threshold,
            'web_search': web_search_threshold,
            'llm_direct': llm_direct_threshold
        }
        
        # Initialize tools
        self.tools = {
            'vector_search': VectorSearchTool(vector_store=vector_store, embedding_service=embedding_service),
            'web_search': WebSearchTool(),
            'llm_direct': LLMDirectTool(openai_api_key=openai_api_key)
        }
        
        # Build the graph
        self.graph = self._build_graph()
        
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        
        # Create state graph
        workflow = StateGraph(QuestionState)
        
        # Add nodes
        workflow.add_node("analyze_question", self._analyze_question_node)
        workflow.add_node("route_question", self._route_question_node)
        workflow.add_node("execute_vector_search", self._execute_vector_search_node)
        workflow.add_node("execute_web_search", self._execute_web_search_node)
        workflow.add_node("execute_llm_direct", self._execute_llm_direct_node)
        workflow.add_node("integrate_results", self._integrate_results_node)
        workflow.add_node("finalize_answer", self._finalize_answer_node)
        
        # Set entry point
        workflow.set_entry_point("analyze_question")
        
        # Add edges
        workflow.add_edge("analyze_question", "route_question")
        
        # Conditional routing from route_question
        workflow.add_conditional_edges(
            "route_question",
            self._should_execute_agents,
            {
                "vector_only": "execute_vector_search",
                "web_only": "execute_web_search", 
                "llm_only": "execute_llm_direct",
                "hybrid": "execute_vector_search"  # Start with vector for hybrid
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
        """Analyze the input question."""
        logger.info(f"Analyzing question: {state['question_content'][:50]}...")
        
        # Create Question object for analysis
        question = Question(
            content=state['question_content'],
            id=state['question_id']
        )
        
        # Extract keywords (simplified)
        keywords = self._extract_keywords(question.content)
        
        # Classify question type
        question_type = self._classify_question_type(question.content)
        
        # Calculate complexity
        complexity_score = self._calculate_complexity(question.content)
        
        # Determine context need
        context_needed = self._requires_context(question.content)
        
        # Update state
        state.update({
            'keywords': keywords,
            'question_type': question_type,
            'complexity_score': complexity_score,
            'context_needed': context_needed
        })
        
        logger.info(f"Question analysis complete - Type: {question_type}, Complexity: {complexity_score:.2f}")
        return state
    
    def _route_question_node(self, state: QuestionState) -> QuestionState:
        """Determine routing strategy based on question analysis."""
        logger.info("Determining routing strategy...")
        
        # Calculate confidence scores
        vector_db_confidence = self._calculate_vector_db_confidence(state)
        web_search_confidence = self._calculate_web_search_confidence(state)
        llm_direct_confidence = self._calculate_llm_direct_confidence(state)
        
        # Determine routing strategy
        routing_strategy = self._determine_routing_strategy(
            vector_db_confidence, web_search_confidence, llm_direct_confidence
        )
        
        # Get recommended sources
        recommended_sources = self._get_recommended_sources(
            vector_db_confidence, web_search_confidence, llm_direct_confidence
        )
        
        # Check if hybrid approach is needed
        requires_hybrid = len(recommended_sources) > 1
        
        # Update state
        state.update({
            'routing_strategy': routing_strategy,
            'source_confidences': {
                'vector_db': vector_db_confidence,
                'web_search': web_search_confidence,
                'llm_direct': llm_direct_confidence
            },
            'recommended_sources': recommended_sources,
            'requires_hybrid': requires_hybrid,
            'routing_timestamp': datetime.now()
        })
        
        logger.info(f"Routing decision: {routing_strategy} with sources: {recommended_sources}")
        return state
    
    def _execute_vector_search_node(self, state: QuestionState) -> QuestionState:
        """Execute vector database search."""
        if 'vector_db' not in state['recommended_sources']:
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
        """Execute web search."""
        if 'web_search' not in state['recommended_sources']:
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
        """Execute direct LLM query."""
        if 'llm_direct' not in state['recommended_sources']:
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
        """Integrate results from multiple sources."""
        if not state['requires_hybrid']:
            return state
            
        logger.info("Integrating hybrid results...")
        
        # Collect successful results
        successful_results = []
        
        if state.get('vector_search_result', {}).get('success'):
            successful_results.append(('vector_db', state['vector_search_result']))
            
        if state.get('web_search_result', {}).get('success'):
            successful_results.append(('web_search', state['web_search_result']))
            
        if state.get('llm_direct_result', {}).get('success'):
            successful_results.append(('llm_direct', state['llm_direct_result']))
        
        if len(successful_results) <= 1:
            return state
        
        # Apply integration strategy
        integration_strategy = self._determine_integration_strategy(successful_results, state)
        integrated_answer = self._apply_integration_strategy(
            successful_results, integration_strategy, state
        )
        
        state['final_answer'] = integrated_answer
        
        logger.info(f"Results integrated using {integration_strategy} strategy")
        return state
    
    def _finalize_answer_node(self, state: QuestionState) -> QuestionState:
        """Finalize the answer selection."""
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
                'content': "죄송합니다. 질문에 대한 답변을 생성할 수 없습니다.",
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
    def _should_execute_agents(self, state: QuestionState) -> str:
        """Determine which agents to execute based on routing strategy."""
        strategy = state.get('routing_strategy', 'llm_only')
        
        if strategy == 'vector_db_only':
            return "vector_only"
        elif strategy == 'web_search_only':
            return "web_only"
        elif strategy == 'llm_direct_only':
            return "llm_only"
        else:
            return "hybrid"
    
    def _next_after_vector_search(self, state: QuestionState) -> str:
        """Determine next step after vector search."""
        sources = state.get('recommended_sources', [])
        
        if 'web_search' in sources and not state.get('web_search_result'):
            return "web_search"
        elif 'llm_direct' in sources and not state.get('llm_direct_result'):
            return "llm_direct"
        elif state.get('requires_hybrid'):
            return "integrate"
        else:
            return "finalize"
    
    def _next_after_web_search(self, state: QuestionState) -> str:
        """Determine next step after web search."""
        sources = state.get('recommended_sources', [])
        
        if 'llm_direct' in sources and not state.get('llm_direct_result'):
            return "llm_direct"
        elif state.get('requires_hybrid'):
            return "integrate"
        else:
            return "finalize"
    
    def _next_after_llm_direct(self, state: QuestionState) -> str:
        """Determine next step after LLM direct."""
        if state.get('requires_hybrid'):
            return "integrate"
        else:
            return "finalize"
    
    # Helper methods (simplified versions of original logic)
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text."""
        import re
        words = re.findall(r'\b[가-힣a-zA-Z]+\b', text.lower())
        return [word for word in words if len(word) > 2][:10]
    
    def _classify_question_type(self, text: str) -> QuestionType:
        """Classify question type."""
        text_lower = text.lower()
        
        # Check for current events
        if any(keyword in text_lower for keyword in ['최근', '최신', '2024', '현재', 'latest', 'recent']):
            return QuestionType.CURRENT_EVENTS
        
        # Check for factual
        if any(keyword in text_lower for keyword in ['정의', '의미', '설명', '차이', 'what is', 'explain']):
            return QuestionType.FACTUAL
        
        # Check for complex
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
    
    def _calculate_vector_db_confidence(self, state: QuestionState) -> float:
        """Calculate vector DB confidence."""
        base_confidence = {
            QuestionType.FACTUAL: 0.9,
            QuestionType.COMPLEX: 0.7,
            QuestionType.GENERAL: 0.4,
            QuestionType.CURRENT_EVENTS: 0.2
        }.get(state['question_type'], 0.3)
        
        # Boost for context requirement
        if state['context_needed']:
            base_confidence += 0.2
        
        return min(1.0, base_confidence)
    
    def _calculate_web_search_confidence(self, state: QuestionState) -> float:
        """Calculate web search confidence."""
        base_confidence = {
            QuestionType.CURRENT_EVENTS: 0.9,
            QuestionType.GENERAL: 0.3,
            QuestionType.COMPLEX: 0.2,
            QuestionType.FACTUAL: 0.1
        }.get(state['question_type'], 0.2)
        
        return base_confidence
    
    def _calculate_llm_direct_confidence(self, state: QuestionState) -> float:
        """Calculate LLM direct confidence."""
        base_confidence = {
            QuestionType.GENERAL: 0.8,
            QuestionType.COMPLEX: 0.5,
            QuestionType.FACTUAL: 0.3,
            QuestionType.CURRENT_EVENTS: 0.2
        }.get(state['question_type'], 0.4)
        
        return base_confidence
    
    def _determine_routing_strategy(self, vector_conf: float, web_conf: float, llm_conf: float) -> str:
        """Determine routing strategy."""
        confidences = {
            'vector_db_only': vector_conf,
            'web_search_only': web_conf,
            'llm_direct_only': llm_conf,
            'hybrid_vector_llm': (vector_conf + llm_conf) / 2,
            'hybrid_web_llm': (web_conf + llm_conf) / 2,
            'hybrid_all': (vector_conf + web_conf + llm_conf) / 3
        }
        
        best_strategy = max(confidences.items(), key=lambda x: x[1])
        return best_strategy[0] if best_strategy[1] >= 0.4 else 'llm_direct_only'
    
    def _get_recommended_sources(self, vector_conf: float, web_conf: float, llm_conf: float) -> List[str]:
        """Get recommended sources."""
        sources = []
        
        if vector_conf >= self.thresholds['vector_db']:
            sources.append('vector_db')
        if web_conf >= self.thresholds['web_search']:
            sources.append('web_search')
        if llm_conf >= self.thresholds['llm_direct']:
            sources.append('llm_direct')
        
        return sources if sources else ['llm_direct']
    
    def _determine_integration_strategy(self, results: List, state: QuestionState) -> str:
        """Determine integration strategy for hybrid answers."""
        if len(results) == 2:
            return 'complementary'
        elif any(source == 'web_search' for source, _ in results):
            return 'hierarchical'
        else:
            return 'weighted_merge'
    
    def _apply_integration_strategy(self, results: List, strategy: str, state: QuestionState) -> Dict[str, Any]:
        """Apply integration strategy to combine results."""
        # Simplified integration - in practice, this would be more sophisticated
        
        if strategy == 'hierarchical':
            # Prioritize web search for current info, then others
            for source, result in results:
                if source == 'web_search' and result.get('success'):
                    return self._format_final_answer(result, source, 'hierarchical')
        
        # Default: use the result with highest confidence
        best_source, best_result = max(results, key=lambda x: state['source_confidences'].get(x[0], 0))
        return self._format_final_answer(best_result, best_source, strategy)
    
    def _select_best_single_answer(self, state: QuestionState) -> Optional[Dict[str, Any]]:
        """Select best single answer from available results."""
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
        return self._format_final_answer(best_result, best_source, 'single')
    
    def _format_final_answer(self, result: Dict[str, Any], source: str, strategy: str) -> Dict[str, Any]:
        """Format final answer consistently."""
        
        # Extract content based on source type
        if source == 'llm_direct':
            content = result.get('content', '')
        elif source == 'vector_search':
            docs = result.get('documents', [])
            content = '\n\n'.join([doc.get('content', '') for doc in docs[:3]]) if docs else ''
        elif source == 'web_search':
            results_list = result.get('results', [])
            content = '\n\n'.join([f"{r.get('title', '')}: {r.get('snippet', '')}" for r in results_list[:3]]) if results_list else ''
        else:
            content = str(result.get('content', ''))
        
        return {
            'success': True,
            'content': content,
            'source_type': source.replace('_search', '_db').replace('_direct', ''),
            'confidence': {
                'relevance': 0.8,
                'completeness': 0.7,
                'accuracy': 0.8,
                'reliability': 0.7
            },
            'metadata': {
                'integration_strategy': strategy,
                'source': source,
                'original_result': result
            }
        }
    
    def run(self, question_content: str) -> Dict[str, Any]:
        """
        Run the question answering graph.
        
        Args:
            question_content: The question to answer
            
        Returns:
            Final answer with metadata
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
            total_processing_time=None
        )
        
        try:
            # Execute graph
            logger.info(f"Starting question answering workflow for: {question_content[:50]}...")
            final_state = self.graph.invoke(initial_state)
            
            logger.info("Question answering workflow completed successfully")
            return {
                'success': True,
                'answer': final_state.get('final_answer'),
                'individual_source_results': final_state.get('individual_source_results', {}),
                'metadata': {
                    'question_id': final_state['question_id'],
                    'question_type': final_state.get('question_type'),
                    'routing_strategy': final_state.get('routing_strategy'),
                    'source_confidences': final_state.get('source_confidences'),
                    'total_processing_time': final_state.get('total_processing_time'),
                    'agent_execution_times': final_state.get('agent_execution_times')
                }
            }
            
        except Exception as e:
            logger.error(f"Question answering workflow failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'answer': {
                    'content': "죄송합니다. 시스템 오류로 인해 답변을 생성할 수 없습니다.",
                    'source_type': 'error'
                }
            }