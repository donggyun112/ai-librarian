"""
Streamlit web interface for the AI Research Project - PDF RAG System.
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
from src.agents.vector_search import VectorSearchAgent
from src.utils.config import get_config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page config
st.set_page_config(
    page_title="AI Research Project - PDF RAG System",
    page_icon="🤖",
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
    
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #4CAF50;
    }
    
    .success-message {
        background-color: #d4edda;
        color: #155724;
        padding: 1rem;
        border-radius: 0.5rem;
        border: 1px solid #c3e6cb;
    }
    
    .error-message {
        background-color: #f8d7da;
        color: #721c24;
        padding: 1rem;
        border-radius: 0.5rem;
        border: 1px solid #f5c6cb;
    }
    
    .info-box {
        background-color: #e3f2fd;
        color: #0d47a1;
        padding: 1rem;
        border-radius: 0.5rem;
        border: 1px solid #bbdefb;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def initialize_services():
    """Initialize all services with caching."""
    try:
        config = get_config()
        
        # Initialize services
        embedding_service = EmbeddingService(
            api_key=config.openai_api_key,
            model=config.openai_embedding_model,
            max_retries=config.openai_max_retries,
            retry_delay=config.openai_retry_delay
        )
        
        vector_store = VectorStore(
            host=config.milvus_host,
            token=config.milvus_token,
            collection_name=config.milvus_collection_name
        )
        
        search_agent = VectorSearchAgent(
            vector_store=vector_store,
            embedding_service=embedding_service,
            max_results=config.vector_search_max_results,
            min_similarity_threshold=config.vector_search_similarity_threshold,
            max_context_length=config.vector_search_max_context_length
        )
        
        # Initialize question router
        from src.agents.question_router import QuestionRouter
        question_router = QuestionRouter(
            vector_db_threshold=0.7,
            web_search_threshold=0.6,
            llm_direct_threshold=0.5
        )
        
        # Initialize web search agent
        from src.agents.web_search import WebSearchAgent
        web_search_agent = WebSearchAgent(
            max_results=5,
            search_timeout=10,
            enable_fallback=True
        )
        
        # Initialize LLM direct agent
        from src.agents.llm_direct import LLMDirectAgent
        llm_direct_agent = LLMDirectAgent(
            api_key=config.openai_api_key,
            model="gpt-4o-mini",
            max_tokens=1000,
            temperature=0.7
        )
        
        # Initialize answer service
        from src.services.answer_service import AnswerService
        answer_service = AnswerService(
            question_router=question_router,
            vector_search_agent=search_agent,
            web_search_agent=web_search_agent,
            llm_direct_agent=llm_direct_agent
        )
        
        return config, embedding_service, vector_store, search_agent, question_router, answer_service, web_search_agent, llm_direct_agent
        
    except Exception as e:
        st.error(f"서비스 초기화 실패: {e}")
        logger.error(f"Service initialization failed: {e}")
        return None, None, None, None


def create_sample_chunks() -> List[DocumentChunk]:
    """Create sample document chunks."""
    return [
        DocumentChunk(
            id="chunk_ai_1",
            document_id="ai_handbook",
            content="인공지능(AI)은 인간의 지능을 모방하는 컴퓨터 시스템의 능력입니다. "
                   "이는 학습, 추론, 문제 해결, 지각, 언어 이해 등의 인지 기능을 포함하며, "
                   "다양한 분야에서 혁신적인 변화를 이끌고 있습니다. "
                   "AI는 크게 약인공지능(Narrow AI)과 강인공지능(General AI)으로 구분됩니다.",
            page_number=1,
            chunk_index=0,
            keywords=["인공지능", "AI", "컴퓨터 시스템", "학습", "추론", "약인공지능", "강인공지능"],
            importance_score=0.9
        ),
        DocumentChunk(
            id="chunk_ml_1",
            document_id="ai_handbook",
            content="머신러닝은 인공지능의 핵심 하위 분야로, 컴퓨터가 명시적으로 프로그래밍되지 않고도 "
                   "데이터로부터 패턴을 학습하고 예측을 수행할 수 있게 합니다. "
                   "지도학습, 비지도학습, 강화학습의 세 가지 주요 유형이 있으며, "
                   "각각 다른 문제 해결 방식을 제공합니다.",
            page_number=2,
            chunk_index=1,
            keywords=["머신러닝", "데이터", "패턴", "학습", "지도학습", "비지도학습", "강화학습"],
            importance_score=0.8
        ),
        DocumentChunk(
            id="chunk_dl_1",
            document_id="ai_handbook",
            content="딥러닝은 인공 신경망을 기반으로 한 머신러닝의 한 분야입니다. "
                   "여러 층의 뉴런으로 구성된 신경망을 통해 복잡한 패턴을 자동으로 학습하며, "
                   "이미지 인식, 자연어 처리, 음성 인식 등에서 뛰어난 성능을 보입니다. "
                   "CNN, RNN, Transformer 등 다양한 아키텍처가 개발되었습니다.",
            page_number=3,
            chunk_index=2,
            keywords=["딥러닝", "신경망", "뉴런", "CNN", "RNN", "Transformer", "이미지 인식"],
            importance_score=0.85
        ),
        DocumentChunk(
            id="chunk_nlp_1",
            document_id="ai_handbook",
            content="자연어 처리(NLP)는 컴퓨터가 인간의 언어를 이해하고 생성할 수 있게 하는 AI 분야입니다. "
                   "텍스트 분석, 감정 분석, 기계 번역, 질의응답 시스템 등 다양한 응용이 있으며, "
                   "최근 GPT, BERT 같은 대규모 언어 모델의 등장으로 급속한 발전을 이루고 있습니다.",
            page_number=4,
            chunk_index=3,
            keywords=["자연어 처리", "NLP", "텍스트 분석", "기계 번역", "GPT", "BERT", "언어 모델"],
            importance_score=0.9
        ),
        DocumentChunk(
            id="chunk_cv_1",
            document_id="ai_handbook",
            content="컴퓨터 비전은 디지털 이미지나 비디오로부터 의미 있는 정보를 추출하는 AI 분야입니다. "
                   "객체 탐지, 이미지 분할, 얼굴 인식, 의료 영상 분석 등에 활용되며, "
                   "자율주행차, 보안 시스템, 의료 진단 등 실생활에 광범위하게 적용되고 있습니다.",
            page_number=5,
            chunk_index=4,
            keywords=["컴퓨터 비전", "이미지", "객체 탐지", "얼굴 인식", "자율주행", "의료 진단"],
            importance_score=0.8
        )
    ]


def main():
    """Main Streamlit application."""
    
    # Header
    st.markdown('<h1 class="main-header">🤖 AI Research Project</h1>', unsafe_allow_html=True)
    st.markdown('<h3 style="text-align: center; color: #666;">PDF RAG System - Vector Search Demo</h3>', 
               unsafe_allow_html=True)
    
    # Initialize services
    with st.spinner("서비스 초기화 중..."):
        services = initialize_services()
        if len(services) == 8:
            config, embedding_service, vector_store, search_agent, question_router, answer_service, web_search_agent, llm_direct_agent = services
        elif len(services) == 6:
            config, embedding_service, vector_store, search_agent, question_router, answer_service = services
            web_search_agent, llm_direct_agent = None, None
        else:
            # Fallback for older version
            config, embedding_service, vector_store, search_agent = services[:4]
            question_router, answer_service, web_search_agent, llm_direct_agent = None, None, None, None
    
    if not all([config, embedding_service, vector_store, search_agent]):
        st.error("서비스 초기화에 실패했습니다. 환경 변수를 확인해주세요.")
        st.stop()
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ 시스템 설정")
        
        # System health check
        st.subheader("🏥 시스템 상태")
        if st.button("헬스 체크"):
            with st.spinner("상태 확인 중..."):
                health = vector_store.health_check()
                if health:
                    st.success("✅ 벡터 DB 연결 정상")
                else:
                    st.error("❌ 벡터 DB 연결 실패")
        
        # Collection stats
        st.subheader("📊 컬렉션 통계")
        if st.button("통계 새로고침"):
            with st.spinner("통계 로딩 중..."):
                stats = vector_store.get_collection_stats()
                st.json(stats)
        
        # Configuration info
        st.subheader("🔧 설정 정보")
        with st.expander("임베딩 설정"):
            embedding_info = embedding_service.get_embedding_info()
            st.json(embedding_info)
        
        with st.expander("검색 설정"):
            search_stats = search_agent.get_search_stats()
            st.json(search_stats)
    
    # Main content
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "🔍 질의응답", 
        "🤖 통합 답변", 
        "🚀 LangGraph 답변",  # 새로운 탭
        "🧠 질문 라우터", 
        "📚 데이터 관리", 
        "📊 분석", 
        "ℹ️ 정보"
    ])
    
    with tab1:
        st.header("질의응답 시스템")
        
        # Question input
        col1, col2 = st.columns([3, 1])
        
        with col1:
            question_text = st.text_area(
                "질문을 입력하세요:",
                placeholder="예: AI와 머신러닝의 차이점은 무엇인가요?",
                height=100
            )
        
        with col2:
            st.write("질문 유형:")
            question_type = st.selectbox(
                "유형 선택",
                ["FACTUAL", "GENERAL", "COMPLEX", "CURRENT_EVENTS"],
                index=0
            )
            
            similarity_threshold = st.slider(
                "유사도 임계값",
                min_value=0.0,
                max_value=1.0,
                value=0.7,
                step=0.05
            )
        
        # Search button
        if st.button("🔍 검색 및 답변 생성", type="primary"):
            if not question_text.strip():
                st.warning("질문을 입력해주세요.")
            else:
                with st.spinner("답변 생성 중..."):
                    try:
                        # Create question object
                        question = Question(
                            id=f"q_{datetime.now().timestamp()}",
                            content=question_text,
                            question_type=QuestionType(question_type.lower()),
                            keywords=question_text.split()[:5],  # Simple keyword extraction
                            preferred_sources=["vector_db"],
                            context_needed=True,
                            language="ko"
                        )
                        
                        # Check if agent can handle the question
                        can_handle = search_agent.can_handle_question(question)
                        
                        if can_handle:
                            # Search for relevant content
                            search_agent.min_similarity_threshold = similarity_threshold
                            relevant_chunks = search_agent.search_relevant_content(question)
                            
                            # Generate answer
                            answer = search_agent.generate_answer(question)
                            
                            if answer:
                                # Display answer
                                st.success("✅ 답변이 생성되었습니다!")
                                
                                # Answer content
                                st.subheader("📝 답변")
                                st.write(answer.content)
                                
                                # Answer metrics
                                col1, col2, col3, col4 = st.columns(4)
                                with col1:
                                    st.metric("신뢰도", f"{answer.confidence_score:.2f}")
                                with col2:
                                    st.metric("처리시간", f"{answer.processing_time_ms}ms")
                                with col3:
                                    st.metric("소스 수", len(answer.sources))
                                with col4:
                                    st.metric("관련성", f"{answer.relevance_score:.2f}")
                                
                                # Source information
                                if answer.sources:
                                    st.subheader("📚 참조 소스")
                                    for i, source in enumerate(answer.sources, 1):
                                        with st.expander(f"소스 {i}: {source.title} (유사도: {source.relevance_score:.3f})"):
                                            st.write(source.snippet)
                                
                                # Search results visualization
                                if relevant_chunks:
                                    st.subheader("🔍 검색 결과")
                                    
                                    # Create DataFrame for visualization
                                    df = pd.DataFrame([
                                        {
                                            "청크 ID": chunk["chunk_id"],
                                            "유사도 점수": chunk["similarity_score"],
                                            "관련성 점수": chunk.get("search_relevance", 0),
                                            "중요도": chunk.get("importance_score", 0),
                                            "페이지": chunk.get("page_number", "?"),
                                            "미리보기": chunk.get("content_preview", "")[:100] + "..."
                                        }
                                        for chunk in relevant_chunks
                                    ])
                                    
                                    st.dataframe(df, use_container_width=True)
                                    
                                    # Similarity score chart
                                    fig = px.bar(
                                        df, 
                                        x="청크 ID", 
                                        y="유사도 점수",
                                        title="검색 결과 유사도 점수",
                                        color="유사도 점수",
                                        color_continuous_scale="viridis"
                                    )
                                    st.plotly_chart(fig, use_container_width=True)
                                
                            else:
                                st.error("답변 생성에 실패했습니다.")
                        else:
                            st.warning("이 유형의 질문은 현재 처리할 수 없습니다.")
                            
                    except Exception as e:
                        st.error(f"오류가 발생했습니다: {e}")
                        logger.error(f"Question processing error: {e}")
                        st.code(traceback.format_exc())
    
    with tab2:
        st.header("통합 답변 시스템")
        
        if answer_service and question_router and web_search_agent and llm_direct_agent:
            st.info("모든 에이전트를 활용한 통합 답변 시스템입니다. 질문을 분석하여 최적의 소스 조합으로 답변합니다.")
            
            # Service status
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("🔍 벡터 검색", "✅ 활성")
            with col2:
                st.metric("🌐 웹 검색", "✅ 활성")
            with col3:
                st.metric("🤖 LLM 직접", "✅ 활성")
            with col4:
                st.metric("🎯 라우터", "✅ 활성")
                
            # Question input
            st.subheader("💬 질문하기")
            
            integrated_question = st.text_area(
                "질문을 입력하세요:",
                placeholder="예: 2024년 최신 AI 기술과 머신러닝의 차이점은 무엇인가요?",
                height=120,
                key="integrated_question"
            )
            
            col1, col2 = st.columns([3, 1])
            
            with col1:
                use_hybrid = st.checkbox("하이브리드 답변 강제 사용", help="여러 소스를 강제로 조합하여 답변합니다")
            
            with col2:
                if st.button("🚀 통합 답변 생성", type="primary", key="integrated_answer"):
                    if integrated_question.strip():
                        with st.spinner("통합 답변 생성 중..."):
                            try:
                                from src.models.question import Question, QuestionType
                                
                                # Create question
                                question = Question(
                                    id=f"integrated_{datetime.now().timestamp()}",
                                    content=integrated_question,
                                    question_type=QuestionType.UNKNOWN,
                                    language="ko"
                                )
                                
                                # Get integrated answer
                                answer = answer_service.get_answer(question)
                                
                                if answer:
                                    st.success("✅ 통합 답변이 생성되었습니다!")
                                    
                                    # Display answer
                                    st.subheader("📋 답변")
                                    st.markdown(answer.content)
                                    
                                    # Answer metadata
                                    st.subheader("📊 답변 정보")
                                    
                                    col1, col2, col3 = st.columns(3)
                                    
                                    with col1:
                                        st.metric("신뢰도", f"{answer.confidence_score:.2f}")
                                        st.metric("관련성", f"{answer.relevance_score:.2f}")
                                        
                                    with col2:
                                        st.metric("완성도", f"{answer.completeness_score:.2f}")
                                        st.metric("정확도", f"{answer.accuracy_score:.2f}")
                                        
                                    with col3:
                                        st.metric("처리 시간", f"{answer.processing_time_ms}ms")
                                        st.metric("토큰 사용", f"{int(answer.tokens_used)}")
                                    
                                    # Source information
                                    if answer.sources:
                                        st.subheader("📚 출처 정보")
                                        
                                        for i, source in enumerate(answer.sources[:5], 1):
                                            with st.expander(f"📎 출처 {i}: {source.title}"):
                                                st.write(f"**유형:** {source.source_type}")
                                                st.write(f"**관련성:** {source.relevance_score:.2f}")
                                                if source.url:
                                                    st.write(f"**링크:** {source.url}")
                                                if source.excerpt:
                                                    st.write(f"**내용:** {source.excerpt}")
                                    
                                    # Routing information
                                    if 'routing_strategy' in answer.metadata:
                                        st.subheader("🎯 라우팅 정보")
                                        
                                        col1, col2 = st.columns(2)
                                        
                                        with col1:
                                            st.write(f"**전략:** {answer.metadata['routing_strategy']}")
                                            st.write(f"**소스 수:** {answer.metadata.get('sources_attempted', 'N/A')}")
                                            st.write(f"**하이브리드:** {'예' if answer.metadata.get('hybrid_approach', False) else '아니오'}")
                                            
                                        with col2:
                                            if 'source_confidences' in answer.metadata:
                                                confidences = answer.metadata['source_confidences']
                                                
                                                import plotly.graph_objects as go
                                                
                                                fig = go.Figure(data=[
                                                    go.Bar(
                                                        x=list(confidences.keys()),
                                                        y=list(confidences.values()),
                                                        marker_color=['#1f77b4', '#ff7f0e', '#2ca02c']
                                                    )
                                                ])
                                                
                                                fig.update_layout(
                                                    title="소스별 신뢰도",
                                                    xaxis_title="소스",
                                                    yaxis_title="신뢰도",
                                                    height=300,
                                                    yaxis=dict(range=[0, 1])
                                                )
                                                
                                                st.plotly_chart(fig, use_container_width=True)
                                    
                                    # Tags
                                    if hasattr(answer, 'tags') and answer.tags:
                                        st.subheader("🏷️ 태그")
                                        tag_cols = st.columns(min(len(answer.tags), 4))
                                        for i, tag in enumerate(answer.tags):
                                            with tag_cols[i % 4]:
                                                st.badge(tag)
                                                
                                else:
                                    st.error("답변 생성에 실패했습니다.")
                                    
                            except Exception as e:
                                st.error(f"오류가 발생했습니다: {e}")
                                st.code(traceback.format_exc())
                    else:
                        st.warning("질문을 입력해주세요.")
                        
            # Service statistics
            st.subheader("📊 서비스 통계")
            
            try:
                service_stats = answer_service.get_service_stats()
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**사용 가능한 에이전트:**")
                    for agent in service_stats['available_agents']:
                        st.write(f"• {agent}")
                        
                with col2:
                    st.write("**지원 기능:**")
                    st.write(f"• 라우팅 활성화: {'예' if service_stats['routing_enabled'] else '아니오'}")
                    st.write(f"• 하이브리드 지원: {'예' if service_stats['hybrid_support'] else '아니오'}")
                    
            except Exception as e:
                st.error(f"서비스 통계 로드 실패: {e}")
                
        else:
            st.warning("통합 답변 서비스가 완전히 초기화되지 않았습니다.")
            missing_components = []
            if not answer_service:
                missing_components.append("Answer Service")
            if not question_router:
                missing_components.append("Question Router")
            if not web_search_agent:
                missing_components.append("Web Search Agent")
            if not llm_direct_agent:
                missing_components.append("LLM Direct Agent")
                
            st.error(f"누락된 구성요소: {', '.join(missing_components)}")
    
    with tab3:
        st.header("질문 라우터 테스트")
        
        if question_router:
            st.info("질문 라우터가 질문을 분석하고 최적의 답변 소스를 결정합니다.")
            
            # Router configuration
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("🔧 라우터 설정")
                router_stats = question_router.get_routing_stats()
                
                st.write("**임계값:**")
                for source, threshold in router_stats['thresholds'].items():
                    st.write(f"- {source}: {threshold}")
                    
                st.write("**패턴 수:**")
                for category, count in router_stats['pattern_counts'].items():
                    st.write(f"- {category}: {count}개")
                    
            with col2:
                st.subheader("🎯 지원 기능")
                st.write("**질문 유형:**")
                for qtype in router_stats['supported_question_types']:
                    st.write(f"- {qtype}")
                    
                st.write("**라우팅 전략:**")
                for strategy in router_stats['routing_strategies']:
                    st.write(f"- {strategy}")
            
            # Question analysis
            st.subheader("🧪 질문 분석 테스트")
            
            test_question = st.text_area(
                "분석할 질문을 입력하세요:",
                placeholder="예: AI와 머신러닝의 차이점은 무엇인가요?",
                height=100
            )
            
            if st.button("🔍 질문 분석 및 라우팅", type="primary"):
                if test_question.strip():
                    with st.spinner("질문 분석 중..."):
                        try:
                            from src.models.question import Question, QuestionType
                            
                            # Create question object
                            question = Question(
                                id=f"test_{datetime.now().timestamp()}",
                                content=test_question,
                                question_type=QuestionType.UNKNOWN,
                                language="ko"
                            )
                            
                            # Analyze question
                            analyzed_question = question_router.analyze_question(question)
                            
                            # Route question
                            routing_result = question_router.route_question(analyzed_question)
                            
                            # Display results
                            st.success("✅ 질문 분석 완료!")
                            
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.subheader("📋 질문 분석 결과")
                                st.write(f"**유형:** {analyzed_question.question_type.value}")
                                st.write(f"**복잡도:** {analyzed_question.complexity_score:.2f}")
                                st.write(f"**컨텍스트 필요:** {analyzed_question.context_needed}")
                                st.write(f"**키워드:** {', '.join(analyzed_question.keywords[:5])}")
                                
                            with col2:
                                st.subheader("🎯 라우팅 결과")
                                st.write(f"**전략:** {routing_result['routing_strategy']}")
                                st.write(f"**추천 소스:** {', '.join(routing_result['recommended_sources'])}")
                                st.write(f"**하이브리드 필요:** {routing_result['requires_hybrid']}")
                                st.write(f"**처리 우선순위:** {routing_result['processing_priority']}")
                                st.write(f"**예상 처리시간:** {routing_result['estimated_processing_time']}ms")
                            
                            # Confidence scores chart
                            st.subheader("📈 소스별 신뢰도")
                            confidences = routing_result['source_confidences']
                            
                            import plotly.graph_objects as go
                            
                            fig = go.Figure(data=[
                                go.Bar(
                                    x=list(confidences.keys()),
                                    y=list(confidences.values()),
                                    marker_color=['#1f77b4', '#ff7f0e', '#2ca02c']
                                )
                            ])
                            
                            fig.update_layout(
                                title="소스별 신뢰도 점수",
                                xaxis_title="답변 소스",
                                yaxis_title="신뢰도 점수",
                                yaxis=dict(range=[0, 1])
                            )
                            
                            st.plotly_chart(fig, use_container_width=True)
                            
                            # Routing explanation
                            st.subheader("💡 라우팅 설명")
                            if routing_result['routing_strategy'] == 'vector_db_only':
                                st.info("📚 이 질문은 문서 기반 답변이 가장 적합합니다. 벡터 DB에서 관련 정보를 검색합니다.")
                            elif routing_result['routing_strategy'] == 'web_search_only':
                                st.info("🌐 이 질문은 최신 정보가 필요합니다. 웹 검색을 통해 답변합니다.")
                            elif routing_result['routing_strategy'] == 'llm_direct_only':
                                st.info("🤖 이 질문은 일반적인 지식으로 답변 가능합니다. LLM이 직접 답변합니다.")
                            elif 'hybrid' in routing_result['routing_strategy']:
                                st.info("🔄 이 질문은 복합적입니다. 여러 소스를 조합하여 답변합니다.")
                                
                        except Exception as e:
                            st.error(f"질문 분석 중 오류: {e}")
                            st.code(traceback.format_exc())
                else:
                    st.warning("질문을 입력해주세요.")
                    
            # Pre-defined test cases
            st.subheader("🧪 미리 정의된 테스트 케이스")
            
            test_cases = {
                "사실적 질문": "AI와 머신러닝의 차이점은 무엇인가요?",
                "최신 정보 질문": "2024년 최신 AI 기술 동향은 어떻게 되나요?",
                "일반적 질문": "프로그래밍을 배우려면 어떻게 시작하는 것이 좋을까요?",
                "복합적 질문": "머신러닝과 딥러닝의 차이점을 설명하고, 각각의 장단점을 비교해주세요."
            }
            
            selected_case = st.selectbox("테스트 케이스 선택:", list(test_cases.keys()))
            
            if st.button("선택한 케이스 분석"):
                st.text_area("선택된 질문:", test_cases[selected_case], height=100, disabled=True)
                # Trigger analysis with selected case
                test_question = test_cases[selected_case]
                st.rerun()
        else:
            st.warning("질문 라우터가 초기화되지 않았습니다.")
            st.info("서비스를 다시 시작해주세요.")
    
    with tab4:
        st.header("데이터 관리")
        
        # Sample data management
        st.subheader("📝 샘플 데이터")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("샘플 데이터 추가"):
                with st.spinner("샘플 데이터 생성 및 임베딩 중..."):
                    try:
                        # Create sample chunks
                        sample_chunks = create_sample_chunks()
                        
                        # Update word counts
                        for chunk in sample_chunks:
                            chunk.update_counts()
                        
                        # Generate embeddings
                        chunks_with_embeddings = embedding_service.embed_document_chunks(sample_chunks)
                        
                        if chunks_with_embeddings:
                            # Insert into vector store
                            success = vector_store.insert_document_chunks(chunks_with_embeddings)
                            
                            if success:
                                st.success(f"✅ {len(chunks_with_embeddings)}개의 샘플 청크가 추가되었습니다!")
                            else:
                                st.error("❌ 벡터 저장소 삽입 실패")
                        else:
                            st.error("❌ 임베딩 생성 실패")
                            
                    except Exception as e:
                        st.error(f"샘플 데이터 추가 실패: {e}")
                        logger.error(f"Sample data insertion error: {e}")
        
        with col2:
            if st.button("문서 데이터 삭제"):
                document_id = st.text_input("삭제할 문서 ID:", "ai_handbook")
                if st.button("삭제 실행", type="secondary"):
                    with st.spinner("데이터 삭제 중..."):
                        try:
                            success = vector_store.delete_document_chunks(document_id)
                            if success:
                                st.success(f"✅ 문서 '{document_id}'의 청크들이 삭제되었습니다!")
                            else:
                                st.error("❌ 데이터 삭제 실패")
                        except Exception as e:
                            st.error(f"삭제 실패: {e}")
        
        # Document chunks viewer
        st.subheader("📄 문서 청크 조회")
        doc_id_input = st.text_input("문서 ID 입력:", "ai_handbook")
        
        if st.button("청크 조회"):
            with st.spinner("청크 조회 중..."):
                try:
                    chunks = vector_store.get_document_chunks(doc_id_input)
                    
                    if chunks:
                        st.success(f"✅ {len(chunks)}개의 청크를 찾았습니다!")
                        
                        for i, chunk in enumerate(chunks, 1):
                            with st.expander(f"청크 {i}: {chunk['chunk_id']} (페이지 {chunk.get('page_number', '?')})"):
                                st.write("**내용:**")
                                st.write(chunk["content"])
                                st.write("**키워드:**", ", ".join(chunk.get("keywords", [])))
                                st.write("**중요도:**", chunk.get("importance_score", 0))
                    else:
                        st.warning("해당 문서의 청크를 찾을 수 없습니다.")
                        
                except Exception as e:
                    st.error(f"청크 조회 실패: {e}")
    
    with tab5:
        st.header("📚 데이터 관리")
        
    with tab6:
        st.header("📊 분석 및 통계")
        
        # Collection statistics
        st.subheader("📊 컬렉션 통계")
        
        try:
            stats = vector_store.get_collection_stats()
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("총 엔티티 수", stats.get("total_entities", 0))
            with col2:
                st.metric("인덱스 상태", stats.get("index_status", "unknown"))
            with col3:
                st.metric("컬렉션명", stats.get("collection_name", ""))
            
        except Exception as e:
            st.error(f"통계 조회 실패: {e}")
        
        # Cost estimation
        st.subheader("💰 비용 추정")
        
        col1, col2 = st.columns(2)
        with col1:
            text_count = st.number_input("텍스트 수", min_value=1, value=100)
        with col2:
            avg_tokens = st.number_input("평균 토큰 수", min_value=1, value=100)
        
        if st.button("비용 계산"):
            cost_info = embedding_service.estimate_cost(text_count, avg_tokens)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("총 토큰 수", f"{cost_info['estimated_total_tokens']:,}")
            with col2:
                st.metric("예상 비용 (USD)", f"${cost_info['estimated_cost_usd']:.6f}")
            with col3:
                st.metric("모델", cost_info['model'])
    
    with tab7:
        st.header("ℹ️ 시스템 정보")
        
        st.subheader("🏗️ 아키텍처")
        st.info("""
        **PDF RAG 시스템 구성요소:**
        
        1. **임베딩 서비스**: OpenAI text-embedding-ada-002 모델 사용
        2. **벡터 저장소**: Milvus 클라우드 (Zilliz) 사용
        3. **검색 에이전트**: 시멘틱 유사도 기반 검색
        4. **질문 처리**: 다양한 질문 유형 지원
        5. **답변 생성**: 구조화된 답변 및 출처 정보 제공
        """)
        
        st.subheader("🔧 기능")
        st.success("""
        **현재 구현된 기능:**
        
        ✅ 벡터 DB 연결 및 관리  
        ✅ 문서 청크 임베딩 및 저장  
        ✅ 시멘틱 유사도 검색  
        ✅ 질문 유형별 처리  
        ✅ 답변 생성 및 신뢰도 평가  
        ✅ 소스 참조 및 메타데이터  
        ✅ 웹 인터페이스 제공
        ✅ LangChain/LangGraph 기반 시스템  
        """)
        
        st.subheader("🚀 LangGraph 시스템 특징")
        st.success("""
        **새로 추가된 LangGraph 기능:**
        
        ✅ 지능적 워크플로우 기반 라우팅  
        ✅ 상태 기반 그래프 실행  
        ✅ 조건부 노드 실행  
        ✅ 내장 추적 및 모니터링  
        ✅ 표준화된 에이전트 인터페이스  
        ✅ 확장 가능한 아키텍처  
        """)
        
        st.subheader("📝 사용법")
        st.markdown("""
        1. **환경 변수 설정**: `.env` 파일에 OpenAI API 키와 Milvus 정보 설정
        2. **질문 입력**: 자연어로 질문 작성
        3. **시스템 선택**: 기존 시스템 또는 LangGraph 시스템 선택
        4. **답변 확인**: 생성된 답변과 메타데이터 검토
        5. **성능 분석**: 처리 시간 및 신뢰도 분석
        """)
    
    with tab3:
        st.header("🚀 LangGraph 기반 질의응답")
        
        st.info("""
        **새로운 LangChain/LangGraph 기반 시스템**
        
        이 탭에서는 LangChain과 LangGraph를 사용한 새로운 질의응답 시스템을 테스트할 수 있습니다.
        기존 시스템과 비교하여 더 지능적인 라우팅과 통합된 답변을 제공합니다.
        """)
        
        # Initialize LangChain service (cached)
        @st.cache_resource
        def get_langchain_service():
            try:
                from src.langchain.services.langchain_answer_service import LangChainAnswerService
                return LangChainAnswerService(
                    vector_store=vector_store,
                    openai_api_key=config.openai_api_key,
                    vector_db_threshold=0.7,
                    web_search_threshold=0.6,
                    llm_direct_threshold=0.5
                )
            except Exception as e:
                st.error(f"LangChain 서비스 초기화 실패: {e}")
                return None
        
        langchain_service = get_langchain_service()
        
        if langchain_service:
            # Question input
            question_input = st.text_area(
                "질문을 입력하세요:",
                placeholder="예: 2024년 최신 AI 기술과 머신러닝의 차이점을 설명하고 활용사례를 추천해주세요",
                height=100,
                key="langchain_question"
            )
            
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                if st.button("🚀 LangGraph로 답변 받기", type="primary", key="langchain_submit"):
                    if question_input.strip():
                        with st.spinner("LangGraph 워크플로우 실행 중..."):
                            try:
                                # Create question object
                                question = Question(content=question_input.strip())
                                
                                # Get comprehensive answer
                                result = langchain_service.get_comprehensive_answer(question)
                                
                                if result.get('success'):
                                    st.success("✅ LangGraph 답변 완료!")
                                    
                                    # Display answer
                                    answer = result.get('answer')
                                    if answer:
                                        st.subheader("📝 답변")
                                        st.markdown(answer.content)
                                        
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
                                                    marker_color=['#4CAF50', '#2196F3', '#FF9800'][:len(sources)]
                                                )
                                            ])
                                            fig.update_layout(
                                                title="소스별 신뢰도 점수",
                                                yaxis_title="신뢰도 (%)",
                                                xaxis_title="답변 소스",
                                                height=400
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
                                        
                                        # Show metadata
                                        with st.expander("🔍 상세 메타데이터"):
                                            st.json(result.get('metadata', {}))
                                            
                                else:
                                    st.error(f"❌ 답변 생성 실패: {result.get('error', '알 수 없는 오류')}")
                                    
                            except Exception as e:
                                st.error(f"❌ 오류 발생: {str(e)}")
                                logger.error(f"LangGraph error: {e}")
                                st.code(traceback.format_exc())
                    else:
                        st.warning("질문을 입력해주세요.")
            
            with col2:
                if st.button("📊 서비스 통계", key="langchain_stats"):
                    stats = langchain_service.get_service_stats()
                    st.json(stats)
            
            with col3:
                if st.button("🔄 통계 리셋", key="langchain_reset"):
                    langchain_service.reset_stats()
                    st.success("통계가 리셋되었습니다.")
            
            # System comparison section
            st.subheader("⚖️ 시스템 비교")
            
            with st.expander("기존 시스템 vs LangGraph 시스템"):
                comparison_df = pd.DataFrame({
                    "특징": [
                        "아키텍처", 
                        "라우팅", 
                        "상태 관리", 
                        "확장성", 
                        "디버깅", 
                        "표준화"
                    ],
                    "기존 시스템": [
                        "커스텀 Python 클래스",
                        "수동 패턴 매칭",
                        "딕셔너리 기반",
                        "제한적",
                        "수동 로깅",
                        "커스텀 구현"
                    ],
                    "LangGraph 시스템": [
                        "LangChain/LangGraph",
                        "지능적 워크플로우",
                        "TypedDict 상태 관리",
                        "높음 (노드 추가 용이)",
                        "내장 추적 및 모니터링",
                        "업계 표준 프레임워크"
                    ]
                })
                st.dataframe(comparison_df, use_container_width=True)
        
        else:
            st.error("LangChain 서비스를 초기화할 수 없습니다. 환경 설정을 확인해주세요.")
    
    with tab4:
        st.header("질문 라우터")
        
        st.subheader("🏗️ 아키텍처")
        st.info("""
        **PDF RAG 시스템 구성요소:**
        
        1. **임베딩 서비스**: OpenAI text-embedding-ada-002 모델 사용
        2. **벡터 저장소**: Milvus 클라우드 (Zilliz) 사용
        3. **검색 에이전트**: 시멘틱 유사도 기반 검색
        4. **질문 처리**: 다양한 질문 유형 지원
        5. **답변 생성**: 구조화된 답변 및 출처 정보 제공
        """)
        
        st.subheader("🔧 기능")
        st.success("""
        **현재 구현된 기능:**
        
        ✅ 벡터 DB 연결 및 관리  
        ✅ 문서 청크 임베딩 및 저장  
        ✅ 시멘틱 유사도 검색  
        ✅ 질문 유형별 처리  
        ✅ 답변 생성 및 신뢰도 평가  
        ✅ 소스 참조 및 메타데이터  
        ✅ 웹 인터페이스 제공  
        """)
        
        st.subheader("🚀 향후 계획")
        st.warning("""
        **구현 예정 기능:**
        
        🔄 질문 라우터 (다중 소스 결정)  
        🔄 웹 검색 연동  
        🔄 LLM 직접 답변  
        🔄 답변 통합 서비스  
        🔄 사용자 피드백 시스템  
        """)
        
        st.subheader("📝 사용법")
        st.markdown("""
        1. **환경 변수 설정**: `.env` 파일에 OpenAI API 키와 Milvus 정보 설정
        2. **샘플 데이터 추가**: '데이터 관리' 탭에서 샘플 데이터 추가
        3. **질문 입력**: '질의응답' 탭에서 질문 입력 및 검색
        4. **결과 확인**: 답변, 유사도 점수, 참조 소스 확인
        """)


if __name__ == "__main__":
    main()