"""
빠른 테스트 스크립트 - 핵심 기능만 테스트
"""

import os
import logging
from src.models.question import Question
from src.services.routing_service import RoutingService

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def test_routing_only():
    """라우팅 서비스만 테스트 (데이터베이스 연결 불필요)"""
    logger.info("=== 라우팅 서비스 테스트 ===")
    
    try:
        # 라우팅 서비스 초기화
        routing_service = RoutingService()
        
        # 테스트 질문들
        test_cases = [
            ("인공지능의 정의는 무엇인가요?", "사실적 질문 - Vector DB 우선 예상"),
            ("2024년 최신 AI 트렌드는?", "최신 정보 질문 - Web Search 우선 예상"),
            ("오늘 날씨가 어때요?", "일반적 질문 - LLM Direct 우선 예상"),
            ("AI와 머신러닝의 차이점을 비교 분석해주세요.", "복합적 질문 - 다중 소스 예상"),
        ]
        
        for question_text, description in test_cases:
            logger.info(f"\n질문: {question_text}")
            logger.info(f"설명: {description}")
            
            question = Question(content=question_text)
            
            # 자동 라우팅 결정
            routing_decision = routing_service.decide_routing(question)
            
            logger.info(f"✅ 추천 소스: {[s.value for s in routing_decision.sources]}")
            logger.info(f"✅ 주요 소스: {routing_decision.primary_source.value}")
            logger.info(f"✅ 전략: {routing_decision.strategy.value}")
            logger.info(f"✅ 추론: {routing_decision.reasoning}")
            
            # 수동 라우팅 테스트
            manual_decision = routing_service.decide_routing(
                question, 
                preferred_sources=[routing_service.DataSource.LLM_DIRECT],
                strategy=routing_service.RoutingStrategy.SINGLE_SOURCE
            )
            logger.info(f"✅ 수동 라우팅 (LLM만): {manual_decision.primary_source.value}")
        
        # 통계 확인
        stats = routing_service.get_routing_stats()
        logger.info(f"\n=== 라우팅 통계 ===")
        logger.info(f"총 결정 수: {stats['routing_stats']['total_decisions']}")
        logger.info(f"자동 결정: {stats['routing_stats']['auto_decisions']}")
        logger.info(f"수동 결정: {stats['routing_stats']['manual_decisions']}")
        logger.info(f"소스 사용 현황: {stats['routing_stats']['source_usage']}")
        
        logger.info("\n🎉 라우팅 서비스 테스트 성공!")
        return True
        
    except Exception as e:
        logger.error(f"❌ 라우팅 서비스 테스트 실패: {str(e)}")
        return False


def test_database_connection_only():
    """데이터베이스 연결만 테스트"""
    logger.info("=== 데이터베이스 연결 테스트 ===")
    
    # 환경 변수 확인
    required_vars = ["ZILLIZ_HOST", "ZILLIZ_TOKEN"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.warning(f"⚠️ 환경 변수 누락: {missing_vars}")
        logger.info("데이터베이스 연결 테스트를 건너뜁니다.")
        return False
    
    try:
        from src.services.vector_store import VectorStore
        
        # Vector Store 초기화 및 연결 테스트
        vector_store = VectorStore()
        
        # 연결 상태 확인
        is_healthy = vector_store.health_check()
        logger.info(f"✅ Vector Store 연결 상태: {'성공' if is_healthy else '실패'}")
        
        if is_healthy:
            # 컬렉션 통계 확인
            stats = vector_store.get_collection_stats()
            logger.info(f"✅ 컬렉션 통계: {stats}")
        
        return is_healthy
        
    except Exception as e:
        logger.error(f"❌ 데이터베이스 연결 실패: {str(e)}")
        return False


def main():
    """메인 테스트 함수"""
    logger.info("🚀 빠른 테스트 시작")
    
    # 1. 라우팅 서비스 테스트 (항상 실행 가능)
    routing_success = test_routing_only()
    
    # 2. 데이터베이스 연결 테스트 (환경 변수 있을 때만)
    db_success = test_database_connection_only()
    
    # 결과 요약
    logger.info("\n" + "="*50)
    logger.info("테스트 결과 요약:")
    logger.info(f"  라우팅 서비스: {'✅ 성공' if routing_success else '❌ 실패'}")
    logger.info(f"  데이터베이스 연결: {'✅ 성공' if db_success else '⚠️ 건너뜀/실패'}")
    
    if routing_success:
        logger.info("\n🎉 핵심 기능이 정상 작동합니다!")
        logger.info("\n📖 사용 방법:")
        logger.info("1. 자동 라우팅:")
        logger.info("   answer_service.get_answer_with_routing(question)")
        logger.info("2. 소스 지정:")
        logger.info("   answer_service.get_answer_with_routing(question, preferred_sources=['llm_direct'])")
        logger.info("3. 라우팅 추천:")
        logger.info("   answer_service.get_routing_recommendation(question)")
        
        if not db_success:
            logger.info("\n⚠️ 데이터베이스 연결을 위해 .env 파일에 다음을 설정하세요:")
            logger.info("   ZILLIZ_HOST=your-zilliz-host")
            logger.info("   ZILLIZ_TOKEN=your-zilliz-token")
            logger.info("   OPENAI_API_KEY=your-openai-api-key")
    else:
        logger.error("\n❌ 핵심 기능에 문제가 있습니다. 코드를 확인해주세요.")


if __name__ == "__main__":
    main()
