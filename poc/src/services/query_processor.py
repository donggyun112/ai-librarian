"""
통합 쿼리 정제 서비스 - 모든 쿼리 전처리를 중앙화
"""

import re
from typing import List, Dict, Any, Optional, Set
from enum import Enum
import logging
from datetime import datetime

from ..models.question import Question, QuestionType

logger = logging.getLogger(__name__)


class QueryProcessingMode(str, Enum):
    """쿼리 처리 모드"""
    
    VECTOR_SEARCH = "vector_search"    # 벡터 검색용
    WEB_SEARCH = "web_search"          # 웹 검색용  
    LLM_DIRECT = "llm_direct"          # LLM 직접 질의용
    GENERAL = "general"                # 일반적 처리


class ProcessedQuery:
    """처리된 쿼리 결과"""
    
    def __init__(self, 
                 original_query: str,
                 processed_query: str,
                 keywords: List[str],
                 processing_mode: QueryProcessingMode,
                 metadata: Dict[str, Any]):
        self.original_query = original_query
        self.processed_query = processed_query
        self.keywords = keywords
        self.processing_mode = processing_mode
        self.metadata = metadata
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "original_query": self.original_query,
            "processed_query": self.processed_query,
            "keywords": self.keywords,
            "processing_mode": self.processing_mode.value,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat()
        }


