"""OpenAI-compatible content organizer.

Migrated from Java OpenAiCompatibleOrganizer with identical prompts and logic.
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
import httpx

from .config import AiSettings, ai_settings

logger = logging.getLogger(__name__)

# ============== Constants ==============

MIN_SUMMARY_LENGTH = 10
MIN_FULL_CONTENT_LENGTH = 20
MAX_KEY_POINTS = 10
MAX_TAGS = 10

ALLOWED_CATEGORIES = {
    "后端开发", "前端开发", "移动开发", "数据库", "DevOps",
    "云计算", "AI与机器学习", "安全", "区块链", "其他",
}

CATEGORY_ALIASES = {
    "backend": "后端开发",
    "frontend": "前端开发",
    "mobile": "移动开发",
    "database": "数据库",
    "devops": "DevOps",
    "cloud": "云计算",
    "ai": "AI与机器学习",
    "ai/ml": "AI与机器学习",
    "machine learning": "AI与机器学习",
    "security": "安全",
    "blockchain": "区块链",
    "other": "其他",
}

DIGEST_CATEGORY_MAP = {
    "hot_trend": ("热点动态", "🔥"),
    "open_source": ("开源项目", "🌟"),
    "tech_article": ("技术文章", "📖"),
    "dev_tool": ("开发工具", "🔧"),
    "creative": ("创意发现", "💡"),
    "paper": ("学术论文", "📄"),
}

# ============== Prompts (identical to Java) ==============

SYSTEM_PROMPT = """你是一位资深技术内容编辑，擅长从网页原始内容中提取核心信息并重组为高质量中文技术文章。
## 输出规则
1. 严格输出 JSON，不要包裹在 markdown 代码块中
2. fullContent 使用 Markdown 格式，代码块使用 ```language 标记，正文 1000-5000 字
3. 保留原文中有价值的代码示例和技术细节，不要丢弃关键信息
4. 英文内容翻译为中文，保留专有名词原文（如 React、Kubernetes、gRPC）
5. tags 必须是具体技术关键词，3-7 个，避免\"技术\"\"编程\"等过泛标签
6. category 必须是以下之一：后端开发、前端开发、移动开发、数据库、DevOps、云计算、AI与机器学习、安全、区块链、其他
7. 如果输入不是有效技术内容（登录页、错误页、空白页、广告页），将 summary 设为"该页面不包含有效技术内容"，其他字段留空
8. 忽略导航菜单、Cookie 提示、评论区、分享按钮、广告、侧边栏等与正文无关的内容
9. keyPoints 应提炼可操作的技术要点，而非泛泛描述"""

OUTPUT_SCHEMA = """
## 输出格式（严格 JSON）
{
  "title": "中文标题，15-30字，突出核心主题",
  "summary": "200-400字核心摘要，涵盖背景、方法、结论",
  "keyPoints": ["技术要点1（具体可操作）", "技术要点2", "技术要点3", "..."],
  "tags": ["具体技术关键词1", "关键词2"],
  "category": "后端开发|前端开发|移动开发|数据库|DevOps|云计算|AI与机器学习|安全|区块链|其他",
  "fullContent": "完整 Markdown 格式技术文章（保留代码示例和关键配置）"
}"""

FEW_SHOT_EXAMPLE = """
## 输出示例
{
  "title": "Spring Boot 3 优雅停机配置详解与实践",
  "summary": "Spring Boot 3 引入了内置的优雅停机机制，通过 server.shutdown=graceful 配置即可让 Web 服务器在关闭时拒绝新请求并等待正在处理的请求完成。结合 SmartLifecycle 接口可实现线程池、数据库连接等资源的有序释放。在 Kubernetes 环境中，还需配合 terminationGracePeriodSeconds 和 preStop 钩子确保流量完全排空后才终止 Pod。",
  "keyPoints": [
    "通过 server.shutdown=graceful 开启优雅停机，默认等待 30s",
    "实现 SmartLifecycle 接口自定义资源释放顺序（先关线程池再关连接）",
    "Kubernetes 需配合 terminationGracePeriodSeconds 和 preStop hook",
    "Spring Boot 3.2+ 支持 Adaptive	为不同 Web 服务器自动配置最优停机策略"
  ],
  "tags": ["Spring Boot 3", "优雅停机", "Kubernetes", "微服务部署"],
  "category": "后端开发",
  "fullContent": "## Spring Boot 3 优雅停机\\n\\n### 开启优雅停机\\n\\n在 application.yml 中配置：\\n\\n```yaml\\nserver:\\n  shutdown: graceful\\nspring:\\n  lifecycle:\\n    timeout-per-shutdown-phase: 30s\\n```\\n\\n启用后，应用关闭时 Web 服务器会拒绝新的请求，并等待正在处理的请求完成。\\n\\n### 自定义资源释放\\n\\n实现 SmartLifecycle 接口，按顺序释放资源。"
}"""

DIGEST_SYSTEM_PROMPT = """你是一位资深技术资讯编辑，负责生成每日技术日报。
## 任务
根据提供的多个来源内容，生成一份结构清晰、信息密度高的中文技术日报。
## 输出规则
1. 严格输出 JSON，不要包裹在 markdown 代码块中
2. fullContent 使用 Markdown 格式，包含标题、列表和链接
3. 每个条目用一句话提炼核心信息（是谁做了什么、有什么影响、对开发者意味着什么）
4. 对同一事件的多次报道合并为一条，优先保留信息最完整的来源
5. 使用中文表达，保留技术专有名词原文（如 React 19、Claude 4、Rust 2024）
6. tags 使用具体技术关键词，5-10 个
7. highlight 应选取对开发者影响最大的事件，100字内说明影响
## 输出格式
{
  "title": "技术日报 | YYYY-MM-DD",
  "summary": "200-400 字今日概要，涵盖最重要的 3-5 件事",
  "sections": [
    {
      "category": "分类代码",
      "categoryName": "分类显示名",
      "emoji": "emoji",
      "items": [
        {
          "title": "事件标题",
          "oneLiner": "一句话核心信息（含影响/意义）",
          "sourceUrl": "原文链接",
          "sourceName": "来源域名"
        }
      ]
    }
  ],
  "highlight": "今日最值得关注的一条（含对开发者的影响）",
  "tags": ["标签1", "标签2"],
  "fullContent": "完整 Markdown 日报正文"
}

## 分类代码对照
- hot_trend -> 热点动态 -> 🔥（行业新闻、版本发布、重大事件）
- open_source -> 开源项目 -> 🌟（GitHub trending、新项目、重要更新）
- tech_article -> 技术文章 -> 📖（深度教程、原理分析、最佳实践）
- dev_tool -> 开发工具 -> 🔧（IDE、CLI、CI/CD、新工具发布）
- creative -> 创意发现 -> 💡（有趣项目、创意应用、跨界结合）
- paper -> 技术论文 -> 📄（arXiv、学术研究、技术白皮书）

## 输出示例
{
  "title": "技术日报 | 2026-05-08",
  "summary": "今日技术圈最值得关注：React 19 正式发布带来 Server Components 稳定版；Bun 1.2 性能再创新高，原生支持 S3 API；一篇深度解析 Linux 内核调度的文章引发广泛讨论。",
  "sections": [
    {
      "category": "hot_trend",
      "categoryName": "热点动态",
      "emoji": "🔥",
      "items": [
        {
          "title": "React 19 正式发布",
          "oneLiner": "Server Components 稳定版上线，use() hook 简化异步数据获取，对现有项目升级影响较大",
          "sourceUrl": "https://react.dev/blog/react-19",
          "sourceName": "react.dev"
        }
      ]
    }
  ],
  "highlight": "React 19 正式发布，Server Components 进入稳定阶段，前端开发者需要评估现有项目的迁移成本",
  "tags": ["React 19", "Bun", "Linux内核", "性能优化"],
  "fullContent": "# 技术日报 | 2026-05-08\\n\\n## 热点动态\\n\\n### React 19 正式发布\\nServer Components 稳定版上线..."
}"""

TEMPLATE_PROMPTS = {
    "tech_summary": {
        "single": "请对以下网页内容进行深度阅读和结构化整理。\n重点：提炼核心技术要点，梳理逻辑脉络，补充必要的背景说明，输出一篇结构清晰、可直接用于技术博客的文章。",
        "multi": "以下是从多个来源收集的技术内容，请综合分析后输出一篇结构化技术摘要。\n重点：提炼各来源的共识观点，合并重复信息，保留互补细节（如不同方案的代码示例），标注信息来源差异。",
    },
    "tutorial": {
        "single": "请将以下内容整理为循序渐进的实战教程。\n重点：拆解为可操作的步骤，每步包含：目标说明、代码/配置、预期结果、常见错误及解决方案。",
        "multi": "以下是从多个来源收集的教程相关内容，请整合为一篇完整的 step-by-step 教程。\n重点：统一技术栈版本，补足各来源缺失的环节，去除重复说明，在关键步骤标注注意事项。",
    },
    "comparison": {
        "single": "请对以下内容进行技术方案对比分析。\n重点：提取方案的核心差异、适用场景、性能指标，用表格或结构化列表呈现，最后给出选型建议。",
        "multi": "以下是从多个来源收集的内容，请进行横向技术方案对比。\n重点：从性能、生态、学习曲线、社区活跃度等维度对比，标注各方案的优劣势和推荐场景，给出结论性建议。",
    },
    "knowledge_report": {
        "single": "请对以下网页内容进行深度阅读，生成一份技术知识报告。\n重点：包含技术背景、核心原理、关键实现细节、当前生态现状，输出可直接沉淀到知识库的内容。",
        "multi": "以下是从多个来源收集的内容，请生成一份综合性技术知识报告。\n重点：包含背景概览、核心原理、实现方案对比、社区实践、趋势判断，标注关键参考来源。",
    },
}

JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*\n?([\s\S]*?)```")


