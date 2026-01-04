Create a new LangGraph worker/tool.

1. Create worker file in `poc/src/workers/`:
```python
from langchain.tools import Tool

def create_<name>_tool() -> Tool:
    return Tool(
        name="<name>",
        description="<description>",
        func=<function>
    )
```

2. Register in supervisor at `poc/src/supervisor/`

3. Write tests in `tests/workers/`

4. Run tests:
```bash
uv run pytest tests/ -v
```
