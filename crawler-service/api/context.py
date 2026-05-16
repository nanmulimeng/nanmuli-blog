"""共享请求上下文（用于日志 Request-ID 传播）"""
import contextvars

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")
