"""FastAPI 서버 실행

Usage:
    uv run python main.py
    # or
    uv run uvicorn src.api:app --reload --host 0.0.0.0 --port 8000
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "src.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
