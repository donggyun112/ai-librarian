# ai-librarian LangGraph ReAct Agent - Project Rules

## Project Overview

ai-librarian is a LangGraph ReAct Agent-based intelligent Q&A system (RAG) using FastAPI and streaming APIs.

| Component | Path | Stack |
|-----------|------|-------|
| Main Server | `poc/` | FastAPI, Python 3.12, LangGraph, LangChain |
| LLM Adapters | `poc/src/adapters/` | OpenAI GPT-4o, Google Gemini 2.0 Flash |
| Supervisor Agent | `poc/src/supervisor/` | LangGraph state graph, ReAct pattern |
| Workers | `poc/src/workers/` | Web search (DuckDuckGo), RAG retrieval |
| API Layer | `poc/src/api/` | FastAPI routes, SSE streaming |
| Memory System | `poc/src/memory/` | Conversation history management |

**Technology Stack**: Python 3.12+, FastAPI, LangChain, LangGraph, OpenAI, Google Gemini, DuckDuckGo API, SSE streaming

---

## Overall Architecture

```
API Layer (FastAPI)
    |
Supervisor (LangGraph State Graph)
    |
Workers (Tools) -> Adapters (LLM providers)
    |
Memory (Conversation History)
```

---

## Module Structure (Canonical Pattern)

**Always use this structure for new modules:**

```
poc/src/module_name/
├── __init__.py           # Module exports
├── schemas.py            # Pydantic models (Request/Response)
├── worker.py             # Worker/Tool implementation (if tool)
├── adapter.py            # Adapter implementation (if LLM provider)
└── utils.py              # Module utilities (optional)
```

**For API endpoints:**
```
poc/src/api/
├── __init__.py           # FastAPI app initialization
├── routers/
│   └── query_router.py   # Query endpoints
└── schemas.py            # Request/response models
```

**Reference implementations:**
- Worker: `poc/src/workers/`
- Adapter: `poc/src/adapters/`
- API: `poc/src/api/`

---

## Coding Standards

### 0. No Lazy Imports (CRITICAL)

ALL imports MUST be at the top of the file. Imports inside functions are STRICTLY FORBIDDEN.

```python
# FORBIDDEN
async def process_data():
    from ..domain.events import SomeEvent  # NEVER DO THIS

# REQUIRED
from ..domain.events import SomeEvent

async def process_data():
    ...
```

**Only Exception:** `TYPE_CHECKING` block for type hints.

### 1. Tests Are Required

NO CODE WITHOUT TESTS. Code without tests = Trash code.

```bash
# Test Commands
uv run pytest tests/ -v
uv run pytest tests/ -v --cov=src
```

Test structure:
```
tests/
├── conftest.py
├── module_name/
│   ├── unit/
│   │   └── test_service.py
│   └── integration/
│       └── test_api.py
```

### 2. Logging: Loguru Only

```python
from loguru import logger

# REQUIRED
logger.info(f"Created team: {team_id}")
logger.error(f"Failed to process: {e}", exc_info=True)

# FORBIDDEN
print(f"Debug: {data}")  # NEVER
import logging; logging.info(...)  # NEVER
```

**After resolving issues, REMOVE all `logger.debug()` statements.**

### 3. Never Log Sensitive Data

```python
# NEVER
logger.info(f"Password: {password}")
logger.info(f"Token: {jwt_token}")
logger.info(f"API Key: {api_key}")

# CORRECT
logger.info(f"User logged in: user_id={user_id}")
```

### 4. Type Hints Required

```python
from typing import Dict, List, Optional, Any

# REQUIRED
async def get_team(team_id: str) -> Optional[Dict[str, Any]]:
    return await self.repo.find_by_id(team_id)

# REJECTED
async def get_team(team_id):  # No types = rejected
    ...
```

### 5. Naming Conventions

- Variables/Functions: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`

---

## Async/Await (CRITICAL)

**All I/O operations must be async:**

```python
# CORRECT: Async for LLM/Network/Web calls
async def invoke_supervisor(query: str) -> str:
    response = await supervisor.invoke(query)
    return response

# WRONG: Blocking synchronous call
def invoke_supervisor_sync(query: str) -> str:
    response = supervisor.invoke(query)  # Blocks event loop - NEVER
    return response

# CORRECT: Async generator for streaming
async def stream_supervisor_response(query: str):
    async for event in supervisor.invoke_streaming(query):
        yield f"data: {json.dumps(event)}\n\n"
```

---

## LangGraph Patterns (MANDATORY)

**All LangGraph integrations must follow these patterns:**

```python
# CORRECT: LangGraph state
from langgraph.graph import StateGraph, START, END

class AgentState(TypedDict):
    query: str
    messages: List[BaseMessage]
    steps: List[str]
    final_response: str

# CORRECT: Tool definition
def create_search_tool() -> Tool:
    return Tool(name="search", func=search_function, ...)

