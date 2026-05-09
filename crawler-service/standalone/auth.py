"""API Key 认证中间件"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from config import settings


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """
    API Key 认证中间件。

    需要认证的路径：
      - /api/v1/* （独立模式管理 API）
      - /crawl/*  （爬取 API）
      - /organize （AI 整理）
      - /keyword  （AI 关键词处理）

    不需要认证的路径：
      - /health, /docs, /redoc, /openapi.json
    """

    # 不需要认证的路径前缀/精确匹配
    _PUBLIC_PATHS = ("/health", "/docs", "/redoc", "/openapi.json")

    def __init__(self, app, **kwargs):
        super().__init__(app, **kwargs)
        self._valid_keys = set()
        if settings.api_keys:
            self._valid_keys = {k.strip() for k in settings.api_keys.split(",") if k.strip()}
        # 从配置读取受保护路径前缀和认证头名称
        self._protected_prefixes = tuple(
            p.strip() for p in settings.auth_protected_prefixes.split(",") if p.strip()
        )
        self._header_name = settings.auth_header_name

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # 不需要认证的路径
        if (path == "/health" or
            path.startswith("/docs") or
            path.startswith("/redoc") or
            path.startswith("/openapi.json")):
            return await call_next(request)

        # 需要认证的路径
        needs_auth = any(path.startswith(prefix) for prefix in self._protected_prefixes)
        if needs_auth:
            api_key = request.headers.get(self._header_name, "")
            if not self._valid_keys or api_key not in self._valid_keys:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid or missing API key. Provide X-API-Key header."}
                )

        return await call_next(request)
