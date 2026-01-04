# Coding Standards - ai-librarian

## Mandatory Requirements

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

Only Exception: `TYPE_CHECKING` block for type hints.

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

After resolving issues, REMOVE all `logger.debug()` statements.

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

## Async/Await (CRITICAL)

All I/O operations must be async:

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

## Configuration

```python
from config import get_config

config = get_config()

# CORRECT: Use config manager
llm_provider = config.llm_provider
openai_key = config.openai_api_key

# WRONG: Direct os.environ
import os
openai_key = os.environ["OPENAI_API_KEY"]  # Avoid
```

## Code Review Checklist

Before submitting code:

- [ ] Tests written (mandatory)
- [ ] Tests pass (`uv run pytest tests/ -v`)
- [ ] Loguru only for logging
- [ ] Debug logs removed
- [ ] Type hints on all functions
- [ ] LangGraph patterns followed
- [ ] No direct LLM API calls outside adapters
- [ ] Async/await for all I/O
- [ ] Error handling for LLM failures
- [ ] No sensitive data in logs
- [ ] Async generators for streaming
- [ ] No hardcoded values
