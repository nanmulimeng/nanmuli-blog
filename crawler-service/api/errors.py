"""全局异常处理器（分级处理）+ 结构化错误码 + RequestID"""

import logging
import uuid
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from config import settings

logger = logging.getLogger(__name__)


# ============== 结构化错误码 ==============

class AppError(Exception):
    """业务错误基类，携带 code + status"""

    def __init__(self, code: str, message: str, status: int = 400):
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)

    def to_dict(self, request_id: str | None = None) -> dict:
        d = {"success": False, "code": self.code, "message": self.message}
        if request_id:
            d["request_id"] = request_id
        return d


# 预定义错误工厂
def crawl_timeout(msg: str = "爬取超时") -> AppError:
    return AppError("CRAWL_TIMEOUT", msg, 504)


def ai_rate_limited(msg: str = "AI 服务限流") -> AppError:
    return AppError("AI_RATE_LIMITED", msg, 429)


def ai_not_configured(msg: str = "AI 未配置") -> AppError:
    return AppError("AI_NOT_CONFIGURED", msg, 503)


def task_not_found(msg: str = "任务不存在") -> AppError:
    return AppError("TASK_NOT_FOUND", msg, 404)


def task_not_terminal(msg: str = "任务未完成") -> AppError:
    return AppError("TASK_NOT_TERMINAL", msg, 400)


def invalid_url(msg: str = "无效 URL") -> AppError:
    return AppError("INVALID_URL", msg, 400)


def search_blocked(msg: str = "搜索引擎反爬") -> AppError:
    return AppError("SEARCH_BLOCKED", msg, 503)


# ============== Request ID Middleware ==============

def _get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")


async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex[:12])
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


def register_request_id_middleware(app: FastAPI):
    app.middleware("http")(request_id_middleware)


# ============== 异常处理器 ==============

def register_error_handlers(app: FastAPI):
    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        errors = exc.errors()
        message = ". ".join(
            f"{'.'.join(str(l) for l in e.get('loc', []))}: {e.get('msg', '')}"
            for e in errors[:3]
        )
        logger.debug("Validation error: %s", message)
        rid = _get_request_id(request)
        content = {"success": False, "code": "VALIDATION_ERROR", "message": message}
        if rid:
            content["request_id"] = rid
        if settings.debug:
            content["detail"] = str(exc)
        return JSONResponse(status_code=422, content=content)

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        rid = _get_request_id(request)
        return JSONResponse(status_code=exc.status, content=exc.to_dict(rid))

    @app.exception_handler(HTTPException)
    async def http_handler(request: Request, exc: HTTPException):
        rid = _get_request_id(request)
        content = {"success": False, "code": "HTTP_ERROR", "message": str(exc.detail)}
        if rid:
            content["request_id"] = rid
        return JSONResponse(status_code=exc.status_code, content=content)

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        rid = _get_request_id(request)
        logger.error("Unhandled exception [%s]: %s %s", rid, request.method, request.url.path, exc_info=True)
        content = {"success": False, "code": "INTERNAL_ERROR", "message": "Internal server error"}
        if rid:
            content["request_id"] = rid
        if settings.debug:
            content["detail"] = str(exc)
        return JSONResponse(status_code=500, content=content)
