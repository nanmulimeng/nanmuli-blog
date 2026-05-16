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

# ============== Constants (configured via ai_settings) ==============
# Values are read dynamically from ai_settings so changes to config take effect.
# We keep module-level names for backward compatibility with internal references.


def _cfg_min_summary_length():
    return ai_settings.ai_min_summary_length


def _cfg_min_full_content_length():
    return ai_settings.ai_min_full_content_length


def _cfg_max_key_points():
    return ai_settings.ai_max_key_points


def _cfg_max_tags():
    return ai_settings.ai_max_tags

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

_DIGEST_CATEGORY_ORDER = ["hot_trend", "open_source", "tech_article", "dev_tool", "paper", "creative"]

# ============== Prompts (identical to Java) ==============

SYSTEM_PROMPT = """你是一位技术内容整理专家。你的核心职责是**整理和标注**网页原始内容，而非改写或创作新文章。

## 核心原则（最高优先级）
- **最大程度保留原文**：不要改写、扩写、缩略或润色原文内容。原文的结构、措辞、代码示例、配置参数应保持原样。
- **你只做三件事**：① 过滤噪音（导航、广告、评论区等）；② 调整格式（统一 Markdown 层级、修复断裂的代码块）；③ 提取元数据（标题、摘要、要点、标签、分类）。
- **禁止编造**：keyPoints 必须来自原文明确提到的内容。不要补充原文没有的"背景知识"、"最佳实践"或"延伸阅读"。

## 输出规则
1. 严格输出 JSON，不要包裹在 markdown 代码块中
2. fullContent 使用 Markdown 格式，代码块使用 ```language 标记。保留原文的长度和结构，不要为了凑字数扩写，也不要为了精简而删减
3. **代码、配置、命令行示例必须原样保留**，包括注释和输出。不要修改代码风格或变量命名
4. 原文是什么语言就保留什么语言。不要将英文翻译为中文，也不要将中文翻译为英文。专有名词保持原文
5. tags 必须是原文中出现或明确讨论的具体技术关键词，3-7 个，避免\"技术\"\"编程\"等过泛标签
6. category 必须是以下之一：后端开发、前端开发、移动开发、数据库、DevOps、云计算、AI与机器学习、安全、区块链、其他
7. 如果输入不是有效技术内容（登录页、错误页、空白页、广告页），将 summary 设为"该页面不包含有效技术内容"，其他字段留空
8. 忽略导航菜单、Cookie 提示、评论区、分享按钮、广告、侧边栏等与正文无关的内容
9. keyPoints 应提炼原文中**实际出现**的技术要点，每条应具体、可操作。不要编造原文未提及的内容"""

OUTPUT_SCHEMA = """
## 输出格式（严格 JSON）
{
  "title": "中文标题，15-30字，概括原文核心主题",
  "summary": "100-300字原文摘要，用原文语言提炼核心内容，不补充原文没有的背景",
  "keyPoints": ["原文中的技术要点1（具体可操作）", "技术要点2", "技术要点3", "..."],
  "tags": ["原文涉及的技术关键词1", "关键词2"],
  "category": "后端开发|前端开发|移动开发|数据库|DevOps|云计算|AI与机器学习|安全|区块链|其他",
  "fullContent": "原文内容的结构化整理（保留代码示例、配置参数、命令行输出原样，维持原文语言，仅过滤噪音和调整格式层级）"
}"""


