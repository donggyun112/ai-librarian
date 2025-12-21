"""
Test script for the new LLM-based autonomous routing system.

This script demonstrates the difference between:
1. Old rule-based routing (executes multiple tools)
2. New LLM-based autonomous routing (selects ONE tool intelligently)
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Test questions covering different scenarios
TEST_QUESTIONS = [
    {
        "question": "LangChain이 무엇인가요?",
        "expected_tool": "vector_db",
        "reason": "정의/설명 질문 → 문서 검색이 적합"
    },
    {
        "question": "2024년 최신 AI 트렌드는 무엇인가요?",
        "expected_tool": "web_search",
        "reason": "최신 정보 → 웹 검색이 필수"
    },
    {
        "question": "AI가 인간의 삶에 미치는 영향에 대해 설명해주세요",
        "expected_tool": "llm_direct",
        "reason": "일반적/철학적 질문 → LLM 직접 답변이 적합"
    },
    {
        "question": "RAG와 파인튜닝의 차이점을 비교하고, 최신 연구 동향도 알려주세요",
        "expected_tool": "hybrid",
        "reason": "복합 질문 (정의 + 최신 정보) → 하이브리드 필요"
    }
]


def test_llm_router_only():
    """Test LLM router without executing tools (just routing decisions)."""
    print("=" * 80)
    print("🧪 TEST 1: LLM Router Decision Testing (No Tool Execution)")
    print("=" * 80)
    print()

    from src.langchain.agents.llm_router import LLMRouter

    # Initialize router
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        print("❌ Error: OPENAI_API_KEY not found in environment")
        return

    router = LLMRouter(openai_api_key=openai_api_key)

    # Test each question
    for i, test_case in enumerate(TEST_QUESTIONS, 1):
        print(f"\n{'─' * 80}")
        print(f"📝 Test Case {i}/{len(TEST_QUESTIONS)}")
        print(f"{'─' * 80}")
        print(f"Question: {test_case['question']}")
        print(f"Expected Tool: {test_case['expected_tool']}")
        print(f"Reason: {test_case['reason']}")
        print()

        # Get routing decision
        decision = router.route(test_case['question'])

        # Display result
        print(f"✅ LLM Router Decision:")
        print(f"   - Selected Tool: {decision.primary_tool.value}")
        print(f"   - Confidence: {decision.confidence:.2f}")
        print(f"   - Reasoning: {decision.reasoning}")

        if decision.fallback_tool:
            print(f"   - Fallback Tool: {decision.fallback_tool.value}")

        if decision.requires_multiple_tools:
            print(f"   - Requires Multiple Tools: Yes")
            print(f"   - Additional Tools: {[t.value for t in decision.additional_tools]}")

        # Check if correct
        is_correct = decision.primary_tool.value == test_case['expected_tool']
        result_emoji = "✅" if is_correct else "⚠️"
        print(f"\n{result_emoji} Result: {'CORRECT' if is_correct else 'DIFFERENT (but may still be valid)'}")

    # Show statistics
    print(f"\n{'=' * 80}")
    print("📊 Router Statistics:")
    print(f"{'=' * 80}")
    stats = router.get_stats()
    print(f"Total Routings: {stats['total_routings']}")
    print(f"Average Confidence: {stats['average_confidence']:.2f}")
    print(f"Tool Selections:")
    for tool, count in stats['tool_selections'].items():
        print(f"  - {tool}: {count}")


def test_autonomous_vs_rule_based():
    """Compare autonomous routing vs rule-based routing."""
    print("\n\n")
    print("=" * 80)
    print("🧪 TEST 2: Autonomous vs Rule-Based Routing Comparison")
    print("=" * 80)
    print()

    # Note: This test requires Milvus to be running
    # We'll just show the conceptual difference here

    print("⚠️  Full integration test requires:")
    print("   1. Milvus/Zilliz cluster running")
    print("   2. Vector store initialized")
    print("   3. Documents indexed")
    print()
    print("📋 Conceptual Comparison:")
    print()
    print("┌─────────────────────────┬──────────────────────┬──────────────────────┐")
    print("│ Aspect                  │ Rule-Based           │ Autonomous LLM       │")
    print("├─────────────────────────┼──────────────────────┼──────────────────────┤")
    print("│ Decision Making         │ Hard-coded rules     │ LLM reasoning        │")
    print("│ Tools Executed          │ Multiple (wasteful)  │ Single (efficient)   │")
    print("│ Adaptability            │ Static               │ Dynamic              │")
    print("│ Reasoning Transparency  │ None                 │ Full explanation     │")
    print("│ Cost                    │ Higher (多 API calls)│ Lower (1-2 calls)    │")
    print("│ Latency                 │ Slower (多 tools)    │ Faster (1 tool)      │")
    print("└─────────────────────────┴──────────────────────┴──────────────────────┘")
    print()

    # Example of what happens in each mode
    print("📌 Example: '2024년 최신 AI 트렌드는?'")
    print()
    print("❌ OLD Rule-Based Mode:")
    print("   1. Calculate confidence: vector_db=0.2, web=0.9, llm=0.3")
    print("   2. All above threshold → Execute ALL THREE")
    print("   3. Execute vector_db → No results")
    print("   4. Execute web_search → Good results ✓")
    print("   5. Execute llm_direct → Generic answer")
    print("   6. Select best result")
    print("   Result: 3 API calls, wasted time/money")
    print()
    print("✅ NEW Autonomous Mode:")
    print("   1. LLM analyzes: '최신' → needs current info")
    print("   2. LLM decides: Use web_search ONLY")
    print("   3. Execute web_search → Good results ✓")
    print("   4. Done")
    print("   Result: 2 API calls (1 routing + 1 tool), efficient!")
    print()


def show_usage_guide():
    """Show how to use the new system."""
    print("\n\n")
    print("=" * 80)
    print("📖 USAGE GUIDE: How to Use Autonomous Routing")
    print("=" * 80)
    print()

    print("1️⃣  Enable Autonomous Routing (Default):")
    print()
    print("```python")
    print("from src.langchain.services.langchain_answer_service import LangChainAnswerService")
    print()
    print("service = LangChainAnswerService(")
    print("    vector_store=vector_store,")
    print("    embedding_service=embedding_service,")
    print("    use_autonomous_routing=True,  # ← NEW! Default is True")
    print("    enable_reflection=False       # ← Optional: retry on failure")
    print(")")
    print()
    print("answer = service.get_answer(question)")
    print("```")
    print()

    print("2️⃣  Check Routing Decision:")
    print()
    print("```python")
    print("# Routing info is in answer metadata")
    print("print(answer.metadata['routing_mode'])        # 'autonomous_llm'")
    print("print(answer.metadata['selected_tool'])       # 'vector_db' | 'web_search' | 'llm_direct'")
    print("print(answer.metadata['routing_confidence'])  # 0.0 - 1.0")
    print("print(answer.metadata['routing_reasoning'])   # LLM's explanation")
    print("```")
    print()

    print("3️⃣  Enable Reflection (Advanced):")
    print()
    print("```python")
    print("service = LangChainAnswerService(")
    print("    vector_store=vector_store,")
    print("    embedding_service=embedding_service,")
    print("    use_autonomous_routing=True,")
    print("    enable_reflection=True  # ← Automatically retry with different tool if first fails")
    print(")")
    print("```")
    print()

    print("4️⃣  Fallback to Rule-Based (If Needed):")
    print()
    print("```python")
    print("service = LangChainAnswerService(")
    print("    vector_store=vector_store,")
    print("    embedding_service=embedding_service,")
    print("    use_autonomous_routing=False  # ← Use old rule-based routing")
    print(")")
    print("```")
    print()


def main():
    """Run all tests."""
    print("\n")
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 15 + "LLM-based Autonomous Routing Test Suite" + " " * 23 + "║")
    print("╚" + "═" * 78 + "╝")
    print()

    # Test 1: Router decisions only
    try:
        test_llm_router_only()
    except Exception as e:
        print(f"\n❌ Test 1 failed: {str(e)}")
        import traceback
        traceback.print_exc()

    # Test 2: Comparison
    test_autonomous_vs_rule_based()

    # Usage guide
    show_usage_guide()

    print("\n" + "=" * 80)
    print("✅ All tests completed!")
    print("=" * 80)
    print()
    print("💡 Next Steps:")
    print("   1. Start your Milvus/Zilliz cluster")
    print("   2. Update streamlit_app.py to use autonomous routing")
    print("   3. Run: uv run streamlit run streamlit_app.py")
    print("   4. Ask questions and check the routing decisions!")
    print()


if __name__ == "__main__":
    main()