# ============== Data Classes ==============

@dataclass
class OrganizedContent:
    title: str = ""
    summary: str = ""
    key_points: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    category: str = ""
    full_content: str = ""
    tokens_used: int = 0
    duration_ms: int = 0


@dataclass
class PageContent:
    url: str = ""
    title: str = ""
    markdown: str = ""
    word_count: int = 0
    depth: int = 0


@dataclass
class DigestPageContent:
    url: str = ""
    title: str = ""
    markdown: str = ""
    summary: str = ""
    category: str = ""
    source_name: str = ""


@dataclass
class DigestSection:
    category: str = ""
    category_name: str = ""
    emoji: str = ""
    items: list = field(default_factory=list)


@dataclass
class DigestItem:
    title: str = ""
    one_liner: str = ""
    source_url: str = ""
    source_name: str = ""


@dataclass
class DigestContent:
    title: str = ""
    summary: str = ""
    sections: list[DigestSection] = field(default_factory=list)
    highlight: str = ""
    tags: list[str] = field(default_factory=list)
    full_content: str = ""
    tokens_used: int = 0
    duration_ms: int = 0


# ============== Organizer ==============

class ContentOrganizer:
    """OpenAI-compatible content organizer."""

    def __init__(self, settings: AiSettings = None):
        self._settings = settings or ai_settings
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=self._settings.ai_connect_timeout,
                    read=self._settings.ai_read_timeout,
                    write=30.0,
                    pool=10.0,
                ),
                headers={
                    "Authorization": f"Bearer {self._settings.ai_api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    @property
    def is_available(self) -> bool:
        return self._settings.is_configured

    # --- Single page ---

    async def organize(
        self, raw_markdown: str, template: str = "tech_summary",
        keyword_context: str = None
    ) -> OrganizedContent:
        start = time.monotonic()
        user_prompt = self._build_single_page_prompt(raw_markdown, template, keyword_context)
        response = await self._call_ai(SYSTEM_PROMPT, user_prompt)
        result = self._parse_organized_content(response["content"])
        result.duration_ms = int((time.monotonic() - start) * 1000)
        result.tokens_used = response.get("total_tokens", 0)
        logger.info("[AiOrganizer] Single page organized: title=%s, duration=%dms, tokens=%d",
                     result.title, result.duration_ms, result.tokens_used)
        return result

    # --- Multi-page ---

    async def organize_multiple(
        self, pages: list[PageContent], template: str = "tech_summary",
        keyword_context: str = None
    ) -> OrganizedContent:
        start = time.monotonic()
        user_prompt = self._build_multi_page_prompt(pages, template, keyword_context)
        response = await self._call_ai(SYSTEM_PROMPT, user_prompt)
        result = self._parse_organized_content(response["content"])
        result.duration_ms = int((time.monotonic() - start) * 1000)
        result.tokens_used = response.get("total_tokens", 0)
        logger.info("[AiOrganizer] Multi-page organized: title=%s, pages=%d, duration=%dms",
                     result.title, len(pages), result.duration_ms)
        return result

    # --- Keyword optimization ---

    async def optimize_keyword(self, keyword: str) -> str:
        if not self._settings.is_configured:
            return keyword
        try:
            system_prompt = (
                "你是一名技术搜索关键词优化专家。\n"
                "任务：将用户输入的技术主题优化为搜索引擎返回更精准结果的查询词。\n"
                "规则：\n"
                "1. 补充技术限定词：添加版本号、产品全称、技术领域等消除歧义\n"
                "   - \"react hooks\" → \"React Hooks 使用教程\"\n"
                "   - \"k8s\" → \"Kubernetes 部署实践\"\n"
                "   - \"微服务\" → \"Spring Cloud 微服务架构\"\n"
                "2. 口语化 → 专业化：将日常用语转为搜索引擎友好的技术术语\n"
                "   - \"怎么学python\" → \"Python 入门学习路线\"\n"
                "   - \"数据库慢\" → \"MySQL 慢查询优化\"\n"
                "3. 中文关键词保持中文，英文关键词可添加中文限定词\n"
                "4. 长度控制在 5-30 字\n"
                "5. 只输出优化后的关键词，不要输出解释、引号、代码块或标点"
            )
            user_prompt = f"用户关键词：{keyword}\n优化结果："
            response = await self._call_ai(system_prompt, user_prompt)
            optimized = response["content"].strip() if response["content"] else keyword
            optimized = re.sub(r"^```\w*\s*", "", optimized)
            optimized = re.sub(r"\s*```$", "", optimized)
            optimized = optimized.strip().strip("\"'")

            if not optimized or len(optimized) > 100 or len(optimized) < 2:
                logger.warning("[AiKeywordOptimizer] fallback: invalid output for '%s'", keyword)
                return keyword

            if optimized != keyword:
                logger.info("[AiKeywordOptimizer] '%s' -> '%s'", keyword, optimized)
            return optimized
        except Exception as e:
            logger.warning("[AiKeywordOptimizer] fallback: %s for '%s'", e, keyword)
            return keyword

    # --- Keyword expansion ---

    async def expand_keywords(self, keyword: str) -> list[str]:
        if not self._settings.is_configured:
            return [keyword]
        try:
            system_prompt = (
                "你是一名技术搜索关键词扩展专家。\n"
                "场景：用户在技术博客系统中使用网页采集器，希望获取高质量技术资料。\n"
                "任务：基于输入关键词生成 3 个搜索角度不同的变体。\n\n"
                "扩展策略（每个变体使用不同策略）：\n"
                "- 同义替换：用等价的技术术语替换（docker → 容器化, k8s → Kubernetes）\n"
                "- 角度变换：从不同视角切入（教程、最佳实践、性能优化、架构设计）\n"
                "- 技术栈限定：补充关联技术栈（redis → Redis 集群 | Redis 持久化 | Redis 缓存策略）\n\n"
                "规则：\n"
                "1. 每个变体必须是能独立搜索的完整关键词\n"
                "2. 变体之间搜索结果重叠度应尽量低\n"
                "3. 不要生成\"XX介绍\"\"什么是XX\"等宽泛查询\n"
                "4. 每个变体 5-30 字\n"
                "5. 严格输出 JSON 数组格式，不要包裹在 markdown 中\n\n"
                "示例：\n"
                "输入：docker\n"
                "输出：[\"容器化部署最佳实践\", \"Docker Compose 微服务编排\", \"Docker 多阶段构建优化\"]\n\n"
                "输入：Spring Boot\n"
                "输出：[\"Spring Boot 3 自动配置原理\", \"Spring Boot 生产级监控\", \"Spring Boot 响应式编程\"]"
            )
            user_prompt = f"输入：{keyword}\n输出："
            response = await self._call_ai(system_prompt, user_prompt)
            content = response["content"].strip() if response["content"] else "[]"
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content).strip()

            raw_list = json.loads(content)
            keywords = [
                s.strip() for s in raw_list
                if isinstance(s, str) and s.strip() and len(s.strip()) <= 100
                and s.strip().lower() != keyword.lower()
            ]
            keywords = list(dict.fromkeys(keywords))[:3]  # dedupe + limit

            if not keywords:
                logger.warning("[AiKeywordExpander] fallback: empty for '%s'", keyword)
                return [keyword]

            logger.info("[AiKeywordExpander] '%s' -> %s", keyword, keywords)
            return keywords
        except Exception as e:
            logger.warning("[AiKeywordExpander] fallback: %s for '%s'", e, keyword)
            return [keyword]

    # --- Digest ---

    async def generate_digest(
        self, pages: list[DigestPageContent], date: str
    ) -> DigestContent:
        start = time.monotonic()
        user_prompt = self._build_digest_prompt(pages, date)
        response = await self._call_ai(DIGEST_SYSTEM_PROMPT, user_prompt)
        result = self._parse_digest_content(response["content"])
        result.duration_ms = int((time.monotonic() - start) * 1000)
        result.tokens_used = response.get("total_tokens", 0)
        logger.info("[AiOrganizer] Digest generated: title=%s, sections=%d, duration=%dms",
                     result.title, len(result.sections), result.duration_ms)
        return result

    # ============== Prompt Builders ==============

    def _build_single_page_prompt(
        self, raw_markdown: str, template: str, keyword_context: str | None
    ) -> str:
        truncated = _truncate_at_paragraph_boundary(
            raw_markdown, self._settings.ai_single_page_max_chars
        )

        template_prompts = TEMPLATE_PROMPTS.get(template, TEMPLATE_PROMPTS["tech_summary"])
        role_instruction = template_prompts["single"]

        parts = [role_instruction, "\n"]
        if keyword_context and keyword_context.strip():
            parts.append("## 搜索上下文\n")
            parts.append(keyword_context.strip())
            parts.append("\n请优先围绕以上实际搜索意图组织内容，避免被来源页面中的旁支主题带偏。\n\n")
        parts.append("## 原始内容\n")
        parts.append(truncated)
        parts.append("\n")
        parts.append(OUTPUT_SCHEMA)
        parts.append(FEW_SHOT_EXAMPLE)
        return "".join(parts)

    def _build_multi_page_prompt(
        self, pages: list[PageContent], template: str, keyword_context: str | None
    ) -> str:
        template_prompts = TEMPLATE_PROMPTS.get(template, TEMPLATE_PROMPTS["tech_summary"])
        role_instruction = template_prompts.get("multi", template_prompts["single"])

        parts = [role_instruction, "\n"]
        if keyword_context and keyword_context.strip():
            parts.append("## 搜索上下文\n")
            parts.append(keyword_context.strip())
            parts.append("\n请优先围绕以上实际搜索意图组织内容，避免被来源页面中的旁支主题带偏。\n\n")
        parts.append("## 来源内容\n\n")

        sorted_pages = sorted(pages, key=lambda p: len(p.markdown or ""), reverse=True)
        budget = self._settings.ai_multi_page_total_budget
        per_max = self._settings.ai_multi_page_per_max_chars

        for i, page in enumerate(sorted_pages):
            parts.append(f"### 来源 {i + 1}: {page.title or '未知标题'}\n")
            parts.append(f"URL: {page.url or '未知'}\n\n")

            page_budget = min(per_max, budget)
            if page_budget <= 0:
                parts.append("[已达到总输入预算上限，后续来源已省略]\n\n")
                continue

            markdown = _truncate_at_paragraph_boundary(page.markdown or "", page_budget)
            parts.append(markdown)
            parts.append("\n\n---\n\n")
            budget -= len(markdown)

        parts.append(OUTPUT_SCHEMA)
        parts.append(FEW_SHOT_EXAMPLE)
        return "".join(parts)

    def _build_digest_prompt(
        self, pages: list[DigestPageContent], date: str
    ) -> str:
        parts = [f"## 日报日期\n{date}\n\n", "## 来源内容\n\n"]

        by_category: dict[str, list[DigestPageContent]] = {}
        for p in pages:
            if not p.markdown or not p.markdown.strip():
                continue
            cat = p.category or "tech_article"
            by_category.setdefault(cat, []).append(p)

        budget = self._settings.ai_multi_page_total_budget
        per_max = self._settings.ai_multi_page_per_max_chars

        for cat in sorted(by_category):
            cat_pages = sorted(by_category[cat], key=lambda p: p.title or "")
            parts.append(f"### 分类: {cat}\n\n")
            for i, page in enumerate(cat_pages):
                parts.append(f"#### 来源 {i + 1}: {page.title or '未知标题'}\n")
                parts.append(f"URL: {page.url or '未知'}\n")
                if page.summary:
                    parts.append(f"摘要: {page.summary}\n")

                page_budget = min(per_max, budget)
                if page_budget <= 0:
                    parts.append("[已达到总输入预算上限，后续来源已省略]\n\n")
                    continue

                markdown = _truncate_at_paragraph_boundary(page.markdown or "", page_budget)
                parts.append(markdown)
                parts.append("\n\n---\n\n")
                budget -= len(markdown)

        parts.append("\n请根据以上内容生成结构化技术日报。")
        return "".join(parts)

    # ============== AI API Call ==============

    async def _call_ai(self, system_prompt: str, user_prompt: str) -> dict:
        if not self._settings.is_configured:
            raise RuntimeError("AI not configured")

        request_body = {
            "model": self._settings.ai_model,
            "temperature": self._settings.ai_temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        client = await self._get_client()
        response = await client.post(
            f"{self._settings.ai_base_url.rstrip('/')}/chat/completions",
            json=request_body,
        )

        if response.status_code == 429:
            raise RateLimitError("Rate limited by AI API")
        if 400 <= response.status_code < 500 and response.status_code != 429:
            raise UnrecoverableError(f"API client error {response.status_code}: {response.text[:200]}")
        if response.status_code >= 500:
            raise RuntimeError(f"API server error {response.status_code}")

        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("No choices in AI response")

        message = choices[0].get("message", {})
        content = _extract_message_content(message.get("content"))
        if not content:
            raise RuntimeError("Empty content in AI response")

        finish_reason = choices[0].get("finish_reason", "unknown")
        total_tokens = data.get("usage", {}).get("total_tokens", 0)

        if finish_reason == "length":
            raise TruncatedError(f"AI output truncated, tokens={total_tokens}")

        return {"content": content, "total_tokens": total_tokens, "finish_reason": finish_reason}

    # ============== Response Parsing ==============

    def _parse_organized_content(self, response: str) -> OrganizedContent:
        raw = json.loads(_extract_json(response))

        content = OrganizedContent()
        content.title = _normalize(raw.get("title", ""))
        content.summary = _normalize(raw.get("summary", ""))
        content.key_points = _normalize_list(raw.get("keyPoints"), MAX_KEY_POINTS)
        content.tags = _normalize_list(raw.get("tags"), MAX_TAGS)
        content.category = _normalize_category(raw.get("category", ""))
        content.full_content = _normalize(raw.get("fullContent", ""))

        self._validate_organized(content)
        return content

    def _validate_organized(self, c: OrganizedContent):
        if not c.title:
            raise InvalidOutputError("Missing title")
        if not c.summary or len(c.summary) < MIN_SUMMARY_LENGTH:
            raise InvalidOutputError("Summary too short")
        if not c.full_content or len(c.full_content) < MIN_FULL_CONTENT_LENGTH:
            raise InvalidOutputError("fullContent too short")
        if not c.key_points:
            raise InvalidOutputError("Missing keyPoints")
        if not c.tags:
            raise InvalidOutputError("Missing tags")
        if c.category not in ALLOWED_CATEGORIES:
            raise InvalidOutputError(f"Invalid category: {c.category}")

    def _parse_digest_content(self, response: str) -> DigestContent:
        raw = json.loads(_extract_json(response))

        content = DigestContent()
        content.title = _normalize(raw.get("title", ""))
        content.summary = _normalize(raw.get("summary", ""))
        content.highlight = _normalize(raw.get("highlight", ""))
        content.tags = _normalize_list(raw.get("tags"), MAX_TAGS)
        content.full_content = _normalize(raw.get("fullContent", ""))

        sections_raw = raw.get("sections", [])
        content.sections = []
        for sec in sections_raw:
            if not isinstance(sec, dict):
                continue
            section = DigestSection(
                category=_normalize(sec.get("category", "")),
                category_name=_normalize(sec.get("categoryName", "")),
                emoji=_normalize(sec.get("emoji", "")),
            )
            for item in sec.get("items", []):
                if not isinstance(item, dict):
                    continue
                section.items.append(DigestItem(
                    title=_normalize(item.get("title", "")),
                    one_liner=_normalize(item.get("oneLiner", "")),
                    source_url=_normalize(item.get("sourceUrl", "")),
                    source_name=_normalize(item.get("sourceName", "")),
                ))
            content.sections.append(section)

        self._validate_digest(content)
        return content

    def _validate_digest(self, c: DigestContent):
        if not c.title:
            raise InvalidOutputError("Digest missing title")
        if not c.summary or len(c.summary) < MIN_SUMMARY_LENGTH:
            raise InvalidOutputError("Digest summary too short")
        if not c.full_content or len(c.full_content) < MIN_FULL_CONTENT_LENGTH:
            raise InvalidOutputError("Digest fullContent too short")
        if not c.tags:
            raise InvalidOutputError("Digest missing tags")

        valid_categories = set(DIGEST_CATEGORY_MAP.keys())
        has_valid = False
        for sec in c.sections:
            # 校验并修正 category 代码
            if sec.category and sec.category not in valid_categories:
                logger.warning("Unknown digest category '%s', mapping to 'tech_article'", sec.category)
                sec.category = "tech_article"
                cat_info = DIGEST_CATEGORY_MAP["tech_article"]
                sec.category_name = cat_info[0]
                sec.emoji = cat_info[1]
            if sec.category and sec.category_name and sec.items:
                for item in sec.items:
                    if item.title and item.one_liner and item.source_url and item.source_name:
                        has_valid = True
                        break
            if has_valid:
                break
        if not has_valid:
            raise InvalidOutputError("Digest missing valid items")


# ============== Exceptions ==============

class OrganizerError(Exception):
    pass

class TruncatedError(OrganizerError):
    pass

class UnrecoverableError(OrganizerError):
    pass

class RateLimitError(OrganizerError):
    pass

class InvalidOutputError(OrganizerError):
    pass


# ============== Utility Functions ==============

def _extract_message_content(content) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict):
                text = part.get("text", "")
                if text:
                    parts.append(text)
            elif part is not None:
                parts.append(str(part))
        return "\n".join(parts).strip()
    return ""