FEW_SHOT_EXAMPLE = """
## 输出示例（注意：fullContent 是原文的结构化整理，不是新写的文章）
{
  "title": "Spring Boot 3 优雅停机配置说明",
  "summary": "原文介绍了 Spring Boot 3 内置的优雅停机机制：通过 server.shutdown=graceful 配置让 Web 服务器在关闭时拒绝新请求并等待处理中的请求完成，结合 SmartLifecycle 接口实现资源有序释放，Kubernetes 环境下需配合 terminationGracePeriodSeconds 和 preStop 钩子。",
  "keyPoints": [
    "server.shutdown=graceful 开启优雅停机，默认等待 30s",
    "实现 SmartLifecycle 接口自定义资源释放顺序",
    "Kubernetes 需配置 terminationGracePeriodSeconds 和 preStop hook"
  ],
  "tags": ["Spring Boot 3", "优雅停机", "Kubernetes"],
  "category": "后端开发",
  "fullContent": "## 开启优雅停机\\n\\n在 application.yml 中配置：\\n\\n```yaml\\nserver:\\n  shutdown: graceful\\nspring:\\n  lifecycle:\\n    timeout-per-shutdown-phase: 30s\\n```\\n\\n启用后，应用关闭时 Web 服务器会拒绝新的请求，并等待正在处理的请求完成。\\n\\n## 自定义资源释放\\n\\n实现 SmartLifecycle 接口，按顺序释放资源。"
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
7. sourceUrl 必须原样复制输入中提供的 URL，不可修改、截断或编造
8. 论文类内容（category=paper）需包含：论文标题、核心发现、对从业者的实际意义
9. 只输出有实际内容支撑的分类，空分类不要出现在输出中。不要为凑分类而编造条目
## 热点排序优先级（从高到低）
按以下标准判断事件重要性，重要事件排在各分类的前面：
1. **影响范围**：影响全行业/多数开发者 > 仅影响特定技术栈用户
2. **时效性**：今天新发生/新发布 > 持续讨论中的旧闻
3. **权威性**：官方公告/正式发布 > 第三方解读/分析文章
4. **开发者影响**：需要开发者立即行动（如安全漏洞、breaking change）> 纯信息类
## highlight 选择标准
从所有条目中选取对开发者影响最大的一条，需满足：
- 优先选择影响范围最广、时效性最强的事件
- 100字内说明：事件是什么 + 对开发者意味着什么 + 是否需要行动
- 安全漏洞、重大版本发布、行业政策变化应优先于普通新闻
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
  "summary": "今日技术圈最值得关注：React 19 正式发布带来 Server Components 稳定版；Bun 1.2 性能再创新高，原生支持 S3 API；一篇深度解析 Linux 内核调度的文章引发广泛讨论；Mozilla 发布 WASM 组件模型正式规范。",
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
        },
        {
          "title": "Bun 1.2 性能再突破",
          "oneLiner": "原生支持 S3 API 和 PostgreSQL 协议，零依赖后端开发成为可能",
          "sourceUrl": "https://bun.sh/blog/bun-v1.2",
          "sourceName": "bun.sh"
        }
      ]
    },
    {
      "category": "tech_article",
      "categoryName": "技术文章",
      "emoji": "📖",
      "items": [
        {
          "title": "Linux 内核调度器深度解析",
          "oneLiner": "从 CFS 到 EEVDF 的演进，帮助理解容器环境下 CPU 调度瓶颈",
          "sourceUrl": "https://lwn.net/Articles/linux-scheduler",
          "sourceName": "lwn.net"
        }
      ]
    },
    {
      "category": "open_source",
      "categoryName": "开源项目",
      "emoji": "🌟",
      "items": [
        {
          "title": "WASM 组件模型规范正式发布",
          "oneLiner": "标准化 WASM 模块间互操作，Web 端可像 npm 一样组合 WASM 包",
          "sourceUrl": "https://github.com/WebAssembly/component-model",
          "sourceName": "github.com"
        }
      ]
    }
  ],
  "highlight": "React 19 正式发布，Server Components 进入稳定阶段，前端开发者需要评估现有项目的迁移成本",
  "tags": ["React 19", "Bun 1.2", "Linux调度器", "WASM", "组件模型"],
  "fullContent": "# 技术日报 | 2026-05-08\\n\\n## 热点动态\\n\\n### React 19 正式发布\\nServer Components 稳定版上线，use() hook 简化异步数据获取...\\n\\n### Bun 1.2 性能再突破\\n原生支持 S3 API...\\n\\n## 技术文章\\n\\n### Linux 内核调度器深度解析\\n从 CFS 到 EEVDF 的演进...\\n\\n## 开源项目\\n\\n### WASM 组件模型规范正式发布\\n标准化 WASM 模块间互操作..."
}"""

