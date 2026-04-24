"""API Key 认证中间件"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from config import settings


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """
    仅对 /api/v1/* 路径生效的 API Key 认证。
    /crawl/*, /health, /docs, /redoc, /openapi.json 不认证。
    """

    def __init__(self, app, **kwargs):
        super().__init__(app, **kwargs)
        self._valid_keys = set()
        if settings.api_keys:
            self._valid_keys = {k.strip() for k in settings.api_keys.split(",") if k.strip()}

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # 不需要认证的路径
        if (path.startswith("/crawl/") or
            path == "/health" or
            path.startswith("/docs") or
            path.startswith("/redoc") or
            path.startswith("/openapi.json")):
            return await call_next(request)

        # 独立模式管理 API 需要认证
        if path.startswith("/api/v1"):
            api_key = request.headers.get("X-API-Key", "")
            if not self._valid_keys or api_key not in self._valid_keys:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid or missing API key. Provide X-API-Key header."}
                )

        return await call_next(request)