def _extract_json(response: str) -> str:
    matcher = JSON_BLOCK_RE.search(response)
    if matcher:
        candidate = matcher.group(1).strip()
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass

    # 查找第一个 JSON 起始符（对象或数组）
    obj_start = response.find("{")
    arr_start = response.find("[")
    if obj_start < 0 and arr_start < 0:
        raise ValueError("No JSON found in AI response")

    if obj_start < 0:
        start = arr_start
    elif arr_start < 0:
        start = obj_start
    else:
        start = min(obj_start, arr_start)

    open_ch = response[start]
    close_ch = "}" if open_ch == "{" else "]"

    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(response)):
        c = response[i]
        if escape:
            escape = False
            continue
        if c == "\\" and in_string:
            escape = True
            continue
        if c == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return response[start:i + 1]

    raise ValueError("No balanced JSON found in AI response")


def _truncate_at_paragraph_boundary(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    cut_pos = text.rfind("\n\n", 0, max_len)
    if cut_pos < max_len * 0.8:
        cut_pos = text.rfind("\n", 0, max_len)
    if cut_pos < max_len * 0.5:
        cut_pos = max_len
    return text[:cut_pos] + "\n\n[...内容过长已截断]"


def _normalize(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_list(obj, max_items: int) -> list[str]:
    if not isinstance(obj, list):
        return []
    result = []
    seen = set()
    for item in obj:
        s = _normalize(item)
        if s and s not in seen:
            seen.add(s)
            result.append(s)
            if len(result) >= max_items:
                break
    return result


def _normalize_category(value) -> str:
    raw = _normalize(value)
    if not raw:
        return raw
    mapped = CATEGORY_ALIASES.get(raw.lower(), raw)
    if mapped not in ALLOWED_CATEGORIES:
        return "其他"
    return mapped


