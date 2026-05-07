"""AI configuration from environment variables."""

import os
from pydantic_settings import BaseSettings


class AiSettings(BaseSettings):
    ai_enabled: bool = False
    ai_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    ai_api_key: str = ""
    ai_model: str = "qwen-plus"
    ai_temperature: float = 0.3
    ai_connect_timeout: int = 10
    ai_read_timeout: int = 90
    ai_max_retries: int = 2
    ai_rate_limit_backoff_ms: int = 10000

    # Content budget (chars)
    ai_single_page_max_chars: int = 80_000
    ai_multi_page_per_max_chars: int = 20_000
    ai_multi_page_total_budget: int = 150_000

    @property
    def is_configured(self) -> bool:
        return (
            self.ai_enabled
            and bool(self.ai_api_key)
            and bool(self.ai_base_url)
            and bool(self.ai_model)
        )

    model_config = {"env_file": ".env", "extra": "ignore"}


ai_settings = AiSettings()
