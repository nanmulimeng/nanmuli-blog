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

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if not settings.auth_enabled:
            return await call_next(request)

        # 不需要认证的路径
        if (path == "/health" or
            path.startswith("/docs") or
            path.startswith("/redoc") or
            path.startswith("/openapi.json")):
            return await call_next(request)

        # 每次请求动态读取配置，确保配置更新后立即生效
        protected_prefixes = tuple(
            p.strip() for p in settings.auth_protected_prefixes.split(",") if p.strip()
        )
        needs_auth = any(path.startswith(prefix) for prefix in protected_prefixes)
        if needs_auth:
            valid_keys = set()
            if settings.api_keys:
                valid_keys = {k.strip() for k in settings.api_keys.split(",") if k.strip()}
            header_name = settings.auth_header_name
            api_key = request.headers.get(header_name, "")
            if not valid_keys or api_key not in valid_keys:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid or missing API key. Provide X-API-Key header."}
                )

        return await call_next(request)
