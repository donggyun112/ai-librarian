"""
LangChain-based answer service that provides compatibility with existing interfaces.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import logging
import os

from ...models.question import Question
from ...models.answer import Answer, AnswerSource, AnswerConfidence
from ...services.vector_store import VectorStore
from ...services.embedding_service import EmbeddingService
from ..graphs.question_answering_graph import QuestionAnsweringGraph
from ..graphs.selective_question_answering_graph import SelectiveQuestionAnsweringGraph
from ..graphs.autonomous_question_answering_graph import AutonomousQuestionAnsweringGraph
from ...services.routing_service import RoutingService, RoutingDecision, DataSource, RoutingStrategy

logger = logging.getLogger(__name__)


class LangChainAnswerService:
    """
    LangChain/LangGraph-based answer service that maintains compatibility 
    with the existing AnswerService interface.
    
    This service uses LangGraph workflows internally while providing
    the same API as the original AnswerService.
    """
    
    def __init__(self,
                 vector_store: VectorStore,
                 embedding_service: EmbeddingService,
                 openai_api_key: Optional[str] = None,
                 vector_db_threshold: float = 0.7,
                 web_search_threshold: float = 0.6,
                 llm_direct_threshold: float = 0.5,
                 use_autonomous_routing: bool = True,
                 enable_reflection: bool = False):
        """
        Initialize LangChain answer service.

        Args:
            vector_store: Vector store for document search
            embedding_service: Embedding service for query processing
            openai_api_key: OpenAI API key (will use env var if not provided)
            vector_db_threshold: Threshold for vector DB confidence
            web_search_threshold: Threshold for web search confidence
            llm_direct_threshold: Threshold for LLM direct confidence
            use_autonomous_routing: Use LLM-based autonomous routing (default: True)
            enable_reflection: Enable reflection for retry on failure (default: False)
        """
        self.vector_store = vector_store
        self.embedding_service = embedding_service
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.use_autonomous_routing = use_autonomous_routing

        if not self.openai_api_key:
            raise ValueError("OpenAI API key is required")

        # Initialize routing service
        self.routing_service = RoutingService(
            vector_db_threshold=vector_db_threshold,
            web_search_threshold=web_search_threshold,
            llm_direct_threshold=llm_direct_threshold
        )

        # Initialize LangGraph workflows
        self.graph = QuestionAnsweringGraph(
            vector_store=vector_store,
            embedding_service=embedding_service,
            openai_api_key=self.openai_api_key,
            vector_db_threshold=vector_db_threshold,
            web_search_threshold=web_search_threshold,
            llm_direct_threshold=llm_direct_threshold
        )

        self.selective_graph = SelectiveQuestionAnsweringGraph(
            vector_store=vector_store,
            embedding_service=embedding_service,
            openai_api_key=self.openai_api_key,
            routing_service=self.routing_service
        )

        # NEW: Autonomous graph with LLM-based routing
        self.autonomous_graph = AutonomousQuestionAnsweringGraph(
            vector_store=vector_store,
            embedding_service=embedding_service,
            openai_api_key=self.openai_api_key,
            router_model="gpt-4o-mini",
            enable_reflection=enable_reflection
        )

        # Statistics tracking
        self.stats = {
            'total_questions': 0,
            'successful_answers': 0,
            'failed_answers': 0,
            'average_processing_time': 0.0,
            'source_usage': {
                'vector_db': 0,
                'web_search': 0,
                'llm_direct': 0,
                'hybrid': 0
            },
            'routing_mode': 'autonomous' if use_autonomous_routing else 'rule_based'
        }
    
    def get_answer(self, question: Question) -> Optional[Answer]:
        """
        Get answer for a question using LangGraph workflow.

        Uses autonomous LLM-based routing by default, or falls back to rule-based routing.

        Args:
            question: Question object to answer

        Returns:
            Answer object or None if failed
        """
        start_time = datetime.now()

        try:
            logger.info(f"Processing question via LangGraph: {question.content[:50]}...")

            # Choose routing mode
            if self.use_autonomous_routing:
                logger.info("Using AUTONOMOUS LLM-based routing")
                result = self.autonomous_graph.run(question.content)
            else:
                logger.info("Using RULE-based routing")
                result = self.graph.run(question.content)

            if not result.get('success'):
                logger.error(f"LangGraph workflow failed: {result.get('error')}")
                self._update_stats(False, 0)
                return None

            # Extract answer data
            answer_data = result.get('answer', {})
            metadata = result.get('metadata', {})
            routing_info = result.get('routing_info', {})

            # Convert to Answer object
            answer = self._convert_to_answer_object(answer_data, metadata, question)

            # Add routing info to answer metadata
            if self.use_autonomous_routing:
                answer.metadata.update({
                    'routing_mode': 'autonomous_llm',
                    'selected_tool': routing_info.get('selected_tool'),
                    'routing_confidence': routing_info.get('routing_confidence'),
                    'routing_reasoning': routing_info.get('routing_reasoning'),
                    'attempt_count': routing_info.get('attempt_count', 1),
                    'reflection_used': routing_info.get('reflection_used', False)
                })

            # Update statistics
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            self._update_stats(True, processing_time)

            if self.use_autonomous_routing:
                tool_used = routing_info.get('selected_tool', 'unknown')
                self._update_source_usage(tool_used)
            else:
                self._update_source_usage(metadata.get('routing_strategy', 'unknown'))

            logger.info(f"Question answered successfully in {processing_time:.0f}ms")
            return answer

        except Exception as e:
            logger.error(f"LangChain answer service error: {str(e)}")
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            self._update_stats(False, processing_time)
            return None
    
    def get_comprehensive_answer(self, question: Question, show_all_sources: bool = False, force_hybrid: bool = False) -> Dict[str, Any]:
        """
        Get comprehensive answer with detailed metadata and individual source answers.
        
        Args:
            question: Question to answer
            show_all_sources: If True, get answers from all sources regardless of routing
            force_hybrid: If True, force hybrid integration of all available sources
            
        Returns:
            Comprehensive answer data with individual source answers
        """
        start_time = datetime.now()
        
        try:
            if show_all_sources:
                # Get answers from all sources
                return self._get_all_source_answers(question, force_hybrid)
            else:
                # Use routing based on configuration
                if self.use_autonomous_routing:
                    logger.info("Using AUTONOMOUS routing in comprehensive answer")
                    result = self.autonomous_graph.run(question.content)
                else:
                    logger.info("Using RULE-BASED routing in comprehensive answer")
                    result = self.graph.run(question.content)
                
                processing_time = (datetime.now() - start_time).total_seconds() * 1000
                
                if not result.get('success'):
                    return {
                        'success': False,
                        'error': result.get('error', 'Unknown error'),
                        'processing_time': processing_time
                    }
                
                answer_data = result.get('answer', {})
                metadata = result.get('metadata', {})

                # Get individual source answers from graph results
                individual_answers = self._extract_individual_answers_from_graph(result, question)

                # Build routing info based on routing mode
                if self.use_autonomous_routing:
                    routing_info_dict = result.get('routing_info', {})
                    routing_info_dict['total_processing_time'] = processing_time
                else:
                    routing_info_dict = {
                        'strategy': metadata.get('routing_strategy'),
                        'source_confidences': metadata.get('source_confidences', {}),
                        'question_type': metadata.get('question_type'),
                        'total_processing_time': processing_time
                    }

                # Format comprehensive response
                final_answer_obj = self._convert_to_answer_object(answer_data, metadata, question)

                # Add autonomous routing metadata if applicable
                if self.use_autonomous_routing:
                    final_answer_obj.metadata.update({
                        'routing_mode': 'autonomous_llm',
                        'selected_tool': routing_info_dict.get('selected_tool'),
                        'routing_confidence': routing_info_dict.get('routing_confidence'),
                        'routing_reasoning': routing_info_dict.get('routing_reasoning'),
                        'attempt_count': routing_info_dict.get('attempt_count', 1),
                        'reflection_used': routing_info_dict.get('reflection_used', False)
                    })
                else:
                    final_answer_obj.metadata['routing_mode'] = 'rule_based'

                comprehensive_answer = {
                    'success': True,
                    'final_answer': final_answer_obj,
                    'individual_answers': individual_answers,
                    'routing_info': routing_info_dict,
                    'performance_metrics': {
                        'total_time': processing_time,
                        'agent_times': metadata.get('agent_execution_times', {}),
                        'token_usage': self._extract_token_usage(answer_data)
                    },
                    'metadata': {
                        'question_id': metadata.get('question_id'),
                        'timestamp': datetime.now().isoformat(),
                        'system': 'langchain_langgraph',
                        'show_all_sources': show_all_sources,
                        'force_hybrid': force_hybrid
                    }
                }
                
                # Update statistics
                self._update_stats(True, processing_time)

                # Update source usage based on routing mode
                if self.use_autonomous_routing:
                    tool_used = routing_info_dict.get('selected_tool', 'unknown')
                    self._update_source_usage(tool_used)
                else:
                    self._update_source_usage(metadata.get('routing_strategy', 'unknown'))
                
                return comprehensive_answer
                
        except Exception as e:
            logger.error(f"Comprehensive answer error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'processing_time': (datetime.now() - start_time).total_seconds() * 1000
            }
    
    def _get_all_source_answers(self, question: Question, force_hybrid: bool = False) -> Dict[str, Any]:
        """Get answers from all sources regardless of routing."""
        start_time = datetime.now()
        individual_answers = {}
        
        try:
            # Get answer from each source
            logger.info("Getting answers from all sources...")
            
            # Vector DB search
            try:
                vector_result = self.graph.tools['vector_search']._run(question.content, top_k=5)
                if vector_result.get('success'):
                    individual_answers['vector_db'] = self._format_individual_answer(
                        vector_result, 'vector_db', question
                    )
            except Exception as e:
                logger.error(f"Vector search failed: {e}")
            
            # Web search
            try:
                web_result = self.graph.tools['web_search']._run(question.content, max_results=5)
                if web_result.get('success'):
                    individual_answers['web_search'] = self._format_individual_answer(
                        web_result, 'web_search', question
                    )
            except Exception as e:
                logger.error(f"Web search failed: {e}")
            
            # LLM direct
            try:
                llm_result = self.graph.tools['llm_direct']._run(
                    question.content, 
                    question_type='general',
                    creativity_level=0.7
                )
                if llm_result.get('success'):
                    individual_answers['llm_direct'] = self._format_individual_answer(
                        llm_result, 'llm_direct', question
                    )
            except Exception as e:
                logger.error(f"LLM direct failed: {e}")
            
            # Create hybrid answer if requested and multiple sources available
            final_answer = None
            integration_strategy = 'none'
            
            if force_hybrid and len(individual_answers) > 1:
                final_answer = self._create_hybrid_answer(individual_answers, question)
                integration_strategy = 'forced_hybrid'
            elif len(individual_answers) == 1:
                # Use the single available answer
                source_name, source_data = next(iter(individual_answers.items()))
                final_answer = source_data.get('answer')
                integration_strategy = f'single_{source_name}'
            elif len(individual_answers) > 1:
                # Use the best answer
                best_answer = self._select_best_individual_answer(individual_answers)
                final_answer = best_answer
                integration_strategy = 'best_selection'
            
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return {
                'success': True,
                'final_answer': final_answer,
                'individual_answers': individual_answers,
                'routing_info': {
                    'strategy': integration_strategy,
                    'source_confidences': {name: 1.0 for name in individual_answers.keys()},
                    'question_type': self._classify_question_type(question.content),
                    'total_processing_time': processing_time
                },
                'performance_metrics': {
                    'total_time': processing_time,
                    'agent_times': {name: data.get('processing_time', 0) for name, data in individual_answers.items()},
                    'sources_attempted': len(individual_answers)
                },
                'metadata': {
                    'question_id': question.id,
                    'timestamp': datetime.now().isoformat(),
                    'system': 'langchain_all_sources',
                    'show_all_sources': True,
                    'force_hybrid': force_hybrid
                }
            }
            
        except Exception as e:
            logger.error(f"All sources answer error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'processing_time': (datetime.now() - start_time).total_seconds() * 1000
            }
    
    def _extract_individual_answers_from_graph(self, graph_result: Dict[str, Any], question: Question) -> Dict[str, Any]:
        """Extract individual answers from graph execution results."""
        individual_answers = {}
        
        # Get individual source results from graph
        individual_results = graph_result.get('individual_source_results', {})
        
        # Format each source result as answer
        for source_key, raw_result in individual_results.items():
            if raw_result and raw_result.get('success'):
                source_type = source_key.replace('_search', '').replace('_result', '')
                if source_type == 'vector':
                    source_type = 'vector_db'
                
                individual_answers[source_type] = self._format_individual_answer(
                    raw_result, source_type, question
                )
            
        return individual_answers
    
    def _create_hybrid_answer(self, individual_answers: Dict[str, Any], question: Question) -> Answer:
        """Create hybrid answer by combining all individual answers."""
        
        # Combine all answer contents
        combined_content = "## 📚 종합 답변 (다중 소스 통합)\n\n"
        
        source_order = ['vector_db', 'llm_direct', 'web_search']  # Preferred order
        
        for source_type in source_order:
            if source_type in individual_answers:
                source_data = individual_answers[source_type]
                answer = source_data.get('answer')
                if answer:
                    source_names = {
                        'vector_db': '📚 벡터 데이터베이스',
                        'llm_direct': '🤖 LLM 직접 답변',
                        'web_search': '🌐 웹 검색'
                    }
                    
                    combined_content += f"### {source_names.get(source_type, source_type)}\n\n"
                    combined_content += f"{answer.content}\n\n"
                    combined_content += "---\n\n"
        
        # Calculate average confidence
        all_confidences = []
        for source_data in individual_answers.values():
            answer = source_data.get('answer')
            if answer:
                all_confidences.append(answer.confidence)
        
        if all_confidences:
            avg_confidence = AnswerConfidence(
                relevance=sum(c.relevance for c in all_confidences) / len(all_confidences),
                completeness=sum(c.completeness for c in all_confidences) / len(all_confidences),
                accuracy=sum(c.accuracy for c in all_confidences) / len(all_confidences),
                reliability=sum(c.reliability for c in all_confidences) / len(all_confidences)
            )
        else:
            avg_confidence = AnswerConfidence()
        
        # Create hybrid answer
        hybrid_answer = Answer(
            content=combined_content,
            primary_source=AnswerSource.HYBRID,
            confidence=avg_confidence,
            question_id=question.id
        )
        
        hybrid_answer.metadata.update({
            'integration_strategy': 'forced_hybrid',
            'sources_combined': list(individual_answers.keys()),
            'total_sources': len(individual_answers)
        })
        
        return hybrid_answer
    
    def _select_best_individual_answer(self, individual_answers: Dict[str, Any]) -> Answer:
        """Select the best individual answer based on confidence."""
        
        best_answer = None
        best_score = 0.0
        
        for source_data in individual_answers.values():
            answer = source_data.get('answer')
            if answer:
                score = answer.confidence.overall_score()
                if score > best_score:
                    best_score = score
                    best_answer = answer
        
        return best_answer or Answer(
            content="답변을 생성할 수 없습니다.",
            primary_source=AnswerSource.UNKNOWN,
            confidence=AnswerConfidence(),
            question_id=""
        )
    
    def _classify_question_type(self, text: str) -> str:
        """Simple question type classification."""
        text_lower = text.lower()
        
        if any(keyword in text_lower for keyword in ['최근', '최신', '2024', '현재']):
            return 'CURRENT_EVENTS'
        elif any(keyword in text_lower for keyword in ['정의', '의미', '설명', '차이']):
            return 'FACTUAL'
        elif len(text.split()) > 20:
            return 'COMPLEX'
        else:
            return 'GENERAL'
    
    def _convert_to_answer_object(self, answer_data: Dict[str, Any], 
                                 metadata: Dict[str, Any], 
                                 question: Question) -> Answer:
        """Convert LangGraph result to Answer object."""
        
        # Extract content
        content = answer_data.get('content', '')
        if not content:
            content = "답변을 생성할 수 없습니다."
        
        # Determine source type
        source_type_map = {
            'vector_db': AnswerSource.VECTOR_DB,
            'web_search': AnswerSource.WEB_SEARCH,
            'llm_direct': AnswerSource.LLM_DIRECT,
            'hybrid': AnswerSource.HYBRID
        }
        
        source_type = answer_data.get('source_type', 'llm_direct')
        answer_source = source_type_map.get(source_type, AnswerSource.LLM_DIRECT)
        
        # Extract or create confidence metrics
        confidence_data = answer_data.get('confidence', {})
        confidence = AnswerConfidence(
            relevance=confidence_data.get('relevance', 0.7),
            completeness=confidence_data.get('completeness', 0.7),
            accuracy=confidence_data.get('accuracy', 0.7),
            reliability=confidence_data.get('reliability', 0.7)
        )
        
        # Create Answer object
        answer = Answer(
            content=content,
            primary_source=answer_source,
            confidence=confidence,
            question_id=question.id
        )
        
        # Add metadata
        answer.metadata.update({
            'langchain_system': True,
            'routing_strategy': metadata.get('routing_strategy'),
            'question_type': str(metadata.get('question_type', '')),
            'source_confidences': metadata.get('source_confidences', {}),
            'processing_time': metadata.get('total_processing_time', 0),
            'agent_execution_times': metadata.get('agent_execution_times', {}),
            'original_answer_data': answer_data
        })
        
        return answer
    
    def _format_individual_answer(self, result: Dict[str, Any], source_type: str, question: Question) -> Dict[str, Any]:
        """Format individual source result as answer."""
        
        # Extract content based on source type
        if source_type == 'llm_direct':
            content = result.get('content', '')
            confidence_score = 0.8
        elif source_type == 'vector_db':
            docs = result.get('documents', [])
            if docs:
                content = '\n\n'.join([
                    f"**문서 {i+1}** (유사도: {doc.get('similarity_score', 0):.2f})\n{doc.get('content', '')}"
                    for i, doc in enumerate(docs[:3])
                ])
                confidence_score = sum(doc.get('similarity_score', 0) for doc in docs) / len(docs)
            else:
                content = '관련 문서를 찾을 수 없습니다.'
                confidence_score = 0.0
        elif source_type == 'web_search':
            results_list = result.get('results', [])
            if results_list:
                content = '\n\n'.join([
                    f"**{r.get('title', 'N/A')}**\n{r.get('snippet', '')}\n출처: {r.get('source', 'N/A')}"
                    for r in results_list[:3]
                ])
                confidence_score = sum(r.get('relevance_score', 0) for r in results_list) / len(results_list)
            else:
                content = '웹 검색 결과를 찾을 수 없습니다.'
                confidence_score = 0.0
        else:
            content = str(result.get('content', '답변을 생성할 수 없습니다.'))
            confidence_score = 0.5
        
        # Create confidence metrics
        confidence = AnswerConfidence(
            relevance=confidence_score,
            completeness=0.7,
            accuracy=confidence_score,
            reliability=0.7
        )
        
        # Create Answer object
        source_map = {
            'vector_db': AnswerSource.VECTOR_DB,
            'web_search': AnswerSource.WEB_SEARCH,
            'llm_direct': AnswerSource.LLM_DIRECT
        }
        
        answer = Answer(
            content=content,
            primary_source=source_map.get(source_type, AnswerSource.UNKNOWN),
            confidence=confidence,
            question_id=question.id
        )
        
        return {
            'answer': answer,
            'raw_result': result,
            'processing_time': result.get('processing_time', 0),
            'success': result.get('success', False)
        }
    
    def _extract_token_usage(self, answer_data: Dict[str, Any]) -> Dict[str, int]:
        """Extract token usage information."""
        original_result = answer_data.get('metadata', {}).get('original_result', {})
        return original_result.get('token_usage', {})
    
    def _update_stats(self, success: bool, processing_time: float):
        """Update service statistics."""
        self.stats['total_questions'] += 1
        
        if success:
            self.stats['successful_answers'] += 1
        else:
            self.stats['failed_answers'] += 1
        
        # Update average processing time
        total_successful = self.stats['successful_answers']
        if total_successful > 0:
            current_avg = self.stats['average_processing_time']
            self.stats['average_processing_time'] = (
                (current_avg * (total_successful - 1) + processing_time) / total_successful
            )
    
    def _update_source_usage(self, routing_strategy: str):
        """Update source usage statistics."""
        if 'hybrid' in routing_strategy.lower():
            self.stats['source_usage']['hybrid'] += 1
        elif 'vector' in routing_strategy.lower():
            self.stats['source_usage']['vector_db'] += 1
        elif 'web' in routing_strategy.lower():
            self.stats['source_usage']['web_search'] += 1
        elif 'llm' in routing_strategy.lower():
            self.stats['source_usage']['llm_direct'] += 1
    
    def get_service_stats(self) -> Dict[str, Any]:
        """Get service statistics."""
        return {
            'system': 'LangChain/LangGraph',
            'stats': self.stats.copy(),
            'thresholds': self.graph.thresholds,
            'available_tools': list(self.graph.tools.keys()),
            'graph_info': {
                'nodes': ['analyze_question', 'route_question', 'execute_vector_search', 
                         'execute_web_search', 'execute_llm_direct', 'integrate_results', 
                         'finalize_answer'],
                'workflow_type': 'StateGraph'
            }
        }
    
    def reset_stats(self):
        """Reset service statistics."""
        self.stats = {
            'total_questions': 0,
            'successful_answers': 0,
            'failed_answers': 0,
            'average_processing_time': 0.0,
            'source_usage': {
                'vector_db': 0,
                'web_search': 0,
                'llm_direct': 0,
                'hybrid': 0
            }
        }
        logger.info("Service statistics reset")
    
    def get_answer_with_routing(self, 
                                   question: Question,
                                   preferred_sources: Optional[List[str]] = None,
                                   preferred_strategy: Optional[str] = None) -> Optional[Answer]:
        """
        라우팅 지정과 함께 답변 생성.
        
        Args:
            question: 질문 객체
            preferred_sources: 선호하는 데이터소스 목록 ['vector_db', 'web_search', 'llm_direct']
            preferred_strategy: 선호하는 전략 ['single_source', 'hybrid', 'sequential', 'parallel']
            
        Returns:
            Answer 객체 또는 None
        """
        start_time = datetime.now()
        
        try:
            logger.info(f"Processing question with routing: {question.content[:50]}...")
            
            # Run selective graph with routing
            result = self.selective_graph.run_with_routing(
                question_content=question.content,
                preferred_sources=preferred_sources,
                preferred_strategy=preferred_strategy
            )
            
            if not result.get('success'):
                logger.error(f"Selective graph failed: {result.get('error')}")
                self._update_stats(False, 0)
                return None
            
            # Extract answer data
            answer_data = result.get('answer', {})
            metadata = result.get('metadata', {})
            routing_info = result.get('routing_info', {})
            
            # Convert to Answer object
            answer = self._convert_to_answer_object(answer_data, metadata, question)
            
            # Add routing information to metadata
            answer.metadata.update({
                'routing_info': routing_info,
                'selected_sources': routing_info.get('selected_sources', []),
                'routing_strategy': routing_info.get('routing_strategy'),
                'routing_reasoning': routing_info.get('routing_reasoning', '')
            })
            
            # Update statistics
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            self._update_stats(True, processing_time)
            self._update_source_usage(routing_info.get('routing_strategy', 'unknown'))
            
            logger.info(f"Question answered with routing in {processing_time:.0f}ms")
            return answer
            
        except Exception as e:
            logger.error(f"Routing answer service error: {str(e)}")
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            self._update_stats(False, processing_time)
            return None
    
    def get_routing_recommendation(self, question: Question) -> Dict[str, Any]:
        """
        질문에 대한 라우팅 추천 정보 제공.
        
        Args:
            question: 분석할 질문
            
        Returns:
            라우팅 추천 정보
        """
        try:
            # Get routing decision without execution
            routing_decision = self.routing_service.decide_routing(question)
            
            return {
                'success': True,
                'recommendation': routing_decision.to_dict(),
                'available_sources': [source.value for source in DataSource],
                'available_strategies': [strategy.value for strategy in RoutingStrategy],
                'routing_stats': self.routing_service.get_routing_stats()
            }
            
        except Exception as e:
            logger.error(f"Failed to get routing recommendation: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'available_sources': [source.value for source in DataSource],
                'available_strategies': [strategy.value for strategy in RoutingStrategy]
            }
    
    def get_comprehensive_answer_with_routing(self, 
                                            question: Question,
                                            preferred_sources: Optional[List[str]] = None,
                                            preferred_strategy: Optional[str] = None,
                                            show_routing_analysis: bool = True) -> Dict[str, Any]:
        """
        라우팅과 함께 포괄적 답변 생성.
        
        Args:
            question: 질문 객체
            preferred_sources: 선호하는 데이터소스 목록
            preferred_strategy: 선호하는 전략
            show_routing_analysis: 라우팅 분석 정보 포함 여부
            
        Returns:
            포괄적 답변 데이터
        """
        start_time = datetime.now()
        
        try:
            # Get routing recommendation if requested
            routing_analysis = None
            if show_routing_analysis:
                routing_analysis = self.get_routing_recommendation(question)
            
            # Run selective graph
            result = self.selective_graph.run_with_routing(
                question_content=question.content,
                preferred_sources=preferred_sources,
                preferred_strategy=preferred_strategy
            )
            
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            if not result.get('success'):
                return {
                    'success': False,
                    'error': result.get('error', 'Unknown error'),
                    'processing_time': processing_time,
                    'routing_analysis': routing_analysis
                }
            
            answer_data = result.get('answer', {})
            metadata = result.get('metadata', {})
            routing_info = result.get('routing_info', {})
            
            # Get individual source answers
            individual_answers = self._extract_individual_answers_from_graph(result, question)
            
            # Format comprehensive response
            comprehensive_answer = {
                'success': True,
                'final_answer': self._convert_to_answer_object(answer_data, metadata, question),
                'individual_answers': individual_answers,
                'routing_info': routing_info,
                'routing_analysis': routing_analysis,
                'performance_metrics': {
                    'total_time': processing_time,
                    'agent_times': metadata.get('agent_execution_times', {}),
                    'sources_executed': len(routing_info.get('selected_sources', []))
                },
                'metadata': {
                    'question_id': metadata.get('question_id'),
                    'timestamp': datetime.now().isoformat(),
                    'system': 'langchain_selective_routing',
                    'preferred_sources': preferred_sources,
                    'preferred_strategy': preferred_strategy
                }
            }
            
            # Update statistics
            self._update_stats(True, processing_time)
            self._update_source_usage(routing_info.get('routing_strategy', 'unknown'))
            
            return comprehensive_answer
            
        except Exception as e:
            logger.error(f"Comprehensive routing answer error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'processing_time': (datetime.now() - start_time).total_seconds() * 1000,
                'routing_analysis': routing_analysis if show_routing_analysis else None
            }
    
    # Compatibility methods for existing interfaces
    def get_available_agents(self) -> List[str]:
        """Get list of available agents (for compatibility)."""
        return ['vector_search', 'web_search', 'llm_direct', 'question_router']
    
    def get_available_sources(self) -> List[str]:
        """사용 가능한 데이터소스 목록 반환."""
        return [source.value for source in DataSource]
    
    def get_available_strategies(self) -> List[str]:
        """사용 가능한 라우팅 전략 목록 반환."""
        return [strategy.value for strategy in RoutingStrategy]
    
    def get_routing_info(self, question: Question) -> Dict[str, Any]:
        """Get routing information without executing (simplified for compatibility)."""
        return {
            'system': 'langchain_langgraph_selective',
            'note': 'Routing can be controlled externally or handled automatically',
            'available_sources': self.get_available_sources(),
            'available_strategies': self.get_available_strategies(),
            'routing_service_stats': self.routing_service.get_routing_stats()
        }