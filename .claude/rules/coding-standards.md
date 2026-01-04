# Coding Standards - ai-librarian

## Mandatory Requirements

### Skill Invocation (BEFORE coding)

- Always run `/backend-guide` before writing or reviewing backend code.
- Invoke `/python-testing-patterns` when you add or modify tests.
- If you change LangGraph structures, also run `/architecture-patterns`.

Document which skills you invoked when reporting work; failure to invoke relevant skills is grounds for rejection.

### 0. No Lazy Imports (CRITICAL)

**ALL imports MUST be at the top of the file. Imports inside functions are STRICTLY FORBIDDEN.**

```python
# ❌ FORBIDDEN: Lazy imports inside functions
async def process_data():
    from ..domain.events import SomeEvent  # NEVER DO THIS
    from ..utils.helpers import helper_func  # NEVER DO THIS
    ...

# ✅ REQUIRED: All imports at file top level
from ..domain.events import SomeEvent
from ..utils.helpers import helper_func

async def process_data():
    ...
```

**Why:**
- Hard to track dependencies
- Circular import masking (fix the architecture instead)
- Inconsistent code style
- Performance overhead on each function call

**Only Exception:** `TYPE_CHECKING` block for type hints (this is standard Python):
```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..domain.entity import Entity  # OK for type hints only
```

### 1. Tests Are Required

**NO CODE WITHOUT TESTS. No exceptions. Code without tests = Trash code.**

**Test Commands:**
```bash
uv run --extra test pytest tests/ -v
uv run --group dev --extra test pytest tests/ --cov=src -v
```

**Test File Location:**
```
tests/
├── conftest.py              # Global fixtures
├── module_name/
│   ├── conftest.py         # Module-specific fixtures
│   ├── unit/
│   │   └── test_service.py
│   └── integration/
│       └── test_api.py
```

**Test Writing Rules:**

```python
import pytest
from unittest.mock import AsyncMock

# ✅ REQUIRED: Async tests (pytest-asyncio auto mode)
async def test_create_team():
    team = await team_service.create({"name": "Test Team"})
    assert team["name"] == "Test Team"

# ✅ REQUIRED: Mock dependencies
async def test_service_with_mock():
    mock_repo = AsyncMock(spec=TeamRepository)
    mock_repo.find_by_id.return_value = {"_id": "123", "name": "Test"}

    service = TeamService(repo=mock_repo)
    result = await service.get_team("123")

    assert result["name"] == "Test"
    mock_repo.find_by_id.assert_called_once_with("123")

# ✅ REQUIRED: Test edge cases
async def test_get_team_not_found():
    mock_repo = AsyncMock(spec=TeamRepository)
    mock_repo.find_by_id.return_value = None

    service = TeamService(repo=mock_repo)

    with pytest.raises(HTTPException) as exc_info:
        await service.get_team("nonexistent")
    assert exc_info.value.status_code == 404
```

**What Tests Must Cover:**

| Component | Test Requirements |
|-----------|-------------------|
| Repository | CRUD operations, edge cases |
| Service | Business logic, error handling, mock dependencies |
| Router | HTTP status codes, request validation, response format |

**Code Without Tests Will Be Rejected:**
```python
# ❌ REJECTED: No test file
async def new_feature():
    ...  # This is TRASH CODE

# ✅ ACCEPTED: With corresponding test
# src/module/services/feature_service.py
async def new_feature():
    ...

# tests/module/unit/test_feature_service.py
async def test_new_feature():
    result = await new_feature()
    assert result == expected
```

### 2. Logging: Loguru Only

**All debugging MUST use loguru. No print(), no logging module.**

```python
from loguru import logger

# ✅ REQUIRED: Use loguru
logger.debug(f"Processing user_id={user_id}")
logger.info(f"Created team: {team_id}")
logger.warning(f"Rate limit approaching: {count}/{limit}")
logger.error(f"Failed to process: {e}", exc_info=True)

# ❌ FORBIDDEN
print(f"Debug: {data}")                    # NEVER
import logging; logging.info(...)          # NEVER
```

**Log Levels:**

| Level | Use For | Keep/Remove |
|-------|---------|-------------|
| `debug` | Development debugging | **REMOVE after fix** |
| `info` | Important state changes | Keep |
| `warning` | Recoverable issues | Keep |
| `error` | Errors with stack traces | Keep |

### Debug Log Cleanup (MANDATORY)

**After resolving an issue, you MUST remove all debug logs.**

```python
# ❌ DEBUG LOGS LEFT BEHIND (REJECTED)
async def process_payment(payment_id: str):
    logger.debug(f"Starting payment: {payment_id}")  # DELETE THIS
    logger.debug(f"Payment data: {data}")            # DELETE THIS
    result = await billing_service.charge(...)
    logger.debug(f"Result: {result}")                # DELETE THIS
    return result

# ✅ CLEAN CODE (ACCEPTED)
async def process_payment(payment_id: str):
    result = await billing_service.charge(...)
    logger.info(f"Payment processed: payment_id={payment_id}")  # Keep info level
    return result
```

