# Architecture Rules - ai-librarian

## Overall Architecture

The ai-librarian project implements a **LangGraph ReAct Agent** pattern:

```
API Layer (FastAPI)
    |
    v
Supervisor (LangGraph State Graph)
    |
    v
Workers (Tools) -> Adapters (LLM providers)
    |
    v
Memory (Conversation History)
```

## Module Structure

Always use this structure for new modules:

```
poc/src/module_name/
├── __init__.py           # Module exports
├── schemas.py            # Pydantic models (Request/Response)
├── worker.py             # Worker/Tool implementation (if tool)
├── adapter.py            # Adapter implementation (if LLM provider)
└── utils.py              # Module utilities (optional)
```

For API endpoints:
```
poc/src/api/
├── __init__.py           # FastAPI app initialization
├── routers/
│   └── query_router.py   # Query endpoints
└── schemas.py            # Request/response models
```

Reference implementations:
- Worker: `poc/src/workers/`
- Adapter: `poc/src/adapters/`
- API: `poc/src/api/`

## LangGraph Patterns (MANDATORY)

All LangGraph integrations must follow these patterns:

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

## LLM Adapter Pattern (MANDATORY)

All LLM calls must go through adapters:

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

## SSE Streaming (REQUIRED)

All long-running operations must use SSE streaming:

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
```
