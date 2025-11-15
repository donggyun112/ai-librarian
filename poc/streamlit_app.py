"""
Streamlit web interface for the AI Research Project - LangChain/LangGraph RAG System.
"""

import streamlit as st
import logging
import traceback
from datetime import datetime
from typing import Optional, List, Dict, Any
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

from src.models.question import Question, QuestionType
from src.models.document import DocumentChunk
from src.services.vector_store import VectorStore
from src.services.embedding_service import EmbeddingService
from src.langchain.services.langchain_answer_service import LangChainAnswerService
from src.utils.config import get_config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page config
st.set_page_config(
    page_title="AI Research Project - LangChain/LangGraph RAG System",
    page_icon="��",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        text-align: center;
        margin-bottom: 2rem;
        background: linear-gradient(90deg, #4CAF50, #2196F3);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def initialize_services():
    """Initialize all required services (cached)."""
    try:
        # Load configuration
        config = get_config()
        logger.info("Configuration loaded successfully")
        
        # Initialize embedding service
        embedding_service = EmbeddingService(
            api_key=config.openai_api_key,
            model=config.openai_embedding_model,
            max_retries=config.openai_max_retries,
            retry_delay=config.openai_retry_delay
        )
        
        # Initialize vector store
        vector_store = VectorStore(
            host=config.milvus_host,
            token=config.milvus_token,
            collection_name=config.milvus_collection_name
        )
        
        # Initialize LangChain answer service
        langchain_service = LangChainAnswerService(
            vector_store=vector_store,
            embedding_service=embedding_service,
            openai_api_key=config.openai_api_key,
            vector_db_threshold=0.7,
            web_search_threshold=0.6,
            llm_direct_threshold=0.5
        )
        
        return config, embedding_service, vector_store, langchain_service
        
    except Exception as e:
        st.error(f"서비스 초기화 실패: {e}")
        logger.error(f"Service initialization failed: {e}")
        return None, None, None, None


def create_sample_chunks() -> List[DocumentChunk]:
    """Create sample document chunks for testing."""
    sample_chunks = [
        DocumentChunk(
            id="chunk_1",
            content="LangChain은 대규모 언어 모델(LLM)을 활용한 애플리케이션 개발을 위한 프레임워크입니다. 체인, 에이전트, 메모리 등의 구성 요소를 제공합니다.",
            metadata={"source": "langchain_guide.pdf", "page": 1, "type": "definition"}
        ),
        DocumentChunk(
            id="chunk_2", 
            content="LangGraph는 LangChain의 확장으로, 복잡한 워크플로우를 그래프 형태로 구성할 수 있게 해주는 라이브러리입니다. 상태 관리와 조건부 실행을 지원합니다.",
            metadata={"source": "langgraph_tutorial.pdf", "page": 1, "type": "definition"}
        ),
        DocumentChunk(
            id="chunk_3",
            content="머신러닝은 데이터로부터 패턴을 학습하는 AI의 한 분야입니다. 지도학습, 비지도학습, 강화학습으로 구분됩니다.",
            metadata={"source": "ml_basics.pdf", "page": 3, "type": "concept"}
        ),
        DocumentChunk(
            id="chunk_4",
            content="딥러닝은 인공신경망을 사용하는 머신러닝의 하위 분야입니다. 다층 신경망을 통해 복잡한 패턴을 학습할 수 있습니다.",
            metadata={"source": "deep_learning.pdf", "page": 2, "type": "concept"}
        ),
        DocumentChunk(
            id="chunk_5",
            content="RAG(Retrieval-Augmented Generation)는 외부 지식베이스에서 관련 정보를 검색하여 LLM의 답변 생성을 보강하는 기법입니다.",
            metadata={"source": "rag_paper.pdf", "page": 1, "type": "technique"}
        )
    ]
    return sample_chunks


def display_individual_answer(source_name: str, source_data: Dict[str, Any]):
    """Display individual source answer."""
    if not source_data or not source_data.get('success', False):
        st.warning(f"❌ {source_name} 소스에서 답변을 생성하지 못했습니다.")
        return
    
    answer = source_data.get('answer')
    if answer:
        st.markdown(answer.content)
        
        # Show confidence metrics
        confidence = answer.confidence
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("관련성", f"{confidence.relevance:.2f}")
        with col2:
            st.metric("완성도", f"{confidence.completeness:.2f}")
        with col3:
            st.metric("정확도", f"{confidence.accuracy:.2f}")
        with col4:
            st.metric("신뢰도", f"{confidence.reliability:.2f}")
        
        # Show processing time
        processing_time = source_data.get('processing_time', 0)
        st.caption(f"⏱️ 처리 시간: {processing_time:.0f}ms")
        
        # Show raw result in expander
        with st.expander("🔍 원본 데이터"):
            st.json(source_data.get('raw_result', {}))


def main():
    """Main Streamlit application."""
    
    # Header
    st.markdown('<h1 class="main-header">🚀 LangChain/LangGraph RAG System</h1>', unsafe_allow_html=True)
    
    # Initialize services
    config, embedding_service, vector_store, langchain_service = initialize_services()
    
    if not all([config, embedding_service, vector_store, langchain_service]):
        st.error("⚠️ 서비스 초기화에 실패했습니다. 환경 설정을 확인해주세요.")
        return
    
    # Sidebar
    with st.sidebar:
        st.header("🔧 시스템 설정")
        
        # System status
        st.subheader("📊 시스템 상태")
        
        try:
            # Vector store stats
            stats = vector_store.get_collection_stats()
            st.metric("문서 수", stats.get('total_documents', 0))
            st.metric("벡터 차원", stats.get('dimension', 'N/A'))
            
        except Exception as e:
            st.warning(f"통계 로드 실패: {e}")
        
        # Service stats
        service_stats = langchain_service.get_service_stats()
        st.subheader("📈 서비스 통계")
        st.metric("처리된 질문", service_stats['stats']['total_questions'])
        st.metric("성공률", f"{service_stats['stats']['successful_answers'] / max(1, service_stats['stats']['total_questions']) * 100:.1f}%")
        st.metric("평균 처리시간", f"{service_stats['stats']['average_processing_time']:.0f}ms")
    
    # Main tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "🚀 질의응답", 
        "📚 데이터 관리", 
        "📊 분석", 
        "ℹ️ 시스템 정보"
    ])
    
    with tab1:
        st.header("🚀 LangChain/LangGraph 질의응답")
        
        st.info("""
        **LangChain/LangGraph 기반 지능형 질의응답 시스템**
        
        이 시스템은 질문 유형을 자동으로 분석하여 최적의 답변 소스를 선택하고, 
        필요시 여러 소스를 조합하여 포괄적인 답변을 제공합니다.
        """)
        
        # Question input
        question_input = st.text_area(
            "질문을 입력하세요:",
            placeholder="예: LangChain과 LangGraph의 차이점을 설명하고, 실제 프로젝트에서 어떻게 활용할 수 있는지 추천해주세요",
            height=120
        )
        
        # Answer options
        col_opt1, col_opt2 = st.columns(2)
        with col_opt1:
            show_all_sources = st.checkbox("🔄 모든 소스에서 답변 받기", value=False, 
                                         help="체크하면 라우팅과 관계없이 모든 소스(벡터DB, 웹검색, LLM)에서 답변을 받습니다.")
        with col_opt2:
            force_hybrid = st.checkbox("🔀 하이브리드 통합 강제", value=False,
                                     help="체크하면 가능한 모든 소스를 통합하여 하이브리드 답변을 생성합니다.")
        
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            if st.button("🚀 답변 받기", type="primary"):
                if question_input.strip():
                    with st.spinner("LangGraph 워크플로우 실행 중..."):
                        try:
                            # Create question object
                            question = Question(content=question_input.strip())
                            
                            # Get comprehensive answer with options
                            result = langchain_service.get_comprehensive_answer(
                                question, 
                                show_all_sources=show_all_sources,
                                force_hybrid=force_hybrid
                            )
                            
                            if result.get('success'):
                                    st.success("✅ 답변 생성 완료!")
                                    
                                    # Display final answer
                                    final_answer = result.get('final_answer')
                                    individual_answers = result.get('individual_answers', {})
                                    
                                    if final_answer:
                                        st.subheader("🎯 최종 통합 답변")
                                        st.markdown(final_answer.content)
                                        
                                        # Show individual source answers if available
                                        if individual_answers:
                                            st.subheader("📋 소스별 개별 답변")
                                            
                                            # Create tabs for each source
                                            source_names = list(individual_answers.keys())
                                            source_display_names = {
                                                'vector_db': '📚 벡터 DB',
                                                'web_search': '🌐 웹 검색', 
                                                'llm_direct': '🤖 LLM 직접'
                                            }
                                            
                                            if len(source_names) > 1:
                                                source_tabs = st.tabs([
                                                    source_display_names.get(name, name) 
                                                    for name in source_names
                                                ])
                                                
                                                for i, (source_name, source_data) in enumerate(individual_answers.items()):
                                                    with source_tabs[i]:
                                                        display_individual_answer(source_name, source_data)
                                            else:
                                                # Single source - display directly
                                                for source_name, source_data in individual_answers.items():
                                                    st.write(f"**{source_display_names.get(source_name, source_name)}**")
                                                    display_individual_answer(source_name, source_data)
                                    
                                    # Show routing info
                                    st.subheader("🧠 라우팅 정보")
                                    routing_info = result.get('routing_info', {})
                                    
                                    col1, col2, col3 = st.columns(3)
                                    with col1:
                                        st.metric("라우팅 전략", routing_info.get('strategy', 'N/A'))
                                    with col2:
                                        st.metric("질문 유형", str(routing_info.get('question_type', 'N/A')))
                                    with col3:
                                        st.metric("처리 시간", f"{routing_info.get('total_processing_time', 0):.0f}ms")
                                    
                                    # Show confidence scores
                                    confidences = routing_info.get('source_confidences', {})
                                    if confidences:
                                        st.subheader("📊 소스별 신뢰도")
                                        
                                        # Create confidence chart
                                        sources = list(confidences.keys())
                                        scores = [confidences[s] * 100 for s in sources]
                                        
                                        fig = go.Figure(data=[
                                            go.Bar(
                                                x=sources,
                                                y=scores,
                                                marker_color=['#4CAF50', '#2196F3', '#FF9800'][:len(sources)],
                                                text=[f"{s:.1f}%" for s in scores],
                                                textposition='auto'
                                            )
                                        ])
                                        fig.update_layout(
                                            title="소스별 신뢰도 점수",
                                            yaxis_title="신뢰도 (%)",
                                            xaxis_title="답변 소스",
                                            height=400,
                                            showlegend=False
                                        )
                                        st.plotly_chart(fig, use_container_width=True)
                                    
                                    # Show performance metrics
                                    st.subheader("⚡ 성능 지표")
                                    perf_metrics = result.get('performance_metrics', {})
                                    agent_times = perf_metrics.get('agent_times', {})
                                    
                                    if agent_times:
                                        df = pd.DataFrame([
                                            {"에이전트": k.replace('_', ' ').title(), "처리시간 (ms)": v}
                                            for k, v in agent_times.items()
                                        ])
                                        st.dataframe(df, use_container_width=True)
                                    
                                    # Show hybrid comparison if multiple sources
                                    if individual_answers and len(individual_answers) > 1:
                                        st.subheader("⚖️ 답변 비교 분석")
                                        
                                        # Create comparison table
                                        comparison_data = []
                                        for source_name, source_data in individual_answers.items():
                                            if source_data.get('success'):
                                                answer = source_data.get('answer')
                                                if answer:
                                                    comparison_data.append({
                                                        "소스": source_display_names.get(source_name, source_name),
                                                        "답변 길이": f"{len(answer.content)}자",
                                                        "신뢰도": f"{answer.confidence.overall_score():.2f}",
                                                        "처리시간": f"{source_data.get('processing_time', 0):.0f}ms",
                                                        "소스 타입": answer.primary_source.value
                                                    })
                                        
                                        if comparison_data:
                                            df = pd.DataFrame(comparison_data)
                                            st.dataframe(df, use_container_width=True)
                                            
                                            # Show integration strategy
                                            integration_strategy = final_answer.metadata.get('integration_strategy', 'N/A')
                                            st.info(f"🔄 **통합 전략**: {integration_strategy}")
                                    
                                    # Show metadata
                                    with st.expander("🔍 상세 메타데이터"):
                                        st.json(result.get('metadata', {}))
                                        
                            else:
                                st.error(f"❌ 답변 생성 실패: {result.get('error', '알 수 없는 오류')}")
                                
                        except Exception as e:
                            st.error(f"❌ 오류 발생: {str(e)}")
                            logger.error(f"LangGraph error: {e}")
                            with st.expander("오류 상세 정보"):
                                st.code(traceback.format_exc())
                else:
                    st.warning("질문을 입력해주세요.")
        
        with col2:
            if st.button("📊 서비스 통계"):
                stats = langchain_service.get_service_stats()
                st.json(stats)
        
        with col3:
            if st.button("🔄 통계 리셋"):
                langchain_service.reset_stats()
                st.success("통계가 리셋되었습니다.")
                st.rerun()
    
    with tab2:
        st.header("📚 데이터 관리")
        
        st.subheader("📄 샘플 데이터 추가")
        
        if st.button("🔄 샘플 문서 추가"):
            try:
                with st.spinner("샘플 문서를 벡터 DB에 추가하는 중..."):
                    sample_chunks = create_sample_chunks()
                    
                    # Generate embeddings and store
                    for chunk in sample_chunks:
                        embedding = embedding_service.get_embedding(chunk.content)
                        vector_store.add_document(chunk, embedding)
                    
                    st.success(f"✅ {len(sample_chunks)}개의 샘플 문서가 추가되었습니다!")
                    st.rerun()
                    
            except Exception as e:
                st.error(f"❌ 샘플 데이터 추가 실패: {e}")
        
        # Collection management
        st.subheader("🗂️ 컬렉션 관리")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📊 컬렉션 통계"):
                try:
                    stats = vector_store.get_collection_stats()
                    st.json(stats)
                except Exception as e:
                    st.error(f"통계 조회 실패: {e}")
        
        with col2:
            if st.button("🗑️ 컬렉션 초기화", type="secondary"):
                if st.session_state.get('confirm_reset'):
                    try:
                        vector_store.reset_collection()
                        st.success("컬렉션이 초기화되었습니다.")
                        st.session_state.confirm_reset = False
                        st.rerun()
                    except Exception as e:
                        st.error(f"초기화 실패: {e}")
                else:
                    st.warning("⚠️ 이 작업은 모든 데이터를 삭제합니다.")
                    if st.button("확인"):
                        st.session_state.confirm_reset = True
                        st.rerun()
    
    with tab3:
        st.header("📊 시스템 분석")
        
        # Service statistics
        st.subheader("📈 서비스 성능")
        
        try:
            stats = langchain_service.get_service_stats()
            service_stats = stats['stats']
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("총 질문 수", service_stats['total_questions'])
            with col2:
                st.metric("성공한 답변", service_stats['successful_answers'])
            with col3:
                success_rate = (service_stats['successful_answers'] / max(1, service_stats['total_questions'])) * 100
                st.metric("성공률", f"{success_rate:.1f}%")
            with col4:
                st.metric("평균 처리시간", f"{service_stats['average_processing_time']:.0f}ms")
            
            # Source usage chart
            st.subheader("📊 소스 사용 현황")
            source_usage = service_stats['source_usage']
            
            if any(source_usage.values()):
                fig = go.Figure(data=[
                    go.Pie(
                        labels=list(source_usage.keys()),
                        values=list(source_usage.values()),
                        hole=0.4
                    )
                ])
                fig.update_layout(
                    title="답변 소스별 사용 비율",
                    height=400
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("아직 처리된 질문이 없습니다.")
        
        except Exception as e:
            st.error(f"통계 로드 실패: {e}")
    
    with tab4:
        st.header("ℹ️ 시스템 정보")
        
        st.subheader("🏗️ 아키텍처")
        st.info("""
        **LangChain/LangGraph RAG 시스템 구성요소:**
        
        1. **LangChain Tools**: VectorSearchTool, WebSearchTool, LLMDirectTool
        2. **LangGraph 워크플로우**: 상태 기반 그래프 실행
        3. **벡터 저장소**: Milvus 클라우드 (Zilliz) 사용
        4. **임베딩 서비스**: OpenAI text-embedding-ada-002 모델
        5. **LLM**: OpenAI GPT-4o-mini 모델
        """)
        
        st.subheader("🚀 주요 특징")
        st.success("""
        **LangGraph 시스템의 핵심 기능:**
        
        ✅ **지능적 워크플로우**: 질문 유형에 따른 자동 라우팅  
        ✅ **상태 관리**: TypedDict 기반 상태 추적  
        ✅ **조건부 실행**: 필요한 에이전트만 선택적 실행  
        ✅ **병렬 처리**: 여러 소스 동시 조회 가능  
        ✅ **하이브리드 답변**: 다중 소스 통합 답변  
        ✅ **내장 모니터링**: 실행 추적 및 성능 분석  
        ✅ **확장성**: 새로운 노드/에이전트 쉽게 추가  
        ✅ **표준화**: 업계 표준 프레임워크 사용  
        """)
        
        st.subheader("🔧 기술 스택")
        tech_stack = {
            "프레임워크": ["LangChain", "LangGraph", "Streamlit"],
            "AI/ML": ["OpenAI GPT-4o-mini", "OpenAI Embeddings", "Milvus Vector DB"],
            "언어/라이브러리": ["Python 3.13", "Pydantic", "Poetry"],
            "시각화": ["Plotly", "Pandas"]
        }
        
        for category, technologies in tech_stack.items():
            st.write(f"**{category}**: {', '.join(technologies)}")
        
        st.subheader("📝 사용법")
        st.markdown("""
        1. **환경 설정**: `.env` 파일에 OpenAI API 키와 Milvus 정보 설정
        2. **샘플 데이터**: '📚 데이터 관리' 탭에서 샘플 문서 추가
        3. **질문 입력**: '🚀 질의응답' 탭에서 자연어 질문 작성
        4. **결과 분석**: 생성된 답변과 라우팅 정보 확인
        5. **성능 모니터링**: '📊 분석' 탭에서 시스템 성능 추적
        """)
        
        # System configuration
        with st.expander("🔧 시스템 설정 정보"):
            system_config = langchain_service.get_service_stats()
            st.json(system_config)


if __name__ == "__main__":
    main()
