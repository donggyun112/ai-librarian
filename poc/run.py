"""간단한 CLI 테스트"""
import asyncio
import sys
import os

# Add src to python path to allow imports if running directly from poc/
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.supervisor import Supervisor


async def main():
    print("=" * 50)
    print("AI Librarian - Supervisor ReAct Pattern Test")
    print("=" * 50)

    # 초기화 (Workers 불필요)
    supervisor = Supervisor()

    # 테스트 질문
    test_questions = [
        "LangChain이 무엇인가요?",
        "2024년 AI 트렌드는 무엇인가요?",
    ]

    for question in test_questions:
        print(f"\n📝 질문: {question}")
        print("-" * 40)

        response = await supervisor.process(question)

        print(f"\n💡 답변:\n{response.answer}")
        
        if response.execution_log:
            print("\n📋 실행 로그:")
            for log in response.execution_log:
                print(f"  {log}")
                
        if response.sources:
            print(f"\n📎 출처: {response.sources}")

        print("\n" + "=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
