"""FastAPI 애플리케이션"""
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from fastapi.responses import JSONResponse

from config import config
from .routes import router
from src.auth import router as auth_router
from src.auth.utils import lifespan
from .books import router as books_router

# 앱 생성
app = FastAPI(
    title="AI Librarian",
    description="AI 기반 문서 검색 및 질의응답 서비스",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if not config.RATE_LIMIT_ENABLED:
        return await call_next(request)

    limiter = getattr(request.app.state, "rate_limiter", None)
    if limiter is None:
        return await call_next(request)

    # TODO: Replace in-memory limiter with shared store (e.g., Redis) for multi-worker deployments.
    window = config.RATE_LIMIT_WINDOW_SECONDS
    limit = config.RATE_LIMIT_REQUESTS
    key = request.client.host if request.client else "unknown"
    now = time.monotonic()

    async with limiter["lock"]:
        hits = limiter["hits"][key]
        while hits and (now - hits[0]) > window:
            hits.popleft()
        if len(hits) >= limit:
            return JSONResponse(status_code=429, content={"detail": "Too Many Requests"})
        hits.append(now)

    return await call_next(request)

# API 라우트 등록
app.include_router(router, prefix="/v1")
app.include_router(auth_router)
app.include_router(books_router)

# Static 파일 서빙 (UI)
static_dir = Path(__file__).parent.parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/")
    async def serve_ui():
        """메인 UI 페이지"""
        return FileResponse(static_dir / "index.html")
