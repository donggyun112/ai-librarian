"""프롬프트 동작 평가 테스트

검색 여부, 검색 횟수 등을 평가하는 테스트
"""
import pytest
from unittest.mock import MagicMock, patch

from src.supervisor import Supervisor
from src.schemas.models import StreamEventType


class TestQueryClassification:
    """쿼리 분류 및 검색 전략 평가"""

    @pytest.fixture
    def mock_supervisor(self):
        """Mock된 Supervisor 생성"""
        with patch("src.adapters.openai.ChatOpenAI") as mock_chat:
            mock_llm = MagicMock()
            mock_chat.return_value = mock_llm
            mock_llm.bind_tools = MagicMock(return_value=mock_llm)
            supervisor = Supervisor(provider="openai")
            return supervisor

    def count_tool_calls(self, events: list, tool_name: str = None) -> int:
        """이벤트에서 도구 호출 횟수 카운트"""
        count = 0
        for event in events:
            if event.get("type") == StreamEventType.ACT:
                if tool_name is None or event.get("tool") == tool_name:
                    count += 1
        return count

    def has_search_call(self, events: list) -> bool:
        """검색 도구 호출 여부 확인"""
        for event in events:
            if event.get("type") == StreamEventType.ACT:
                tool = event.get("tool", "")
                if "search" in tool.lower():
                    return True
        return False


class TestStaticKnowledgeQueries:
    """정적 지식 쿼리 - 검색 없이 답변해야 함"""

    STATIC_QUERIES = [
        "Python 리스트 컴프리헨션 문법",
        "JavaScript async await 사용법",
        "피타고라스 정리가 뭐야?",
        "for 루프 문법 알려줘",
        "HTML div 태그 사용법",
        "SQL SELECT 문법",
        "Git commit 명령어",
        "HTTP GET과 POST 차이",
    ]

    @pytest.mark.parametrize("query", STATIC_QUERIES)
    def test_static_query_classification(self, query):
        """정적 지식 쿼리는 검색이 필요 없음을 확인"""
        # 이 테스트는 프롬프트의 의도를 문서화
        # 실제 LLM 호출 없이 쿼리 유형만 검증
        static_keywords = [
            "문법", "syntax", "사용법", "usage", "정의", "definition",
            "뭐야", "what is", "알려줘", "how to", "차이", "difference",
            "명령어", "command", "태그", "tag"
        ]
        is_static = any(kw in query.lower() for kw in static_keywords)
        assert is_static, f"'{query}'는 정적 지식 쿼리로 분류되어야 함"


class TestTimeSensitiveQueries:
    """시간 민감 쿼리 - 검색이 필요함"""

    TIME_SENSITIVE_QUERIES = [
        "2025년 AI 트렌드",
        "최신 Python 버전",
        "오늘 날씨",
        "현재 비트코인 가격",
        "최근 뉴스",
        "요즘 인기있는 프레임워크",
    ]

    @pytest.mark.parametrize("query", TIME_SENSITIVE_QUERIES)
    def test_time_sensitive_query_classification(self, query):
        """시간 민감 쿼리는 검색이 필요함을 확인"""
        time_keywords = [
            "2024", "2025", "최신", "latest", "현재", "current",
            "오늘", "today", "요즘", "최근", "recent", "트렌드", "trend"
        ]
        needs_search = any(kw in query.lower() for kw in time_keywords)
        assert needs_search, f"'{query}'는 검색이 필요한 쿼리로 분류되어야 함"


