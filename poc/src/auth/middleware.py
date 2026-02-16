"""전역 인증 미들웨어

모든 요청에 대해 JWT 토큰을 검증하고,
인증된 사용자 정보를 request.state.user에 저장합니다.
Public 엔드포인트는 화이트리스트로 제외됩니다.
"""
from typing import List

from fastapi import Request, status
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response


# 인증 불필요한 엔드포인트
PUBLIC_PATHS: List[str] = [
    "/health",
    "/v1/health",
    "/docs",
    "/redoc",
    "/openapi.json",
]

# 정적 파일 접두사
PUBLIC_PREFIXES: List[str] = [
    "/static/",
    "/_next/",
]


class AuthMiddleware(BaseHTTPMiddleware):
    """Supabase JWT 인증 미들웨어

    모든 요청에 대해 Authorization: Bearer <token> 헤더를 확인합니다.
    Public 엔드포인트를 제외한 모든 요청에 인증을 요구합니다.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # OPTIONS (CORS preflight)는 패스
        if request.method == "OPTIONS":
            return await call_next(request)

        # Public 엔드포인트 체크
        path = request.url.path
        if self._is_public(path):
            return await call_next(request)

        # Authorization 헤더 추출
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Not authenticated"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = auth_header.removeprefix("Bearer ").strip()
        if not token:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Not authenticated"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Supabase로 토큰 검증
        supabase_client = getattr(request.app.state, "supabase", None)
        if not supabase_client:
            logger.error("Supabase client not initialized")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Authentication service unavailable"},
            )

        try:
            response = await supabase_client.auth.get_user(token)
            if not response or not response.user:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Invalid authentication credentials"},
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # request.state에 사용자 정보 저장
            request.state.user = response.user
            request.state.token = token

        except Exception as e:
            logger.error(f"Token verification failed: {type(e).__name__}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Could not validate credentials"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        return await call_next(request)

    @staticmethod
    def _is_public(path: str) -> bool:
        """Public 엔드포인트 여부 확인"""
        # 정확히 일치하는 경로
        if path in PUBLIC_PATHS:
            return True

        # 접두사 매칭 (auth, static 등)
        for prefix in PUBLIC_PATHS:
            if path.startswith(prefix):
                return True

        for prefix in PUBLIC_PREFIXES:
            if path.startswith(prefix):
                return True

        return False