TEMPLATE_PROMPTS = {
    "tech_summary": {
        "single": "请对以下网页内容进行整理和标注。\n重点：过滤噪音、调整格式层级、保留所有代码/配置/命令行示例原样。不要改写原文内容。",
        "multi": "以下是从多个来源收集的内容，请整理为一份结构化技术摘要。\n重点：按主题归并各来源内容，保留各来源的代码示例和具体细节，标注每条信息的来源。不要合并或改写原文措辞。",
    },
    "tutorial": {
        "single": "请将以下内容整理为有序的步骤列表。\n重点：按原文已有的操作顺序编号，保留每步的代码/配置/命令行原样。如果原文没有的步骤不要编造。",
        "multi": "以下是从多个来源收集的教程相关内容，请按主题归并整理。\n重点：保留各来源的代码示例原样，标注来源，去除重复内容。不要补充原文没有的步骤。",
    },
    "comparison": {
        "single": "请对以下内容进行技术方案对比整理。\n重点：提取原文中提及的方案差异、适用场景、性能数据，用表格呈现。只使用原文中的数据，不要补充外部知识。",
        "multi": "以下是从多个来源收集的内容，请整理为横向技术对比。\n重点：从原文中提取各方案的性能、生态、学习曲线等维度的数据，标注数据来源。只使用原文中的实际数据。",
    },
    "knowledge_report": {
        "single": "请对以下网页内容进行知识提炼和标注。\n重点：保留原文的技术背景、核心原理、实现细节，按知识库格式整理。不要补充原文没有的信息。",
        "multi": "以下是从多个来源收集的内容，请整理为综合性技术知识条目。\n重点：保留各来源的核心原理和实现细节，标注参考来源。只整理原文中实际存在的信息。",
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
        digest_max_tokens = getattr(self._settings, "ai_digest_max_tokens", self._settings.ai_max_tokens)
        response = await self._call_ai(DIGEST_SYSTEM_PROMPT, user_prompt, max_tokens=digest_max_tokens)
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

        budget = getattr(self._settings, "ai_digest_total_budget", self._settings.ai_multi_page_total_budget)
        per_max = getattr(self._settings, "ai_digest_per_max_chars", self._settings.ai_multi_page_per_max_chars)

        # 按 _DIGEST_CATEGORY_ORDER 优先级排序，未知分类放末尾
        _order_map = {cat: i for i, cat in enumerate(_DIGEST_CATEGORY_ORDER)}
        sorted_cats = sorted(by_category.keys(), key=lambda c: _order_map.get(c, 99))

        # 每分类预算下限：防止高优先级分类耗尽总预算导致其他分类被截断
        num_cats = len(sorted_cats)
        min_cat_budget = budget // max(num_cats, 1)
        cat_budget_used = {cat: 0 for cat in sorted_cats}

        summary_only_count = 0
        budget_exhausted = False
        for cat in sorted_cats:
            cat_pages = sorted(by_category[cat], key=lambda p: p.title or "")
            # 每分类保留前半（至少 3 条）完整 markdown，后半仅发 summary
            full_detail_count = max(3, len(cat_pages) // 2)
            cat_info = DIGEST_CATEGORY_MAP.get(cat, ("技术文章", "📖"))
            parts.append(f"### 分类: {cat}（{cat_info[0]}）{cat_info[1]}\n\n")
            for i, page in enumerate(cat_pages):
                parts.append(f"#### 来源 {i + 1}: {page.title or '未知标题'}\n")
                parts.append(f"URL: {page.url or '未知'}\n")

                # 超过 full_detail_count 的条目：仅发 summary，节省 token
                if i >= full_detail_count and page.summary:
                    parts.append(f"摘要: {page.summary}\n")
                    parts.append("[该条目仅提供摘要，请根据标题和摘要生成条目]\n\n")
                    summary_only_count += 1
                    continue

                if page.summary:
                    parts.append(f"摘要: {page.summary}\n")

                # 计算当前分类剩余预算：取总预算和分类最低保证的较大值
                remaining_total = budget - sum(cat_budget_used.values())
                cat_remaining = min_cat_budget - cat_budget_used[cat]
                available = max(remaining_total, cat_remaining)
                page_budget = min(per_max, max(0, available))
                if page_budget <= 0:
                    logger.warning("[DigestPrompt] Budget exhausted, %d pages in '%s' omitted",
                                   len(cat_pages) - i, cat)
                    parts.append("[已达到总输入预算上限，后续来源已省略]\n\n")
                    continue

                markdown = _truncate_at_paragraph_boundary(page.markdown or "", page_budget)
                parts.append(markdown)
                parts.append("\n\n---\n\n")
                consumed = len(markdown)
                budget_used_total = sum(cat_budget_used.values()) + consumed
                cat_budget_used[cat] += consumed
                # 全局预算检查
                if budget_used_total >= budget:
                    remaining_cats = [c for c in sorted_cats if cat_budget_used[c] < min_cat_budget * 0.5]
                    if not remaining_cats:
                        budget_exhausted = True
                        break
            if budget_exhausted:
                break

        if summary_only_count:
            logger.info("[DigestPrompt] %d pages sent as summary-only (token optimization)", summary_only_count)
        parts.append("\n请根据以上内容生成结构化技术日报。")
        return "".join(parts)

    # ============== AI API Call ==============

    async def _call_ai(self, system_prompt: str, user_prompt: str, max_tokens: int | None = None) -> dict:
        if not self._settings.is_configured:
            raise RuntimeError("AI not configured")

        request_body = {
            "model": self._settings.ai_model,
            "temperature": self._settings.ai_temperature,
            "max_tokens": max_tokens or self._settings.ai_max_tokens,
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
        content.key_points = _normalize_list(raw.get("keyPoints"), _cfg_max_key_points())
        content.tags = _normalize_list(raw.get("tags"), _cfg_max_tags())
        content.category = _normalize_category(raw.get("category", ""))
        content.full_content = _normalize(raw.get("fullContent", ""))

        self._validate_organized(content)
        return content

    def _validate_organized(self, c: OrganizedContent):
        min_s = _cfg_min_summary_length()
        min_f = _cfg_min_full_content_length()

        # 检测"非有效技术内容"模式（多模式匹配，避免精确字符串依赖）
        _NON_TECH_PATTERNS = ["不包含有效", "非技术", "非有效", "空白页", "登录页", "广告页", "错误页"]
        if c.summary and any(p in c.summary for p in _NON_TECH_PATTERNS):
            raise InvalidOutputError("页面不包含有效技术内容（登录页/错误页/广告页等）")

        if not c.title:
            raise InvalidOutputError("Missing title")
        if not c.summary:
            raise InvalidOutputError("Missing summary")
        if len(c.summary) < min_s:
            raise InvalidOutputError(f"Summary too short (len={len(c.summary)}, min={min_s})")
        if not c.full_content:
            raise InvalidOutputError("Missing fullContent")
        if len(c.full_content) < min_f:
            raise InvalidOutputError(f"fullContent too short (len={len(c.full_content)}, min={min_f})")
        if not c.key_points:
            raise InvalidOutputError("Missing keyPoints (got empty array)")
        # keyPoints 质量检查：每条至少 5 个字符
        thin_points = [kp for kp in c.key_points if len(kp) < 5]
        if thin_points:
            raise InvalidOutputError(f"keyPoints too short: {thin_points[:3]}")
        if not c.tags:
            raise InvalidOutputError("Missing tags (got empty array)")
        if c.category not in ALLOWED_CATEGORIES:
            raise InvalidOutputError(f"Invalid category '{c.category}', allowed: {', '.join(sorted(ALLOWED_CATEGORIES))}")

    def _parse_digest_content(self, response: str) -> DigestContent:
        raw = json.loads(_extract_json(response))

        content = DigestContent()
        content.title = _normalize(raw.get("title", ""))
        content.summary = _normalize(raw.get("summary", ""))
        content.highlight = _normalize(raw.get("highlight", ""))
        content.tags = _normalize_list(raw.get("tags"), _cfg_max_tags())
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
        min_s = _cfg_min_summary_length()
        min_f = _cfg_min_full_content_length()

        if not c.title:
            raise InvalidOutputError("Digest missing title")
        if not c.summary:
            raise InvalidOutputError("Digest missing summary")
        if len(c.summary) < min_s:
            raise InvalidOutputError(f"Digest summary too short (len={len(c.summary)}, min={min_s})")
        if not c.full_content:
            raise InvalidOutputError("Digest missing fullContent")
        if len(c.full_content) < min_f:
            raise InvalidOutputError(f"Digest fullContent too short (len={len(c.full_content)}, min={min_f})")
        if not c.tags:
            raise InvalidOutputError("Digest missing tags (got empty array)")

        valid_categories = set(DIGEST_CATEGORY_MAP.keys())
        for sec in c.sections:
            if sec.category and sec.category not in valid_categories:
                logger.warning("Unknown digest category '%s', mapping to 'tech_article'", sec.category)
                sec.category = "tech_article"
                cat_info = DIGEST_CATEGORY_MAP["tech_article"]
                sec.category_name = cat_info[0]
                sec.emoji = cat_info[1]

        # 跨板块 sourceUrl 去重：保留 oneLiner 最完整的条目
        seen_urls: dict[str, tuple[int, int]] = {}  # url -> (section_idx, item_idx)
        for si, sec in enumerate(c.sections):
            items_to_keep = []
            for item in sec.items:
                url = item.source_url
                if url in seen_urls:
                    prev_si, prev_ii = seen_urls[url]
                    prev_item = c.sections[prev_si].items[prev_ii]
                    if len(item.one_liner) > len(prev_item.one_liner):
                        # 新条目更完整，从旧板块移除旧条目
                        c.sections[prev_si].items[prev_ii] = None
                    else:
                        continue  # 旧条目更完整，跳过新条目
                seen_urls[url] = (si, len(items_to_keep))
                items_to_keep.append(item)
            sec.items = items_to_keep
        # 清理被标记为 None 的条目
        for sec in c.sections:
            sec.items = [it for it in sec.items if it is not None]

        # 过滤空板块（放在 URL 去重之后，避免去重后出现新空板块）
        c.sections = [sec for sec in c.sections if sec.items]

        # sourceUrl 合法性校验：移除非 HTTP URL 和明显编造的 URL
        _URL_RE = re.compile(r"^https?://\S+\.\S+", re.IGNORECASE)
        for sec in c.sections:
            sec.items = [
                item for item in sec.items
                if not item.source_url or _URL_RE.match(item.source_url)
            ]
        c.sections = [sec for sec in c.sections if sec.items]

        has_valid = any(
            item.title and item.one_liner and item.source_url and item.source_name
            for sec in c.sections
            for item in sec.items
        )
        if not has_valid:
            raise InvalidOutputError("Digest missing valid items")

        # highlight 兜底：为空时取第一个 section 第一个 item 的 oneLiner
        if not c.highlight and c.sections and c.sections[0].items:
            c.highlight = c.sections[0].items[0].one_liner


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