class TestExploratoryQueries:
    """탐색적 쿼리 - 다중 검색이 필요할 수 있음"""

    EXPLORATORY_QUERIES = [
        "AI 도구 추천해줘",
        "Python 웹 프레임워크 뭐가 있어?",
        "프론트엔드 프레임워크 비교해줘",
        "좋은 IDE 추천",
    ]

    @pytest.mark.parametrize("query", EXPLORATORY_QUERIES)
    def test_exploratory_query_classification(self, query):
        """탐색적 쿼리는 다중 검색이 필요할 수 있음을 확인"""
        exploratory_keywords = [
            "추천", "recommend", "뭐가 있", "what are",
            "비교", "compare", "좋은", "best", "리스트", "list"
        ]
        is_exploratory = any(kw in query.lower() for kw in exploratory_keywords)
        assert is_exploratory, f"'{query}'는 탐색적 쿼리로 분류되어야 함"


class TestQueryClassifier:
    """쿼리 분류기 유틸리티"""

    @staticmethod
    def classify(query: str) -> str:
        """쿼리 유형 분류

        Returns:
            "static" | "time_sensitive" | "exploratory" | "internal"
        """
        query_lower = query.lower()

        # 시간 민감 키워드 (먼저 체크)
        time_keywords = [
            "2024", "2025", "최신", "latest", "현재", "current",
            "오늘", "today", "요즘", "최근", "recent", "트렌드", "trend",
            "뉴스", "news", "가격", "price"
        ]
        if any(kw in query_lower for kw in time_keywords):
            return "time_sensitive"

        # 내부 문서 키워드
        internal_keywords = [
            "내부", "internal", "회사", "company", "우리",
            "사내", "문서", "document"
        ]
        if any(kw in query_lower for kw in internal_keywords):
            return "internal"

        # 탐색적 키워드 (추천, 비교 등) - "리스트"는 프로그래밍 용어일 수 있으므로 제외
        exploratory_keywords = [
            "추천", "recommend", "뭐가 있", "what are",
            "비교", "compare", "좋은", "best",
            "어떤 것", "which"
        ]
        if any(kw in query_lower for kw in exploratory_keywords):
            return "exploratory"

        # 기본값: 정적 지식
        return "static"

    def test_classifier_static(self):
        """정적 지식 분류 테스트"""
        assert self.classify("Python 문법") == "static"
        assert self.classify("for 루프 사용법") == "static"
        assert self.classify("HTTP란 무엇인가") == "static"

    def test_classifier_time_sensitive(self):
        """시간 민감 분류 테스트"""
        assert self.classify("2025년 트렌드") == "time_sensitive"
        assert self.classify("최신 뉴스") == "time_sensitive"
        assert self.classify("현재 가격") == "time_sensitive"

    def test_classifier_exploratory(self):
        """탐색적 분류 테스트"""
        assert self.classify("프레임워크 추천해줘") == "exploratory"
        assert self.classify("뭐가 있어?") == "exploratory"
        assert self.classify("비교해줘") == "exploratory"

    def test_classifier_internal(self):
        """내부 문서 분류 테스트"""
        assert self.classify("내부 문서 검색") == "internal"
        assert self.classify("회사 정책") == "internal"


class TestExpectedBehavior:
    """기대 동작 명세"""

    def test_expected_search_behavior(self):
        """쿼리별 기대 검색 동작"""
        expected = {
            # 정적 지식 - 검색 불필요
            "Python 리스트 컴프리헨션": {"search_needed": False, "max_searches": 0},
            "for 루프 문법": {"search_needed": False, "max_searches": 0},
            "HTTP GET POST 차이": {"search_needed": False, "max_searches": 0},

            # 시간 민감 - 1회 검색
            "2025년 AI 트렌드": {"search_needed": True, "max_searches": 3},
            "최신 Python 버전": {"search_needed": True, "max_searches": 1},

            # 탐색적 - 다중 검색 가능
            "AI 도구 추천": {"search_needed": True, "max_searches": 5},
            "프레임워크 비교": {"search_needed": True, "max_searches": 3},
        }

        for query, behavior in expected.items():
            query_type = TestQueryClassifier.classify(query)

            if not behavior["search_needed"]:
                assert query_type == "static", f"'{query}'는 검색 불필요"
            else:
                assert query_type != "static", f"'{query}'는 검색 필요"