**Debug Cleanup Checklist:**
1. Problem resolved → Remove ALL `logger.debug()` statements
2. Search for `logger.debug` in modified files
3. Keep only `logger.info()`, `logger.warning()`, `logger.error()`
4. Commit message should NOT include debug log commits

### 3. Never Log Sensitive Data

```python
# ❌ NEVER
logger.info(f"Password: {password}")
logger.info(f"Token: {jwt_token}")
logger.info(f"API Key: {api_key}")

# ✅ CORRECT
logger.info(f"User logged in: user_id={user_id}")
logger.info(f"Payment processed: payment_id={payment_id}")
```

## Type Hints

**All functions must have type hints:**

```python
from typing import Dict, List, Optional, Any

# ✅ Required
async def get_team(team_id: str) -> Optional[Dict[str, Any]]:
    return await self.repo.find_by_id(team_id)

def calculate_usage(amount: int, limit: int) -> float:
    return (amount / limit) * 100 if limit > 0 else 0.0

# ❌ Rejected
async def get_team(team_id):  # No types = rejected
    return await self.repo.find_by_id(team_id)
```

## Pydantic for Validation

```python
from pydantic import BaseModel, Field, EmailStr

class TeamCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    limit: int = Field(default=500_000, ge=0)

    @validator('name')
    def validate_name(cls, v):
        if not v.strip():
            raise ValueError("팀 이름은 공백일 수 없습니다")
        return v.strip()
```

## Naming Conventions

### Variables and Functions: snake_case

```python
user_id: str
team_members: List[Dict]
async def get_active_members(team_id: str) -> List[Dict]:
```

### Classes: PascalCase

```python
class TeamRepository:
class UserService:
class SubscriptionModel:
```

### Constants: UPPER_SNAKE_CASE

```python
DEFAULT_LIMIT = 500_000
MAX_TEAM_SIZE = 100
CACHE_EXPIRE_SECONDS = 900
```

## Async/Await (CRITICAL for ai-librarian)

**All I/O operations must be async:**

```python
# ✅ Async for LLM/Network/Web calls
async def invoke_supervisor(query: str) -> str:
    response = await supervisor.invoke(query)  # Async call
    return response

# ❌ WRONG: Blocking synchronous call
def invoke_supervisor_sync(query: str) -> str:
    response = supervisor.invoke(query)  # Blocks event loop - NEVER
    return response

# ✅ Correct: Async generator for streaming
async def stream_supervisor_response(query: str):
    async for event in supervisor.invoke_streaming(query):
        yield f"data: {json.dumps(event)}\n\n"
```

## Supabase Memory Rules

- **AsyncClient Only**: Instantiate `supabase.AsyncClient` once (DI container or FastAPI lifespan) and pass it into the memory implementation. Never create clients per request.
- **`ChatMemory` Is Async**: All memory methods must be `async def` and awaited at call sites (supervisor, services). Mixing sync/async is forbidden.
- **Metadata Discipline**: Persist structured extras (tool outputs, token counts) in the `metadata` column instead of sprinkling extra tables/columns.
- **Testing**: Use `AsyncMock(spec=AsyncClient)` to stub `.table().select().eq().order().execute()` chains. Assert the expected filters/order/limit are applied.
- **Error Handling**: Catch Supabase HTTP/WebSocket errors, log context (session_id, operation) without dumping raw message content, and raise explicit domain exceptions for the supervisor.

## Error Handling

```python
# ✅ Handle LLM-specific errors
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

# ✅ Graceful degradation in workers
async def search_web(query: str) -> str:
    try:
        results = await duckduckgo_worker.search(query)
    except Exception as e:
        logger.warning(f"Web search failed: {e}")
        return "Search temporarily unavailable"
    return results
```

## Configuration

```python
from config import get_config

config = get_config()

# ✅ Use config manager
llm_provider = config.llm_provider
openai_key = config.openai_api_key
gemini_key = config.google_api_key

# ❌ Direct os.environ (insecure)
import os
openai_key = os.environ["OPENAI_API_KEY"]  # Avoid
```

## Documentation

```python
async def transfer_team_member(
    user_id: str,
    from_team_id: str,
    to_team_id: str
) -> Dict[str, Any]:
    """
    팀 멤버를 다른 팀으로 이전

    Args:
        user_id: 이전할 사용자 ID
        from_team_id: 현재 팀 ID
        to_team_id: 대상 팀 ID

    Returns:
        이전된 멤버 정보

    Raises:
        TeamNotFoundError: 팀을 찾을 수 없음
        UserNotFoundError: 사용자를 찾을 수 없음
    """
```

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
