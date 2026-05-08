"""统一配置管理（Pydantic Settings）"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 基础服务配置（两种模式共享）
    host: str = "0.0.0.0"
    port: int = 8500
    debug: bool = False
    log_level: str = "INFO"

    # 爬取限制（两种模式共享）
    max_pages_limit: int = 20
    max_depth_limit: int = 3
    max_concurrent_crawls: int = 3

    # 模式切换
    standalone: bool = False

    # 独立模式专用
    api_keys: str = ""
    auth_enabled: bool = True
    db_path: str = "data/crawler.db"
    max_concurrent_tasks: int = 3

    # 代理配置（HTTP/HTTPS/SOCKS5）
    proxy_url: str = ""

    # 搜索去重配置
    max_domain_dedup: int = 2

    # AI 配置（独立模式 + AI 整理）
    ai_enabled: bool = False
    ai_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    ai_api_key: str = ""
    ai_model: str = "qwen-plus"
    ai_temperature: float = 0.3
    ai_connect_timeout: int = 10
    ai_read_timeout: int = 90
    ai_max_retries: int = 2
    ai_rate_limit_backoff_ms: int = 10000
    ai_single_page_max_chars: int = 80_000
    ai_multi_page_per_max_chars: int = 20_000
    ai_multi_page_total_budget: int = 150_000

    # 日报配置
    digest_enabled: bool = False
    digest_cron: str = "0 8 * * 1-5"  # 工作日 8:00
    digest_search_engine: str = "bing"  # 日报专用搜索引擎
    digest_sections: str = '[{"name":"news","keyword":"tech news","time_range":"day","max_items":5},{"name":"articles","keyword":"technology blog","time_range":"week","max_items":3},{"name":"opensource","keyword":"GitHub trending","time_range":"week","max_items":3}]'

    # 质量评估关键词（逗号分隔，可通过 .env 覆盖）
    quality_clickbait_keywords: str = "震惊,绝了,逆天,炸裂,颠覆,史诗,神级,99%的人不知道,看完我沉默了,后悔没早点,太可怕了,万万没想到,不可思议,惊人,史上最强,全网首发,独家揭秘,内幕,震惊中外,轰动,爆款,疯传,shocking,unbelievable,mind-blowing,epic,you won't believe,this changes everything"
    quality_ad_keywords: str = "限时优惠,点击购买,立即下单,免费试用,优惠券,折扣码,推广链接,affiliate,赞助内容,广告合作,扫码领取,关注公众号,限量,秒杀,抢购,不容错过,错过等一年"
    quality_paywall_indicators: str = "subscribe to read,membership required,premium content,登录后阅读,订阅后查看,会员专属,付费阅读,sign up to continue,create an account"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
