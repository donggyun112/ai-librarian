# Architecture Rules - ai-librarian

## Overall Architecture

The ai-librarian project implements a **LangGraph ReAct Agent** pattern:

```
API Layer (FastAPI)
    ↓
Supervisor (LangGraph State Graph)
    ↓
Workers (Tools) → Adapters (LLM providers)
    ↓
Memory (Supabase Conversation Store)
```

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

## Mandatory Skill Invocation

Before touching architecture, LangGraph, or worker/adapter code:

- Run `/backend-guide` to refresh global backend guardrails.
- Run `/architecture-patterns` to load the canonical LangGraph, worker, and adapter patterns.
- Summarize the skill output and follow every checklist item prior to coding or drafting delegations.

Skipping these skills is a rule violation.

## Memory Layer (Supabase-Backed)

- **Single Source of Truth**: All conversation turns are persisted to Supabase Postgres via the async `supabase-py` client (`supabase.AsyncClient`). No in-memory dicts outside tests.
- **Dedicated Repository**: Put the Supabase implementation under `src/memory/supabase.py` (or similar) implementing `ChatMemory`. Every method becomes `async` because of I/O.
- **Dependency Injection**: Wire the memory instance during FastAPI startup (e.g., `lifespan`) and pass it into the supervisor. Workers never touch Supabase directly.
- **Session Management**: API layer generates/receives `session_id` and hands it down. Supervisor loads context with `await memory.get_messages(session_id)` before running LangGraph.
- **Cleanup**: Schedule TTL cleanup (CRON/BG task) that calls the Supabase delete query defined in `database.md`.

```python
from supabase import AsyncClient, create_client
from src.memory.supabase import SupabaseChatMemory

async def lifespan(app: FastAPI):
    supabase: AsyncClient = create_client(config.supabase_url, config.supabase_key, AsyncClient)
    memory = SupabaseChatMemory(client=supabase)
    supervisor = create_supervisor(memory=memory, adapter=adapter_factory())
    app.state.supervisor = supervisor
    yield
```

## LangGraph Patterns (MANDATORY)

**All LangGraph integrations must follow these patterns:**

```python
# ✅ CORRECT: LangGraph state
from langgraph.graph import StateGraph, START, END

class AgentState(TypedDict):
    query: str
    messages: List[BaseMessage]
    steps: List[str]
    final_response: str

# ✅ CORRECT: Tool definition
def create_search_tool() -> Tool:
    return Tool(name="search", func=search_function, ...)

# ❌ ANTI-PATTERN: Hardcoded LLM calls outside adapters
from openai import OpenAI
client = OpenAI()  # WRONG - use adapter instead
```

## Anti-Patterns (DO NOT USE)

**NEVER create code with these patterns:**

```python
# ❌ ANTI-PATTERN 1: Direct LLM API calls in workers/API
from openai import OpenAI
client = OpenAI()
response = client.chat.completions.create(...)  # Use adapter instead

# ❌ ANTI-PATTERN 2: Blocking I/O in async functions
async def process_query(query: str):
    result = requests.get("http://api.example.com")  # Use aiohttp instead

# ❌ ANTI-PATTERN 3: Storing sensitive data in logs
logger.info(f"API Key: {api_key}")  # NEVER
logger.debug(f"Token: {jwt_token}")  # NEVER
```

## FastAPI Integration with LangGraph

**FastAPI should act as a thin wrapper around LangGraph:**

```python
# ✅ CORRECT: API routes call supervisor
from src.supervisor import create_supervisor

supervisor = create_supervisor()

@router.post("/api/query")
async def query_endpoint(request: QueryRequest):
    # Stream response via SSE
    async def event_generator():
        async for event in supervisor.invoke(request.query):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

## SSE Streaming (REQUIRED)

**All long-running operations must use SSE streaming:**

```python
from fastapi.responses import StreamingResponse

async def stream_supervisor_response(query: str):
    async for event in supervisor.invoke(query):
        # Stream each event
        yield f"data: {json.dumps({'type': 'event', 'data': event})}\n\n"
        await asyncio.sleep(0)  # Allow cancellation

@router.post("/api/query", response_class=StreamingResponse)
async def query(request: QueryRequest):
    return StreamingResponse(
        stream_supervisor_response(request.query),
        media_type="text/event-stream"
    )
```

## LLM Adapter Pattern (MANDATORY)

**All LLM calls must go through adapters:**

```python
# ✅ CORRECT: Adapter abstraction
class LLMAdapter:
    async def invoke(self, messages: List[BaseMessage]) -> str:
        # Provider-specific implementation
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
