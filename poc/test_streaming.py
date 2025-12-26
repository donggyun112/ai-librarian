import asyncio
import sys
import os

# Add src to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.supervisor import Supervisor

async def test_streaming():
    print("Initializing Supervisor...")
    supervisor = Supervisor()
    question = "2024년 AI 트렌드는?"
    
    print(f"\nQuestion: {question}")
    print("-" * 50)
    
    event_counts = {"think": 0, "act": 0, "observe": 0, "answer": 0}
    
    async for event in supervisor.process_stream(question):
        key = event["type"]
        event_counts[key] = event_counts.get(key, 0) + 1
        
        if key == "think":
            print(f"[THINK] {event['content'][:50]}...")
        elif key == "act":
            print(f"[ACT] {event['tool']}({event['args']})")
        elif key == "observe":
            content = event['content']
            print(f"[OBSERVE] Length: {len(content)}")
        elif key == "answer":
            print(f"[ANSWER] {event['content'][:50]}...")
            
    print("-" * 50)
    print("Event Counts:", event_counts)
    
    # Check if we have act/observe and EITHER (think/answer) OR (token)
    has_action = event_counts["act"] > 0 and event_counts["observe"] > 0
    has_content = (event_counts["think"] > 0 or event_counts["answer"] > 0) or (event_counts.get("token", 0) > 0)
    
    if has_action and has_content:
        print("\n✅ Streaming Test PASSED: All event types received.")
    else:
        print("\n❌ Streaming Test FAILED: Missing event types.")

if __name__ == "__main__":
    asyncio.run(test_streaming())
