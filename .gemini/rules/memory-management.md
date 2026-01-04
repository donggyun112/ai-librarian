# Memory Management Rules - ai-librarian

## Conversation Memory System

The ai-librarian project uses an **in-memory conversation memory system**.

```python
# CORRECT: Store conversation in memory
from src.memory import ConversationMemory

memory = ConversationMemory()

async def query(request: QueryRequest, session_id: str):
    memory.add_message(session_id, "user", request.query)
    response = await supervisor.invoke(request.query, memory.get_context(session_id))
    memory.add_message(session_id, "assistant", response)
    return response
```

## Session Management

Sessions are organized by session_id:

```python
# CORRECT: Per-session memory
class ConversationMemory:
    def __init__(self):
        self.sessions: Dict[str, List[Message]] = {}

    def add_message(self, session_id: str, role: str, content: str):
        if session_id not in self.sessions:
            self.sessions[session_id] = []
        self.sessions[session_id].append(Message(role=role, content=content))

    def get_context(self, session_id: str, max_messages: int = 10) -> List[Message]:
        return self.sessions.get(session_id, [])[-max_messages:]

    def clear_session(self, session_id: str):
        if session_id in self.sessions:
            del self.sessions[session_id]
```

## Message Types

```python
from langchain.schema import BaseMessage, HumanMessage, AIMessage

# CORRECT: Use LangChain message types
messages: List[BaseMessage] = [
    HumanMessage(content="What is Python?"),
    AIMessage(content="Python is a programming language...")
]

response = await supervisor.invoke(messages=messages)
```

## Memory Cleanup

Implement session expiration:

```python
# CORRECT: Session expiration
from datetime import datetime, timedelta

class ConversationMemory:
    def __init__(self, expire_minutes: int = 30):
        self.sessions: Dict[str, Dict] = {}
        self.expire_minutes = expire_minutes

    def cleanup_expired_sessions(self):
        now = datetime.now()
        expired = []

        for session_id, session_data in self.sessions.items():
            if now - session_data['created_at'] > timedelta(minutes=self.expire_minutes):
                expired.append(session_id)

        for session_id in expired:
            del self.sessions[session_id]

    def add_message(self, session_id: str, role: str, content: str):
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                'messages': [],
                'created_at': datetime.now()
            }
        self.sessions[session_id]['messages'].append(
            Message(role=role, content=content)
        )
```

## Context Window Management

Manage LLM context window to avoid token limits:

```python
# CORRECT: Limit context size
def get_context(self, session_id: str, max_tokens: int = 2000) -> List[BaseMessage]:
    messages = self.sessions.get(session_id, [])
    context = []
    token_count = 0

    for message in reversed(messages):
        message_tokens = len(message.content.split())
        if token_count + message_tokens > max_tokens:
            break
        context.insert(0, message)
        token_count += message_tokens

    return context
```
