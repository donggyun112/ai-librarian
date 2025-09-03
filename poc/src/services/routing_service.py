"""
라우팅 결정 서비스 - 질문 분석 및 데이터소스 선택을 위한 서비스
"""

from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
import logging
from datetime import datetime

from ..models.question import Question, QuestionType

logger = logging.getLogger(__name__)


class DataSource(str, Enum):
    """사용 가능한 데이터소스 타입."""
    
    VECTOR_DB = "vector_db"
    WEB_SEARCH = "web_search"
    LLM_DIRECT = "llm_direct"


class RoutingStrategy(str, Enum):
    """라우팅 전략 타입."""
    
    SINGLE_SOURCE = "single_source"      # 단일 소스만 사용
    HYBRID = "hybrid"                    # 다중 소스 결합
    SEQUENTIAL = "sequential"            # 순차적 실행
    PARALLEL = "parallel"                # 병렬 실행


class RoutingDecision:
    """라우팅 결정 결과."""
    
    def __init__(self,
                 primary_source: DataSource,
                 strategy: RoutingStrategy,
                 sources: List[DataSource],
                 confidence_scores: Dict[str, float],
                 reasoning: str):
        self.primary_source = primary_source
        self.strategy = strategy
        self.sources = sources
        self.confidence_scores = confidence_scores
        self.reasoning = reasoning
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환."""
        return {
            "primary_source": self.primary_source.value,
            "strategy": self.strategy.value,
            "sources": [source.value for source in self.sources],
            "confidence_scores": self.confidence_scores,
            "reasoning": self.reasoning,
            "timestamp": self.timestamp.isoformat()
        }


class RoutingService:
    """
    질문 분석 및 데이터소스 라우팅 결정 서비스.
    
    사용자가 직접 라우팅을 지정하거나, 자동 분석을 통해 최적의 데이터소스를 선택할 수 있습니다.
    """
    
    def __init__(self,
                 vector_db_threshold: float = 0.7,
                 web_search_threshold: float = 0.6,
                 llm_direct_threshold: float = 0.5):
        """
        라우팅 서비스 초기화.
        
        Args:
            vector_db_threshold: Vector DB 사용 임계값
            web_search_threshold: Web Search 사용 임계값
            llm_direct_threshold: LLM Direct 사용 임계값
        """
        self.thresholds = {
            DataSource.VECTOR_DB: vector_db_threshold,
            DataSource.WEB_SEARCH: web_search_threshold,
            DataSource.LLM_DIRECT: llm_direct_threshold
        }
        
        # 통계 추적
        self.routing_stats = {
            "total_decisions": 0,
            "manual_decisions": 0,
            "auto_decisions": 0,
            "source_usage": {
                DataSource.VECTOR_DB: 0,
                DataSource.WEB_SEARCH: 0,
                DataSource.LLM_DIRECT: 0
            }
        }
    
    def decide_routing(self, 
                      question: Question,
                      preferred_sources: Optional[List[DataSource]] = None,
                      strategy: Optional[RoutingStrategy] = None) -> RoutingDecision:
        """
        라우팅 결정을 수행합니다.
        
        Args:
            question: 분석할 질문
            preferred_sources: 사용자가 선호하는 데이터소스 (선택사항)
            strategy: 사용자가 지정한 전략 (선택사항)
            
        Returns:
            RoutingDecision: 라우팅 결정 결과
        """
        logger.info(f"Deciding routing for question: {question.content[:50]}...")
        
        self.routing_stats["total_decisions"] += 1
        
        # 사용자가 직접 지정한 경우
        if preferred_sources:
            return self._manual_routing(question, preferred_sources, strategy)
        
        # 자동 분석을 통한 라우팅
        return self._auto_routing(question)
    
    def _manual_routing(self, 
                       question: Question,
                       preferred_sources: List[DataSource],
                       strategy: Optional[RoutingStrategy] = None) -> RoutingDecision:
        """사용자가 직접 지정한 라우팅."""
        
        self.routing_stats["manual_decisions"] += 1
        
        # 전략 결정
        if not strategy:
            strategy = RoutingStrategy.SINGLE_SOURCE if len(preferred_sources) == 1 else RoutingStrategy.HYBRID
        
        # 주요 소스 결정 (첫 번째 소스를 주요 소스로)
        primary_source = preferred_sources[0]
        
        # 신뢰도 점수 (사용자 지정이므로 높게 설정)
        confidence_scores = {source.value: 0.9 for source in preferred_sources}
        
        # 통계 업데이트
        for source in preferred_sources:
            self.routing_stats["source_usage"][source] += 1
        
        reasoning = f"사용자가 직접 지정한 데이터소스: {', '.join([s.value for s in preferred_sources])}"
        
        logger.info(f"Manual routing decision: {primary_source.value} with strategy {strategy.value}")
        
        return RoutingDecision(
            primary_source=primary_source,
            strategy=strategy,
            sources=preferred_sources,
            confidence_scores=confidence_scores,
            reasoning=reasoning
        )
    
    def _auto_routing(self, question: Question) -> RoutingDecision:
        """자동 분석을 통한 라우팅."""
        
        self.routing_stats["auto_decisions"] += 1
        
        # 질문 분석
        analysis = self._analyze_question(question)
        
        # 각 소스별 신뢰도 계산
        confidence_scores = {
            DataSource.VECTOR_DB.value: self._calculate_vector_db_confidence(analysis),
            DataSource.WEB_SEARCH.value: self._calculate_web_search_confidence(analysis),
            DataSource.LLM_DIRECT.value: self._calculate_llm_direct_confidence(analysis)
        }
        
        # 임계값을 넘는 소스들 선택
        recommended_sources = []
        for source, threshold in self.thresholds.items():
            if confidence_scores[source.value] >= threshold:
                recommended_sources.append(source)
        
        # 추천 소스가 없으면 LLM Direct를 기본으로
        if not recommended_sources:
            recommended_sources = [DataSource.LLM_DIRECT]
            confidence_scores[DataSource.LLM_DIRECT.value] = 0.6
        
        # 주요 소스 결정 (가장 높은 신뢰도)
        primary_source = max(recommended_sources, 
                           key=lambda s: confidence_scores[s.value])
        
        # 전략 결정
        strategy = RoutingStrategy.SINGLE_SOURCE if len(recommended_sources) == 1 else RoutingStrategy.HYBRID
        
        # 통계 업데이트
        for source in recommended_sources:
            self.routing_stats["source_usage"][source] += 1
        
        # 추론 근거 생성
        reasoning = self._generate_reasoning(analysis, confidence_scores, recommended_sources)
        
        logger.info(f"Auto routing decision: {primary_source.value} with {len(recommended_sources)} sources")
        
        return RoutingDecision(
            primary_source=primary_source,
            strategy=strategy,
            sources=recommended_sources,
            confidence_scores=confidence_scores,
            reasoning=reasoning
        )
    
    def _analyze_question(self, question: Question) -> Dict[str, Any]:
        """질문 분석."""
        
        content = question.content.lower()
        
        # 키워드 분석
        factual_keywords = ['정의', '의미', '설명', '차이', 'what is', 'explain', 'define']
        current_keywords = ['최근', '최신', '2024', '현재', 'latest', 'recent', 'current', '오늘', 'today']
        complex_keywords = ['비교', '분석', '평가', 'compare', 'analyze', 'evaluate']
        
        # 질문 유형 분류
        question_type = question.question_type
        if question_type == QuestionType.UNKNOWN:
            if any(keyword in content for keyword in current_keywords):
                question_type = QuestionType.CURRENT_EVENTS
            elif any(keyword in content for keyword in factual_keywords):
                question_type = QuestionType.FACTUAL
            elif any(keyword in content for keyword in complex_keywords) or len(content.split()) > 20:
                question_type = QuestionType.COMPLEX
            else:
                question_type = QuestionType.GENERAL
        
        # 복잡도 계산
        complexity_score = min(1.0, len(content.split()) / 30.0)
        
        # 실시간 정보 필요성
        needs_realtime = any(keyword in content for keyword in current_keywords)
        
        # 문맥 정보 필요성
        needs_context = any(keyword in content for keyword in factual_keywords + complex_keywords)
        
        return {
            'question_type': question_type,
            'complexity_score': complexity_score,
            'needs_realtime': needs_realtime,
            'needs_context': needs_context,
            'word_count': len(content.split()),
            'has_factual_keywords': any(keyword in content for keyword in factual_keywords),
            'has_current_keywords': any(keyword in content for keyword in current_keywords),
            'has_complex_keywords': any(keyword in content for keyword in complex_keywords)
        }
    
    def _calculate_vector_db_confidence(self, analysis: Dict[str, Any]) -> float:
        """Vector DB 신뢰도 계산."""
        
        base_confidence = {
            QuestionType.FACTUAL: 0.9,
            QuestionType.COMPLEX: 0.7,
            QuestionType.GENERAL: 0.4,
            QuestionType.CURRENT_EVENTS: 0.2
        }.get(analysis['question_type'], 0.3)
        
        # 문맥 정보가 필요한 경우 가산점
        if analysis['needs_context']:
            base_confidence += 0.2
        
        # 실시간 정보가 필요한 경우 감점
        if analysis['needs_realtime']:
            base_confidence -= 0.3
        
        return max(0.0, min(1.0, base_confidence))
    
    def _calculate_web_search_confidence(self, analysis: Dict[str, Any]) -> float:
        """Web Search 신뢰도 계산."""
        
        base_confidence = {
            QuestionType.CURRENT_EVENTS: 0.9,
            QuestionType.GENERAL: 0.3,
            QuestionType.COMPLEX: 0.2,
            QuestionType.FACTUAL: 0.1
        }.get(analysis['question_type'], 0.2)
        
        # 실시간 정보가 필요한 경우 가산점
        if analysis['needs_realtime']:
            base_confidence += 0.4
        
        return max(0.0, min(1.0, base_confidence))
    
    def _calculate_llm_direct_confidence(self, analysis: Dict[str, Any]) -> float:
        """LLM Direct 신뢰도 계산."""
        
        base_confidence = {
            QuestionType.GENERAL: 0.8,
            QuestionType.COMPLEX: 0.5,
            QuestionType.FACTUAL: 0.3,
            QuestionType.CURRENT_EVENTS: 0.2
        }.get(analysis['question_type'], 0.4)
        
        # 복잡도에 따른 조정
        if analysis['complexity_score'] > 0.7:
            base_confidence += 0.2
        
        return max(0.0, min(1.0, base_confidence))
    
    def _generate_reasoning(self, 
                          analysis: Dict[str, Any],
                          confidence_scores: Dict[str, float],
                          recommended_sources: List[DataSource]) -> str:
        """추론 근거 생성."""
        
        reasoning_parts = []
        
        # 질문 유형 기반 추론
        question_type = analysis['question_type']
        if question_type == QuestionType.FACTUAL:
            reasoning_parts.append("사실적 질문으로 문서 검색이 유용함")
        elif question_type == QuestionType.CURRENT_EVENTS:
            reasoning_parts.append("최신 정보가 필요하여 웹 검색이 적합함")
        elif question_type == QuestionType.COMPLEX:
            reasoning_parts.append("복합적 질문으로 다중 소스 활용이 필요함")
        else:
            reasoning_parts.append("일반적 질문으로 LLM 직접 답변이 적합함")
        
        # 특성 기반 추론
        if analysis['needs_realtime']:
            reasoning_parts.append("실시간 정보 필요")
        if analysis['needs_context']:
            reasoning_parts.append("문맥 정보 필요")
        
        # 신뢰도 점수 정보
        max_confidence = max(confidence_scores.values())
        best_source = max(confidence_scores.items(), key=lambda x: x[1])[0]
        reasoning_parts.append(f"최고 신뢰도: {best_source} ({max_confidence:.2f})")
        
        return "; ".join(reasoning_parts)
    
    def get_routing_stats(self) -> Dict[str, Any]:
        """라우팅 통계 반환."""
        return {
            "routing_stats": self.routing_stats.copy(),
            "thresholds": {k.value: v for k, v in self.thresholds.items()},
            "available_sources": [source.value for source in DataSource],
            "available_strategies": [strategy.value for strategy in RoutingStrategy]
        }
    
    def reset_stats(self) -> None:
        """통계 초기화."""
        self.routing_stats = {
            "total_decisions": 0,
            "manual_decisions": 0,
            "auto_decisions": 0,
            "source_usage": {
                DataSource.VECTOR_DB: 0,
                DataSource.WEB_SEARCH: 0,
                DataSource.LLM_DIRECT: 0
            }
        }
        logger.info("Routing statistics reset")
