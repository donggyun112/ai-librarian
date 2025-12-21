"""
Autonomous Question Answering Graph with LLM-based routing.

This graph uses an LLM to autonomously decide which tool to use,
executing only the selected tool for efficiency.
"""

from typing import Dict, List, Any, Optional, Literal
from datetime import datetime
import logging
import uuid

from langgraph.graph import StateGraph, END

from ..schemas.question_answer_schema import QuestionState
from ..agents.llm_router import LLMRouter, RouterDecision, ToolChoice
from ..tools.vector_search_tool import VectorSearchTool
from ..tools.web_search_tool import WebSearchTool
from ..tools.llm_direct_tool import LLMDirectTool
from ...models.question import Question, QuestionType
from ...models.answer import Answer, AnswerConfidence
from ...services.vector_store import VectorStore
from ...services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class AutonomousQuestionAnsweringGraph:
    """
    LLM-based autonomous question answering graph.

    This graph uses an LLM router to intelligently select which tool to use
    for each question, executing only the selected tool for maximum efficiency.
    """

    def __init__(self,
                 vector_store: VectorStore,
                 embedding_service: EmbeddingService,
                 openai_api_key: str,
                 router_model: str = "gpt-4o-mini",
                 enable_reflection: bool = False):
        """
        Initialize the autonomous question answering graph.

        Args:
            vector_store: Vector store for document search
            embedding_service: Embedding service for query processing
            openai_api_key: OpenAI API key
            router_model: LLM model to use for routing decisions
            enable_reflection: Enable reflection-based routing (learns from failures)
        """
        self.vector_store = vector_store
        self.embedding_service = embedding_service
        self.openai_api_key = openai_api_key
        self.enable_reflection = enable_reflection
        self.router_model = router_model  # Store router model name

        # Initialize LLM router
        self.router = LLMRouter(
            openai_api_key=openai_api_key,
            model=router_model,
            temperature=0.0
        )

        # Initialize tools
        self.tools = {
            'vector_search': VectorSearchTool(
                vector_store=vector_store,
                embedding_service=embedding_service
            ),
            'web_search': WebSearchTool(),
            'llm_direct': LLMDirectTool(openai_api_key=openai_api_key)
        }

        # Build the graph
        self.graph = self._build_graph()

        # Statistics
        self.stats = {
            'total_questions': 0,
            'successful_answers': 0,
            'failed_answers': 0,
            'tool_usage': {
                'vector_db': 0,
                'web_search': 0,
                'llm_direct': 0,
                'hybrid': 0
            },
            'reflection_count': 0,
            'average_processing_time': 0.0
        }

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow with LLM-based routing."""

        workflow = StateGraph(QuestionState)

        # Add nodes
        workflow.add_node("llm_route", self._llm_route_node)
        workflow.add_node("execute_vector_search", self._execute_vector_search_node)
        workflow.add_node("execute_web_search", self._execute_web_search_node)
        workflow.add_node("execute_llm_direct", self._execute_llm_direct_node)
        workflow.add_node("execute_hybrid", self._execute_hybrid_node)
        workflow.add_node("evaluate_result", self._evaluate_result_node)
        workflow.add_node("reflect_and_retry", self._reflect_and_retry_node)
        workflow.add_node("finalize_answer", self._finalize_answer_node)

        # Set entry point
        workflow.set_entry_point("llm_route")

        # Routing decision: LLM decides which tool to use
        workflow.add_conditional_edges(
            "llm_route",
            self._route_to_tool,
            {
                "vector_db": "execute_vector_search",
                "web_search": "execute_web_search",
                "llm_direct": "execute_llm_direct",
                "hybrid": "execute_hybrid"
            }
        )

        # After tool execution, evaluate the result
        workflow.add_edge("execute_vector_search", "evaluate_result")
        workflow.add_edge("execute_web_search", "evaluate_result")
        workflow.add_edge("execute_llm_direct", "evaluate_result")
        workflow.add_edge("execute_hybrid", "evaluate_result")

        # Evaluation: Check if result is satisfactory
        workflow.add_conditional_edges(
            "evaluate_result",
            self._should_retry,
            {
                "finalize": "finalize_answer",
                "retry": "reflect_and_retry"
            }
        )

        # Retry with reflection
        workflow.add_conditional_edges(
            "reflect_and_retry",
            self._route_to_tool,
            {
                "vector_db": "execute_vector_search",
                "web_search": "execute_web_search",
                "llm_direct": "execute_llm_direct",
                "hybrid": "execute_hybrid"
            }
        )

        # End
        workflow.add_edge("finalize_answer", END)

        return workflow.compile()

    def _llm_route_node(self, state: QuestionState) -> QuestionState:
        """LLM-based routing node."""
        logger.info(f"LLM routing for question: {state['question_content'][:50]}...")

        try:
            # Use LLM to decide which tool to use
            routing_decision = self.router.route(state['question_content'])

            # Extract tool values (handle both Enum and string cases)
            primary_tool_value = routing_decision.primary_tool.value if hasattr(routing_decision.primary_tool, 'value') else routing_decision.primary_tool
            fallback_tool_value = routing_decision.fallback_tool.value if (routing_decision.fallback_tool and hasattr(routing_decision.fallback_tool, 'value')) else routing_decision.fallback_tool

            # Update state with routing decision
            state.update({
                'routing_decision': routing_decision,
                'selected_tool': primary_tool_value,
                'routing_confidence': routing_decision.confidence,
                'routing_reasoning': routing_decision.reasoning,
                'requires_hybrid': routing_decision.requires_multiple_tools,
                'fallback_tool': fallback_tool_value,
                'routing_timestamp': datetime.now(),
                'attempt_count': state.get('attempt_count', 0)
            })

            logger.info(
                f"LLM Router selected: {primary_tool_value} "
                f"(confidence: {routing_decision.confidence:.2f})"
            )
            logger.info(f"Reasoning: {routing_decision.reasoning}")

        except Exception as e:
            logger.error(f"LLM routing failed: {str(e)}")
            # Fallback to LLM direct
            state.update({
                'selected_tool': 'llm_direct',
                'routing_confidence': 0.5,
                'routing_reasoning': f'Routing error, falling back to LLM: {str(e)}',
                'routing_timestamp': datetime.now()
            })

        return state

    def _execute_vector_search_node(self, state: QuestionState) -> QuestionState:
        """Execute vector database search."""
        logger.info("Executing vector search (selected by LLM)...")
        start_time = datetime.now()

        try:
            result = self.tools['vector_search']._run(
                query=state['question_content'],
                top_k=5,
                similarity_threshold=0.7
            )

            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            state['agent_execution_times']['vector_search'] = processing_time
            state['tool_result'] = result
            state['tool_used'] = 'vector_db'

            logger.info(f"Vector search completed in {processing_time:.0f}ms - Success: {result.get('success')}")

        except Exception as e:
            logger.error(f"Vector search failed: {str(e)}")
            state['tool_result'] = {
                'success': False,
                'message': f"Vector search error: {str(e)}"
            }
            state['tool_used'] = 'vector_db'

        return state

    def _execute_web_search_node(self, state: QuestionState) -> QuestionState:
        """Execute web search."""
        logger.info("Executing web search (selected by LLM)...")
        start_time = datetime.now()

        try:
            result = self.tools['web_search']._run(
                query=state['question_content'],
                max_results=5,
                focus_recent=True
            )

            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            state['agent_execution_times']['web_search'] = processing_time
            state['tool_result'] = result
            state['tool_used'] = 'web_search'

            logger.info(f"Web search completed in {processing_time:.0f}ms - Success: {result.get('success')}")

        except Exception as e:
            logger.error(f"Web search failed: {str(e)}")
            state['tool_result'] = {
                'success': False,
                'message': f"Web search error: {str(e)}"
            }
            state['tool_used'] = 'web_search'

        return state

    def _execute_llm_direct_node(self, state: QuestionState) -> QuestionState:
        """Execute direct LLM query."""
        logger.info("Executing LLM direct (selected by LLM)...")
        start_time = datetime.now()

        try:
            result = self.tools['llm_direct']._run(
                query=state['question_content'],
                question_type='general',
                creativity_level=0.7
            )

            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            state['agent_execution_times']['llm_direct'] = processing_time
            state['tool_result'] = result
            state['tool_used'] = 'llm_direct'

            logger.info(f"LLM direct completed in {processing_time:.0f}ms - Success: {result.get('success')}")

        except Exception as e:
            logger.error(f"LLM direct failed: {str(e)}")
            state['tool_result'] = {
                'success': False,
                'message': f"LLM direct error: {str(e)}"
            }
            state['tool_used'] = 'llm_direct'

        return state

    def _execute_hybrid_node(self, state: QuestionState) -> QuestionState:
        """Execute multiple tools in hybrid mode."""
        logger.info("Executing hybrid mode (multiple tools)...")

        routing_decision = state.get('routing_decision')
        tools_to_use = [routing_decision.primary_tool.value] + [
            tool.value for tool in routing_decision.additional_tools
        ]

        results = {}
        
        # Helper function for parallel execution
        def execute_tool(tool_name):
            if tool_name == 'vector_db':
                return 'vector_db', self._execute_vector_search_node(state.copy()).get('tool_result')
            elif tool_name == 'web_search':
                return 'web_search', self._execute_web_search_node(state.copy()).get('tool_result')
            elif tool_name == 'llm_direct':
                return 'llm_direct', self._execute_llm_direct_node(state.copy()).get('tool_result')
            return tool_name, None

        # Execute tools in parallel
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(tools_to_use)) as executor:
            future_to_tool = {executor.submit(execute_tool, tool): tool for tool in tools_to_use}
            for future in concurrent.futures.as_completed(future_to_tool):
                try:
                    tool_name, result = future.result()
                    if result:
                        results[tool_name] = result
                except Exception as e:
                    logger.error(f"Error executing tool in hybrid mode: {e}")

        # Combine results
        state['tool_result'] = {
            'success': True,
            'hybrid_results': results,
            'content': self._combine_hybrid_results(results)
        }
        state['tool_used'] = 'hybrid'

        logger.info(f"Hybrid execution completed with {len(results)} tools")
        return state

    def _combine_hybrid_results(self, results: Dict[str, Any]) -> str:
        """Combine results from multiple tools."""
        combined = "## 종합 답변 (다중 소스)\n\n"

        for tool_name, result in results.items():
            if result and result.get('success'):
                combined += f"### {tool_name}\n"
                combined += f"{result.get('content', 'No content')}\n\n"

        return combined

    def _evaluate_result_node(self, state: QuestionState) -> QuestionState:
        """Evaluate if the result is satisfactory."""
        logger.info("Evaluating tool execution result...")

        tool_result = state.get('tool_result', {})
        success = tool_result.get('success', False)

        # Check if we should retry
        attempt_count = state.get('attempt_count', 0)
        max_attempts = 2

        state['result_satisfactory'] = success
        state['can_retry'] = (not success) and (attempt_count < max_attempts) and self.enable_reflection

        if not success:
            logger.warning(f"Tool execution failed: {tool_result.get('message', 'Unknown error')}")
        else:
            logger.info("Tool execution successful")

        return state

    def _reflect_and_retry_node(self, state: QuestionState) -> QuestionState:
        """Reflect on failure and select a different tool."""
        logger.info("Reflecting on failure and selecting alternative tool...")

        self.stats['reflection_count'] += 1

        # Build context of previous attempt
        previous_attempts = state.get('previous_attempts', [])
        previous_attempts.append({
            'tool': state.get('tool_used'),
            'success': False,
            'result': state.get('tool_result', {}).get('message', 'Failed'),
            'reasoning': state.get('routing_reasoning', '')
        })

        state['previous_attempts'] = previous_attempts
        state['attempt_count'] = state.get('attempt_count', 0) + 1

        # Use router with reflection
        routing_decision = self.router.route_with_reflection(
            state['question_content'],
            previous_attempts=previous_attempts
        )

        # Update state with new routing
        state.update({
            'routing_decision': routing_decision,
            'selected_tool': routing_decision.primary_tool.value,
            'routing_confidence': routing_decision.confidence,
            'routing_reasoning': routing_decision.reasoning,
            'routing_timestamp': datetime.now()
        })

        logger.info(f"Retry with tool: {routing_decision.primary_tool.value}")
        return state

    def _finalize_answer_node(self, state: QuestionState) -> QuestionState:
        """Finalize the answer."""
        logger.info("Finalizing answer...")

        tool_result = state.get('tool_result', {})

        if tool_result.get('success'):
            state['final_answer'] = tool_result
        else:
            # Use fallback tool if available
            fallback_tool = state.get('fallback_tool')
            if fallback_tool and not state.get('fallback_used'):
                logger.info(f"Using fallback tool: {fallback_tool}")
                state['fallback_used'] = True
                # This would trigger another execution, but for simplicity we'll just note it
                state['final_answer'] = {
                    'success': False,
                    'content': "죄송합니다. 답변을 생성할 수 없습니다.",
                    'message': 'All tools failed'
                }
            else:
                state['final_answer'] = {
                    'success': False,
                    'content': "죄송합니다. 답변을 생성할 수 없습니다.",
                    'message': tool_result.get('message', 'Unknown error')
                }

        # Calculate total processing time
        total_time = sum(state.get('agent_execution_times', {}).values())
        state['total_processing_time'] = total_time

        logger.info(f"Answer finalized - Total time: {total_time:.0f}ms")
        return state

    # Conditional edge functions
    def _route_to_tool(self, state: QuestionState) -> str:
        """Route to the selected tool."""
        selected_tool = state.get('selected_tool', 'llm_direct')

        # Map to node names
        tool_map = {
            'vector_db': 'vector_db',
            'web_search': 'web_search',
            'llm_direct': 'llm_direct',
            'hybrid': 'hybrid'
        }

        return tool_map.get(selected_tool, 'llm_direct')

    def _should_retry(self, state: QuestionState) -> str:
        """Determine if we should retry with a different tool."""
        if state.get('can_retry', False):
            return "retry"
        else:
            return "finalize"

    def run(self, question_content: str) -> Dict[str, Any]:
        """
        Run the autonomous question answering graph.

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
            total_processing_time=None,
            # New fields for autonomous routing
            routing_decision=None,
            selected_tool=None,
            routing_confidence=None,
            routing_reasoning=None,
            tool_result=None,
            tool_used=None,
            result_satisfactory=False,
            can_retry=False,
            attempt_count=0,
            previous_attempts=[],
            fallback_tool=None,
            fallback_used=False
        )

        try:
            # Execute graph
            logger.info(f"Starting autonomous QA workflow for: {question_content[:50]}...")
            start_time = datetime.now()

            final_state = self.graph.invoke(initial_state)

            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            # Update statistics
            self._update_stats(final_state, processing_time)

            logger.info("Autonomous QA workflow completed successfully")

            # Debug logging
            final_answer = final_state.get('final_answer', {})
            logger.info(f"Final answer success status: {final_answer.get('success', False)}")
            logger.info(f"Final answer keys: {list(final_answer.keys())}")

            return {
                'success': final_answer.get('success', False),
                'answer': final_answer,
                'routing_info': {
                    'selected_tool': final_state.get('tool_used'),
                    'routing_confidence': final_state.get('routing_confidence'),
                    'routing_reasoning': final_state.get('routing_reasoning'),
                    'attempt_count': final_state.get('attempt_count', 0),
                    'reflection_used': len(final_state.get('previous_attempts', [])) > 0
                },
                'metadata': {
                    'question_id': final_state['question_id'],
                    'total_processing_time': processing_time,
                    'agent_execution_times': final_state.get('agent_execution_times'),
                    'router_model': self.router_model,
                    'reflection_enabled': self.enable_reflection
                }
            }

        except Exception as e:
            logger.error(f"Autonomous QA workflow failed: {str(e)}")
            self.stats['failed_answers'] += 1

            return {
                'success': False,
                'error': str(e),
                'answer': {
                    'content': "죄송합니다. 시스템 오류로 인해 답변을 생성할 수 없습니다.",
                    'source_type': 'error'
                }
            }

    def _update_stats(self, final_state: QuestionState, processing_time: float):
        """Update graph statistics."""
        self.stats['total_questions'] += 1

        if final_state.get('final_answer', {}).get('success'):
            self.stats['successful_answers'] += 1
        else:
            self.stats['failed_answers'] += 1

        # Update tool usage
        tool_used = final_state.get('tool_used')
        if tool_used:
            self.stats['tool_usage'][tool_used] = self.stats['tool_usage'].get(tool_used, 0) + 1

        # Update average processing time
        total = self.stats['total_questions']
        current_avg = self.stats['average_processing_time']
        self.stats['average_processing_time'] = (
            (current_avg * (total - 1) + processing_time) / total
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get graph statistics."""
        return {
            'graph_stats': self.stats.copy(),
            'router_stats': self.router.get_stats(),
            'system_info': {
                'router_model': self.router_model,
                'reflection_enabled': self.enable_reflection,
                'available_tools': list(self.tools.keys())
            }
        }

    def reset_stats(self):
        """Reset all statistics."""
        self.stats = {
            'total_questions': 0,
            'successful_answers': 0,
            'failed_answers': 0,
            'tool_usage': {
                'vector_db': 0,
                'web_search': 0,
                'llm_direct': 0,
                'hybrid': 0
            },
            'reflection_count': 0,
            'average_processing_time': 0.0
        }
        self.router.reset_stats()
        logger.info("Graph and router statistics reset")