class QueryProcessor:
    """
    통합 쿼리 정제 서비스.
    
    모든 데이터소스별 쿼리 정제 로직을 중앙화하여 일관성을 보장합니다.
    """
    
    def __init__(self):
        """쿼리 프로세서 초기화"""
        
        # 키워드 사전 정의
        self.keyword_categories = {
            'factual': ['정의', '의미', '설명', '차이', '특징', 'what is', 'explain', 'define', 'difference', 'feature'],
            'temporal': ['최근', '최신', '2024', '2025', '현재', 'latest', 'recent', 'current', '오늘', 'today', 'now'],
            'comparative': ['비교', '분석', '평가', '대비', 'compare', 'analyze', 'evaluate', 'versus', 'vs'],
            'procedural': ['어떻게', '방법', '과정', '절차', 'how', 'method', 'process', 'procedure', 'step'],
            'causal': ['왜', '이유', '원인', '때문', 'why', 'reason', 'cause', 'because'],
            'quantitative': ['얼마', '몇', '수', '개수', 'how many', 'how much', 'number', 'count']
        }
        
        # 불용어 정의
        self.stop_words = {
            'korean': ['은', '는', '이', '가', '을', '를', '에', '에서', '로', '으로', '와', '과', '의', '도', '만', '부터', '까지', '에게', '한테'],
            'english': ['a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did']
        }
        
        # 정제 규칙
        self.cleaning_patterns = [
            (r'[^\w\s가-힣]', ' '),           # 특수문자 제거 (한글, 영문, 숫자, 공백만 유지)
            (r'\s+', ' '),                    # 연속 공백을 단일 공백으로
            (r'^\s+|\s+$', ''),               # 앞뒤 공백 제거
        ]
        
        # 통계 추적
        self.processing_stats = {
            'total_processed': 0,
            'mode_usage': {mode.value: 0 for mode in QueryProcessingMode},
            'keyword_extraction_count': 0,
            'query_enhancement_count': 0
        }
    
    def process_query(self, 
                     query: str, 
                     mode: QueryProcessingMode = QueryProcessingMode.GENERAL,
                     question_type: Optional[QuestionType] = None,
                     enhance_with_keywords: bool = True) -> ProcessedQuery:
        """
        쿼리를 지정된 모드에 따라 정제합니다.
        
        Args:
            query: 원본 쿼리
            mode: 처리 모드
            question_type: 질문 유형 (선택사항)
            enhance_with_keywords: 키워드로 쿼리 강화 여부
            
        Returns:
            ProcessedQuery: 처리된 쿼리 결과
        """
        logger.info(f"Processing query in {mode.value} mode: {query[:50]}...")
        
        self.processing_stats['total_processed'] += 1
        self.processing_stats['mode_usage'][mode.value] += 1
        
        # 1. 기본 정제
        cleaned_query = self._clean_query(query)
        
        # 2. 키워드 추출
        keywords = self._extract_keywords(cleaned_query)
        
        # 3. 모드별 특화 처리
        processed_query = self._apply_mode_specific_processing(
            cleaned_query, mode, question_type, keywords
        )
        
        # 4. 키워드로 쿼리 강화 (옵션)
        if enhance_with_keywords and keywords:
            processed_query = self._enhance_with_keywords(processed_query, keywords, mode)
            self.processing_stats['query_enhancement_count'] += 1
        
        # 5. 메타데이터 생성
        metadata = self._generate_metadata(query, processed_query, keywords, mode, question_type)
        
        result = ProcessedQuery(
            original_query=query,
            processed_query=processed_query,
            keywords=keywords,
            processing_mode=mode,
            metadata=metadata
        )
        
        logger.info(f"Query processed: '{query[:30]}...' -> '{processed_query[:30]}...'")
        return result
    
    def _clean_query(self, query: str) -> str:
        """기본 쿼리 정제"""
        cleaned = query
        
        # 정제 패턴 적용
        for pattern, replacement in self.cleaning_patterns:
            cleaned = re.sub(pattern, replacement, cleaned)
        
        return cleaned.strip()
    
    def _extract_keywords(self, query: str) -> List[str]:
        """키워드 추출 (개선된 버전)"""
        self.processing_stats['keyword_extraction_count'] += 1
        
        # 1. 기본 단어 추출
        words = re.findall(r'\b[가-힣a-zA-Z]+\b', query.lower())
        
        # 2. 불용어 제거
        korean_stops = set(self.stop_words['korean'])
        english_stops = set(self.stop_words['english'])
        
        filtered_words = []
        for word in words:
            if len(word) > 1:  # 1글자 단어 제외
                # 한글 불용어 체크
                if any(char in '가-힣' for char in word) and word not in korean_stops:
                    filtered_words.append(word)
                # 영어 불용어 체크
                elif word.isalpha() and word not in english_stops:
                    filtered_words.append(word)
                # 숫자 포함 단어는 유지
                elif any(char.isdigit() for char in word):
                    filtered_words.append(word)
        
        # 3. 중요도 기반 정렬 및 상위 키워드 선택
        important_keywords = self._rank_keywords(filtered_words, query)
        
        return important_keywords[:10]  # 상위 10개만 반환
    
    def _rank_keywords(self, words: List[str], original_query: str) -> List[str]:
        """키워드 중요도 기반 순위 매기기"""
        word_scores = {}
        
        for word in words:
            score = 0
            
            # 길이 점수 (더 긴 단어가 중요)
            score += len(word) * 0.1
            
            # 카테고리 키워드 보너스
            for category, category_words in self.keyword_categories.items():
                if word in category_words:
                    score += 2.0
                    break
            
            # 빈도 점수
            frequency = original_query.lower().count(word)
            score += frequency * 0.5
            
            # 위치 점수 (앞쪽에 나오는 단어가 중요)
            first_position = original_query.lower().find(word)
            if first_position != -1:
                position_score = 1.0 - (first_position / len(original_query))
                score += position_score * 0.3
            
            word_scores[word] = score
        
        # 점수 기준 내림차순 정렬
        ranked_words = sorted(word_scores.items(), key=lambda x: x[1], reverse=True)
        return [word for word, score in ranked_words]
    
    def _apply_mode_specific_processing(self, 
                                      query: str, 
                                      mode: QueryProcessingMode,
                                      question_type: Optional[QuestionType],
                                      keywords: List[str]) -> str:
        """모드별 특화 처리"""
        
        if mode == QueryProcessingMode.WEB_SEARCH:
            return self._process_for_web_search(query, question_type, keywords)
        elif mode == QueryProcessingMode.VECTOR_SEARCH:
            return self._process_for_vector_search(query, keywords)
        elif mode == QueryProcessingMode.LLM_DIRECT:
            return self._process_for_llm_direct(query, question_type)
        else:
            return query
    
    def _process_for_web_search(self, 
                               query: str, 
                               question_type: Optional[QuestionType],
                               keywords: List[str]) -> str:
        """웹 검색용 쿼리 처리"""
        processed = query
        
        # 시간 관련 키워드 추가
        temporal_keywords = self.keyword_categories['temporal']
        has_temporal = any(keyword in query.lower() for keyword in temporal_keywords)
        
        if question_type == QuestionType.CURRENT_EVENTS or not has_temporal:
            if any(char in '가-힣' for char in query):  # Korean
                processed = f"{processed} 최신 2024"
            else:  # English
                processed = f"{processed} latest 2024"
        
        # 질문 형태를 검색 형태로 변환
        question_patterns = [
            (r'^(무엇|뭐|what)\s*(은|는|이|가|is)\s*', ''),
            (r'^(어떻게|how)\s*(하|to)\s*', ''),
            (r'^(왜|why)\s*(는|is)\s*', ''),
            (r'\?$', ''),  # 물음표 제거
        ]
        
        for pattern, replacement in question_patterns:
            processed = re.sub(pattern, replacement, processed, flags=re.IGNORECASE)
        
        return processed.strip()
    
    def _process_for_vector_search(self, query: str, keywords: List[str]) -> str:
        """벡터 검색용 쿼리 처리"""
        # 벡터 검색은 의미적 유사성을 기반으로 하므로 원본 유지하되 정제만 수행
        processed = query
        
        # 질문 형태 유지 (벡터 검색에서는 질문 형태가 도움이 될 수 있음)
        # 단지 불필요한 조사나 특수문자만 정리
        
        return processed
    
    def _process_for_llm_direct(self, query: str, question_type: Optional[QuestionType]) -> str:
        """LLM 직접 질의용 쿼리 처리"""
        processed = query
        
        # LLM은 자연어 처리에 뛰어나므로 원본 형태 최대한 유지
        # 단지 명확성을 위한 최소한의 정제만 수행
        
        # 질문 유형에 따른 컨텍스트 힌트 추가 (옵션)
        if question_type == QuestionType.FACTUAL:
            # 사실적 질문임을 명시적으로 표현
            if not any(word in processed.lower() for word in ['정의', '의미', 'define', 'explain']):
                processed = f"{processed} (정확한 정보로 답변해주세요)"
        
        return processed
    
    def _enhance_with_keywords(self, query: str, keywords: List[str], mode: QueryProcessingMode) -> str:
        """키워드로 쿼리 강화"""
        if not keywords:
            return query
        
        # 모드별 키워드 강화 전략
        if mode == QueryProcessingMode.VECTOR_SEARCH:
            # 벡터 검색: 관련 키워드 추가로 검색 범위 확장
            relevant_keywords = [kw for kw in keywords if len(kw) > 2][:3]
            if relevant_keywords:
                keywords_text = " ".join(relevant_keywords)
                return f"{query} {keywords_text}"
        
        elif mode == QueryProcessingMode.WEB_SEARCH:
            # 웹 검색: 핵심 키워드만 추가
            core_keywords = [kw for kw in keywords if len(kw) > 3][:2]
            if core_keywords:
                keywords_text = " ".join(core_keywords)
                return f"{query} {keywords_text}"
        
        return query
    
    def _generate_metadata(self, 
                          original: str, 
                          processed: str, 
                          keywords: List[str],
                          mode: QueryProcessingMode,
                          question_type: Optional[QuestionType]) -> Dict[str, Any]:
        """메타데이터 생성"""
        
        # 키워드 카테고리 분석
        keyword_categories = {}
        for category, category_words in self.keyword_categories.items():
            found_keywords = [kw for kw in keywords if kw in category_words]
            if found_keywords:
                keyword_categories[category] = found_keywords
        
        return {
            'processing_mode': mode.value,
            'question_type': question_type.value if question_type else None,
            'original_length': len(original),
            'processed_length': len(processed),
            'keywords_count': len(keywords),
            'keyword_categories': keyword_categories,
            'has_temporal_keywords': bool(keyword_categories.get('temporal')),
            'has_factual_keywords': bool(keyword_categories.get('factual')),
            'has_comparative_keywords': bool(keyword_categories.get('comparative')),
            'processing_timestamp': datetime.now().isoformat()
        }
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """처리 통계 반환"""
        return {
            'processing_stats': self.processing_stats.copy(),
            'keyword_categories': list(self.keyword_categories.keys()),
            'available_modes': [mode.value for mode in QueryProcessingMode]
        }
    
    def reset_stats(self) -> None:
        """통계 초기화"""
        self.processing_stats = {
            'total_processed': 0,
            'mode_usage': {mode.value: 0 for mode in QueryProcessingMode},
            'keyword_extraction_count': 0,
            'query_enhancement_count': 0
        }
        logger.info("Query processing statistics reset")
    
    def analyze_query_characteristics(self, query: str) -> Dict[str, Any]:
        """쿼리 특성 분석"""
        
        characteristics = {
            'length': len(query),
            'word_count': len(query.split()),
            'has_korean': bool(re.search(r'[가-힣]', query)),
            'has_english': bool(re.search(r'[a-zA-Z]', query)),
            'has_numbers': bool(re.search(r'\d', query)),
            'has_question_mark': '?' in query,
            'question_words': [],
            'temporal_indicators': [],
            'complexity_score': 0.0
        }
        
        # 질문 단어 찾기
        question_words = ['무엇', '뭐', '어떻게', '왜', '언제', '어디서', '누가', 'what', 'how', 'why', 'when', 'where', 'who']
        for word in question_words:
            if word in query.lower():
                characteristics['question_words'].append(word)
        
        # 시간 지시어 찾기
        for temporal in self.keyword_categories['temporal']:
            if temporal in query.lower():
                characteristics['temporal_indicators'].append(temporal)
        
        # 복잡도 점수 계산
        complexity_factors = {
            'length': min(len(query.split()) / 20, 1.0) * 0.4,
            'questions': min(query.count('?'), 3) / 3 * 0.3,
            'conjunctions': len([w for w in ['그리고', '하지만', 'and', 'but', '또한'] if w in query.lower()]) / 5 * 0.3
        }
        characteristics['complexity_score'] = sum(complexity_factors.values())
        
        return characteristics
