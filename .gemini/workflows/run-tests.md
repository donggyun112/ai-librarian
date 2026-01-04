Run all tests for the ai-librarian project with verbose output.

```bash
uv run pytest tests/ -v
```

If tests fail, analyze the error and suggest fixes.

After fixing, run with coverage:
```bash
uv run pytest tests/ -v --cov=src
```