# ANTI-PATTERN: Hardcoded LLM calls outside adapters
from openai import OpenAI
client = OpenAI()  # WRONG - use adapter instead
```

---

## LLM Adapter Pattern (MANDATORY)

**All LLM calls must go through adapters:**

```python
# CORRECT: Adapter abstraction
class LLMAdapter:
    async def invoke(self, messages: List[BaseMessage]) -> str:
        pass

class OpenAIAdapter(LLMAdapter):
    async def invoke(self, messages: List[BaseMessage]) -> str:
        from openai import AsyncOpenAI
        client = AsyncOpenAI()
        response = await client.chat.completions.create(...)
        return response.choices[0].message.content

# Usage in supervisor (NOT in API or workers)
class Supervisor:
    def __init__(self, adapter: LLMAdapter):
        self.adapter = adapter

    async def invoke(self, query: str):
        response = await self.adapter.invoke(messages)
        return response
```

---

## SSE Streaming (REQUIRED)

**All long-running operations must use SSE streaming:**

```python
from fastapi.responses import StreamingResponse

async def stream_supervisor_response(query: str):
    async for event in supervisor.invoke(query):
        yield f"data: {json.dumps({'type': 'event', 'data': event})}\n\n"
        await asyncio.sleep(0)  # Allow cancellation

@router.post("/api/query", response_class=StreamingResponse)
async def query(request: QueryRequest):
    return StreamingResponse(
        stream_supervisor_response(request.query),
        media_type="text/event-stream"
    )
```

---

## FastAPI Integration with LangGraph

**FastAPI should act as a thin wrapper around LangGraph:**

```python
# CORRECT: API routes call supervisor
from src.supervisor import create_supervisor

supervisor = create_supervisor()

@router.post("/api/query")
async def query_endpoint(request: QueryRequest):
    async def event_generator():
        async for event in supervisor.invoke(request.query):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

---

## Memory Management

### Conversation Memory System

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

### Session Management

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

### Message Types

```python
from langchain.schema import BaseMessage, HumanMessage, AIMessage

# CORRECT: Use LangChain message types
messages: List[BaseMessage] = [
    HumanMessage(content="What is Python?"),
    AIMessage(content="Python is a programming language...")
]
```

### Context Window Management

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

---

## Error Handling

```python
# Handle LLM-specific errors
try:
    response = await adapter.invoke(messages)
except AuthenticationError:
    logger.error("LLM authentication failed - check API keys")
    raise
except RateLimitError:
    logger.warning("LLM rate limit hit - implement backoff")
    raise
except Exception as e:
    logger.error(f"Unexpected LLM error: {e}", exc_info=True)
    raise

# Graceful degradation in workers
async def search_web(query: str) -> str:
    try:
        results = await duckduckgo_worker.search(query)
    except Exception as e:
        logger.warning(f"Web search failed: {e}")
        return "Search temporarily unavailable"
    return results
```

---

## Configuration

```python
from config import get_config

config = get_config()

# CORRECT: Use config manager
llm_provider = config.llm_provider
openai_key = config.openai_api_key
gemini_key = config.google_api_key

# WRONG: Direct os.environ (insecure)
import os
openai_key = os.environ["OPENAI_API_KEY"]  # Avoid
```

---

## Anti-Patterns (DO NOT USE)

```python
# ANTI-PATTERN 1: Direct LLM API calls in workers/API
from openai import OpenAI
client = OpenAI()
response = client.chat.completions.create(...)  # Use adapter instead

# ANTI-PATTERN 2: Blocking I/O in async functions
async def process_query(query: str):
    result = requests.get("http://api.example.com")  # Use aiohttp instead

# ANTI-PATTERN 3: Storing sensitive data in logs
logger.info(f"API Key: {api_key}")  # NEVER
logger.debug(f"Token: {jwt_token}")  # NEVER
```

---

## Development Commands

```bash
# Run server
uv run python main.py

# Testing
uv run pytest tests/ -v
uv run pytest tests/ -v --cov=src

# Code quality
uv run ruff check src/ tests/
uv run ruff format src/ tests/
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Import errors | Check `from src.xxx import yyy` relative paths |
| Port 8000 in use | `lsof -i :8000` then `kill -9 <PID>` |
| Test failures | `uv run pytest tests/ -v --tb=short` |
| Streaming not working | Check SSE headers and async generators |
| LLM API errors | Verify API keys in `.env` file |

---

## Code Review Checklist

Before submitting code:

- [ ] **Tests written** (mandatory - no tests = rejected)
- [ ] **Tests pass** (`uv run pytest tests/ -v`)
- [ ] **Loguru only** for logging (no print, no logging module)
- [ ] **Debug logs removed** (no `logger.debug()` left behind)
- [ ] Type hints on all functions
- [ ] LangGraph patterns followed (state, tools)
- [ ] No direct LLM API calls outside adapters
- [ ] Async/await for all I/O (LLM calls, web requests)
- [ ] Error handling for LLM failures
- [ ] No sensitive data in logs (API keys, tokens)
- [ ] Async generators for streaming (SSE)
- [ ] No hardcoded values (use config)
- [ ] Workers properly mocked in tests
- [ ] Memory management correct (context windows)
