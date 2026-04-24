"""统一配置管理（Pydantic Settings）"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 基础服务配置（两种模式共享）
    host: str = "0.0.0.0"
    port: int = 8500
    debug: bool = False
    log_level: str = "INFO"

    # 爬取限制（两种模式共享）
    max_pages_default: int = 10
    max_pages_limit: int = 20
    max_depth_limit: int = 3
    request_timeout: int = 60

    # 模式切换
    standalone: bool = False

    # 独立模式专用
    api_keys: str = ""
    auth_enabled: bool = True
    db_path: str = "data/crawler.db"
    export_dir: str = "exports"
    max_concurrent_tasks: int = 3

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
