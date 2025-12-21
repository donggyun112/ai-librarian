"""회귀 검색 (2회 이상 검색) 테스트 케이스"""
import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.supervisor import Supervisor
from langchain_core.messages import AIMessage, ToolMessage


async def count_search_calls(supervisor: Supervisor, question: str) -> dict:
    """검색 호출 횟수 및 상세 정보 추출"""
    response = await supervisor.process(question)

    # 로그에서 ACT 횟수 카운트
    act_count = sum(1 for log in response.execution_log if log.startswith("Act:"))
    think_count = sum(1 for log in response.execution_log if "Thinking:" in log)

    # 검색어 추출
    search_queries = []
    for log in response.execution_log:
        if log.startswith("Act:"):
            search_queries.append(log)

    return {
        "question": question,
        "think_count": think_count,
        "act_count": act_count,
        "search_queries": search_queries,
        "answer_length": len(response.answer),
        "execution_log": response.execution_log
    }


async def main():
    print("=" * 60)
    print("회귀 검색 테스트 (2회 이상 검색 유도)")
    print("=" * 60)

    supervisor = Supervisor()

    # 자율 회귀 검색 테스트 케이스 (LLM이 스스로 정보 부족 판단)
    test_cases = [
        # 케이스 1: 검색 결과가 불충분할 가능성이 높은 질문
        {
            "name": "자율 회귀 - 희귀 정보",
            "question": "2024년 12월에 출시된 AI 스타트업 'Cognition AI'의 Devin 에이전트 가격과 성능 벤치마크를 알려주세요",
            "expected_min_searches": 2,
            "reason": "첫 검색에서 가격/벤치마크 둘 다 얻기 어려움 → LLM이 추가 검색 판단"
        },

        # 케이스 2: 상세 정보가 필요한 질문 (한 번 검색으로 부족)
        {
            "name": "자율 회귀 - 깊은 정보",
            "question": "Claude 3.5 Sonnet의 구체적인 컨텍스트 윈도우 크기, 토큰당 가격, 그리고 MMLU 벤치마크 점수를 정확히 알려주세요",
            "expected_min_searches": 2,
            "reason": "세 가지 구체적 수치 → 한 검색으로 모두 얻기 어려움"
        },

        # 케이스 3: 첫 검색 결과가 모호할 수 있는 질문
        {
            "name": "자율 회귀 - 최신 발표",
            "question": "2024년 12월에 발표된 Google의 Gemini 2.0 모델의 새로운 기능과 API 가격을 자세히 알려주세요",
            "expected_min_searches": 2,
            "reason": "최신 정보 + 상세 스펙 → 추가 검색 필요 가능성"
        },

        # 케이스 4: 비교가 필요하지만 명시적으로 요청하지 않음
        {
            "name": "자율 회귀 - 암묵적 비교",
            "question": "현재 가장 성능이 좋은 코딩 AI가 뭔지, 그게 왜 좋은지 근거와 함께 알려줘",
            "expected_min_searches": 2,
            "reason": "순위 확인 → 해당 AI 상세 정보 → 자율적 추가 검색"
        },
    ]

    results = []

    for i, case in enumerate(test_cases, 1):
        print(f"\n{'='*60}")
        print(f"테스트 {i}: {case['name']}")
        print(f"예상 최소 검색 횟수: {case['expected_min_searches']}회")
        print(f"이유: {case['reason']}")
        print(f"{'='*60}")
        print(f"질문: {case['question']}")
        print("-" * 40)

        try:
            result = await count_search_calls(supervisor, case["question"])
            result["test_name"] = case["name"]
            result["expected_min_searches"] = case["expected_min_searches"]
            result["passed"] = result["act_count"] >= case["expected_min_searches"]
            results.append(result)

            print(f"\n결과:")
            print(f"  - THINK 횟수: {result['think_count']}")
            print(f"  - ACT (검색) 횟수: {result['act_count']}")
            print(f"  - 답변 길이: {result['answer_length']} chars")

            if result["search_queries"]:
                print(f"\n검색 호출 상세:")
                for j, query in enumerate(result["search_queries"], 1):
                    print(f"  [{j}] {query}")

            status = "✅ PASS" if result["passed"] else "❌ FAIL"
            print(f"\n테스트 결과: {status} (기대: {case['expected_min_searches']}회 이상, 실제: {result['act_count']}회)")

        except Exception as e:
            print(f"❌ 에러 발생: {str(e)}")
            results.append({
                "test_name": case["name"],
                "error": str(e),
                "passed": False
            })

    # 최종 요약
    print("\n" + "=" * 60)
    print("테스트 결과 요약")
    print("=" * 60)

    passed = sum(1 for r in results if r.get("passed", False))
    total = len(results)

    print(f"\n{'테스트명':<30} {'THINK':<8} {'ACT':<8} {'결과':<10}")
    print("-" * 60)

    for r in results:
        if "error" in r:
            print(f"{r['test_name']:<30} {'ERROR':<8} {'ERROR':<8} {'❌ FAIL':<10}")
        else:
            status = "✅ PASS" if r["passed"] else "❌ FAIL"
            print(f"{r['test_name']:<30} {r['think_count']:<8} {r['act_count']:<8} {status:<10}")

    print("-" * 60)
    print(f"총 {total}개 중 {passed}개 통과 ({passed/total*100:.1f}%)")

    # 회귀 검색 발생 여부 확인
    recursive_cases = [r for r in results if r.get("act_count", 0) >= 2]
    if recursive_cases:
        print(f"\n✅ 회귀 검색 발생 확인: {len(recursive_cases)}개 케이스에서 2회 이상 검색")
    else:
        print(f"\n⚠️ 회귀 검색 미발생: 모든 케이스가 1회 검색으로 종료됨")


if __name__ == "__main__":
    asyncio.run(main())
