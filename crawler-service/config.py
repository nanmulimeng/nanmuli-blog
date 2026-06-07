"""统一配置管理（Pydantic Settings）"""

from pydantic import model_validator
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

    # 外部爬虫依赖兼容策略
    # degraded: Crawl4AI 不可用时服务仍启动，健康检查标记 crawler unavailable，具体爬取任务失败但不影响其他模块。
    # strict: 依赖不可用时启动失败，适合生产强依赖部署前置检查。
    crawler_dependency_mode: str = "degraded"

    # 质量过滤阈值
    min_content_length: int = 100          # 低于此字符数的页面视为低质量

    # 关键词搜索策略
    keyword_max_consecutive_empty: int = 2  # 连续 N 个关键词无新结果时停止
    keyword_max_variants: int = 4           # AI 扩展关键词最大变体数
    keyword_inter_search_delay: float = 2.0 # 多关键词搜索间隔（秒）

    # 日报配置
    digest_section_result_multiplier: int = 2  # 每个板块搜索结果 = max_items * 此值
    digest_inter_section_delay: float = 2.0    # 板块间搜索间隔（秒）
    digest_history_load_count: int = 3         # 加载最近 N 期日报用于去重

    # 外部服务调用超时
    callback_timeout: float = 5.0              # 回调超时（秒）
    sources_api_timeout: float = 5.0           # 外部订阅源 API 超时（秒）

    # 模式切换（已移除，统一为全功能模式）
    # standalone: bool = False  # REMOVED: Phase 3 统一架构

    # 任务服务配置
    api_keys: str = ""
    auth_enabled: bool = True
    db_path: str = "data/crawler.db"
    max_concurrent_tasks: int = 3

    # 代理配置（HTTP/HTTPS/SOCKS5）
    proxy_url: str = ""

    # 搜索去重配置
    max_domain_dedup: int = 2

    # 搜索模块超时配置
    search_page_timeout_ms: int = 15000        # 搜索结果页默认超时
    search_browser_fetch_timeout_ms: int = 20000  # 浏览器抓取超时
    search_httpx_fallback_timeout: int = 15    # httpx 降级超时
    search_client_timeout: int = 30            # 共享搜索客户端超时
    search_warmup_timeout: int = 10            # 搜狗预热超时
    search_page_retries: int = 2               # 搜索页获取重试次数
    search_max_pages_per_engine: int = 5       # 每个搜索引擎最大翻页数
    search_min_word_count: int = 50            # 搜索结果最小词数

    # 搜索引擎延迟配置
    search_engine_switch_delay_min: float = 2.0
    search_engine_switch_delay_max: float = 5.0
    search_page_delay_min: float = 0.8
    search_page_delay_max: float = 2.0
    search_crawl_deadline_seconds: int = 300     # 整体爬取超时（秒），超时返回部分结果
    search_progressive_fallback_enabled: bool = True  # Progressive fit/raw 回退
    optimization_round_delay_min: float = 2.0
    optimization_round_delay_max: float = 4.0

    # 质量评估配置
    quality_source_weight: float = 0.4         # 来源可信度权重
    quality_content_weight: float = 0.6        # 内容质量权重
    quality_keep_threshold: int = 70           # 质量推荐：保留阈值
    quality_review_threshold: int = 50         # 质量推荐：审查阈值
    eval_pass_threshold: int = 65              # 综合评分：通过阈值
    eval_review_threshold: int = 45            # 综合评分：审查阈值
    deep_eval_review_threshold: int = 25       # 深度爬取综合评分：审查阈值（更宽松，域内页面默认可信）

    # 评估维度权重
    eval_weight_angle: float = 0.25
    eval_weight_source: float = 0.20
    eval_weight_depth: float = 0.15
    eval_weight_temporal: float = 0.15
    eval_weight_perspective: float = 0.15
    eval_weight_language: float = 0.10

    # 认证配置
    auth_protected_prefixes: str = "/api/v1,/crawl,/organize,/keyword"
    auth_header_name: str = "X-API-Key"

    # SQLite 配置
    db_busy_timeout: int = 5000               # SQLite busy_timeout (ms)

    # AI 配置
    ai_enabled: bool = False
    ai_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    ai_api_key: str = ""
    ai_model: str = "qwen-plus"
    ai_temperature: float = 0.3
    ai_connect_timeout: int = 10
    ai_read_timeout: int = 90
    ai_section_cleanup_timeout: int = 90       # 栏目清洗独立超时；真实模型清洗多页内容常超过 30s
    ai_max_retries: int = 2
    ai_rate_limit_backoff_ms: int = 10000
    ai_single_page_max_chars: int = 80_000
    ai_multi_page_per_max_chars: int = 20_000
    ai_multi_page_total_budget: int = 150_000
    ai_max_tokens: int = 8000                  # AI 调用最大输出 tokens
    ai_section_cleanup_per_max_chars: int = 6000   # 栏目清洗单来源输入上限
    ai_section_cleanup_total_budget: int = 24000   # 栏目清洗总输入上限
    ai_section_cleanup_max_output_chars: int = 1200 # 栏目清洗单来源输出上限，避免 JSON 被截断
    ai_min_summary_length: int = 10            # 摘要最小长度
    ai_min_full_content_length: int = 20       # 全文最小长度
    ai_max_key_points: int = 10                # 最大要点数
    ai_max_tags: int = 10                      # 最大标签数
    # Digest 专用 AI 参数
    ai_digest_per_max_chars: int = 8000        # 日报每页输入上限（低于普通多页的 20K）
    ai_digest_total_budget: int = 100_000      # 日报总输入预算（低于普通多页的 150K）
    ai_digest_max_tokens: int = 16_000         # 日报输出上限（5板块+多个条目需要更多空间）

    # 日报配置
    digest_enabled: bool = False
    digest_cron: str = "0 8 * * 1-5"  # 工作日 8:00
    digest_search_engine: str = "sogou"  # 日报专用搜索引擎（sogou 对中文技术内容搜索效果好于 bing）
    digest_sections: str = (
        '[{"name":"hot_trend","keyword":"技术新闻 OR 科技资讯 OR 今日热点 OR 版本发布 OR 人工智能 OR 大模型 OR LLM OR 深度学习 OR AI agent","time_range":"week","max_items":6},'
        '{"name":"open_source","keyword":"开源项目 OR 最新发布 OR 热门仓库 OR GitHub trending","time_range":"week","max_items":4},'
        '{"name":"dev_tool","keyword":"开发工具 OR IDE OR 插件 OR 编程工具 OR VS Code","time_range":"week","max_items":3},'
        '{"name":"tech_article","keyword":"技术博客 OR 教程 OR 最佳实践 OR 深度解析 OR 源码分析","time_range":"week","max_items":3}]'
    )
    digest_parallel_sections: int = 2  # 板块并行爬取上限
    digest_global_timeout: int = 600  # 板块并行总时限（秒），超时返回已有结果

    # 回调配置（任务完成后通知调用方）
    callback_url: str = ""
    callback_api_key: str = ""  # 与 Java 端 crawler.callback.api-key 一致
    callback_allow_private_urls: bool = False  # 任务级 callback 默认禁止内网地址，避免 SSRF

    # Java 后端地址（用于拉取订阅源配置，为空则使用本地配置）
    java_api_url: str = ""

    # 自动优化引擎配置
    optimization_enabled: bool = False
    optimization_target_score: float = 0.7  # deprecated: 展示用，实际使用 depth/breadth target
    optimization_max_rounds: int = 3       # 深度优化独立预算
    optimization_min_improvement: float = 0.03
    optimization_mode: str = "both"  # keyword / digest / both — 默认启用所有任务类型的优化
    breadth_max_rounds: int = 3            # 广度扩展独立预算
    optimization_total_budget_seconds: int = 120  # 优化总时间预算（秒）
    # 深度子循环内部权重（三者之和应为 1.0）
    optimization_depth_weight_primary: float = 0.4      # depth 维度
    optimization_depth_weight_secondary: float = 0.35   # angle 维度
    optimization_depth_weight_tertiary: float = 0.25    # temporal 维度
    # 广度子循环内部权重（三者之和应为 1.0）
    optimization_breadth_weight_primary: float = 0.4    # source_diversity 维度
    optimization_breadth_weight_secondary: float = 0.35 # perspective 维度
    optimization_breadth_weight_tertiary: float = 0.25  # language 维度
    # 子循环独立达标线（启发式回退评分保守，目标稍高以触发多轮优化）
    optimization_depth_target_score: float = 0.7
    optimization_breadth_target_score: float = 0.7

    # 信息茧房突破配置
    bubble_breaker_enabled: bool = False
    bubble_min_source_diversity: float = 0.6
    bubble_cross_language: bool = True
    bubble_max_translate_tokens: int = 200

    # 质量评估关键词（逗号分隔，可通过 .env 覆盖）
    quality_clickbait_keywords: str = "震惊,绝了,逆天,炸裂,颠覆,史诗,神级,99%的人不知道,看完我沉默了,后悔没早点,太可怕了,万万没想到,不可思议,惊人,史上最强,全网首发,独家揭秘,内幕,震惊中外,轰动,爆款,疯传,shocking,unbelievable,mind-blowing,epic,you won't believe,this changes everything"
    quality_ad_keywords: str = "限时优惠,点击购买,立即下单,免费试用,优惠券,折扣码,推广链接,affiliate,赞助内容,广告合作,扫码领取,关注公众号,限量,秒杀,抢购,不容错过,错过等一年"
    quality_paywall_indicators: str = "subscribe to read,membership required,premium content,登录后阅读,订阅后查看,会员专属,付费阅读,sign up to continue,create an account"

    # === 过滤管线优化配置（P1-P6）===
    ai_organization_enabled: bool = True         # AI 整理开关
    page_classifier_enabled: bool = True         # P5: 页面类型分类器
    content_dedup_enabled: bool = True           # P6: 内容去重
    content_dedup_simhash_threshold: int = 5     # 汉明距离阈值（越小越严）
    content_dedup_deep_threshold: int = 3        # 深度爬取更严阈值
    filter_deep_min_content: int = 20            # 深度爬取最小内容长度
    filter_skip_header_chars: int = 200          # 去重指纹跳过头部字符数
    filter_content_preview_length: int = 800     # 去重指纹预览长度

    # 日报质量过滤与优化专用配置
    digest_filter_min_content: int = 50          # 日报质量过滤最小内容长度（比通用宽松）
    digest_eval_reject_threshold: int = 40       # 日报质量评分低于此值直接拒绝（不浪费 AI token）
    digest_optimization_enabled: bool = False     # 日报优化独立开关（需 optimization_enabled=True + 此项=True）
    digest_optimization_min_sections: int = 2     # 最少板块数才触发优化
    digest_optimization_min_results_per_section: int = 3  # 每板块最少结果数才触发优化
    digest_optimization_target_score: float = 0.65  # 日报优化目标分（比通用 0.7 稍低）

    model_config = {"env_file": ".env", "extra": "ignore"}

    @model_validator(mode="after")
    def _validate_weight_sums(self):
        assert self.crawler_dependency_mode in ("degraded", "strict"), (
            "crawler_dependency_mode must be degraded or strict"
        )
        depth_sum = (
            self.optimization_depth_weight_primary
            + self.optimization_depth_weight_secondary
            + self.optimization_depth_weight_tertiary
        )
        assert abs(depth_sum - 1.0) < 0.02, (
            f"optimization_depth_weight_* must sum to 1.0, got {depth_sum:.2f}"
        )
        breadth_sum = (
            self.optimization_breadth_weight_primary
            + self.optimization_breadth_weight_secondary
            + self.optimization_breadth_weight_tertiary
        )
        assert abs(breadth_sum - 1.0) < 0.02, (
            f"optimization_breadth_weight_* must sum to 1.0, got {breadth_sum:.2f}"
        )
        eval_sum = (
            self.eval_weight_angle + self.eval_weight_source + self.eval_weight_depth
            + self.eval_weight_temporal + self.eval_weight_perspective
            + self.eval_weight_language
        )
        assert abs(eval_sum - 1.0) < 0.02, (
            f"eval_weight_* must sum to 1.0, got {eval_sum:.2f}"
        )
        return self


settings = Settings()
