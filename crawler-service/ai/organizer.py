"""OpenAI-compatible content organizer.

Migrated from Java OpenAiCompatibleOrganizer with identical prompts and logic.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import httpx

from .config import ai_settings

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
    "paper": "学术论文", "📄"),
}

# ============== Prompts (identical to Java) ==============

SYSTEM_PROMPT = """你是一位资深技术内容编辑，擅长从网页原始内容中提取、整理并重组为高质量技术文章。
## 输出规则
1. 严格输出 JSON，不要包裹在 markdown 代码块中
2. fullContent 使用 Markdown 格式，代码块请使用 ```language 标记，正文建议 1000-5000 字
3. 保留原文中有价值的代码示例，不要丢弃关键信息
4. 英文内容翻译为中文，保留专有名词原文，例如 React、Kubernetes
5. tags 必须是具体技术关键词，建议 3-7 个，避免过泛标签
6. category 必须是以下之一：后端开发、前端开发、移动开发、数据库、DevOps、云计算、AI与机器学习、安全、区块链、其他
7. 如果输入不是有效技术内容，例如登录页、错误页、空白页，请返回一个明确的无效结果，而不是胡乱总结
8. 忽略导航、Cookie 提示、评论区、分享按钮、广告等与正文无关的内容"""

OUTPUT_SCHEMA = """
## 输出格式
{
  "title": "吸引人的中文标题（15-30字）",
  "summary": "200-300字核心摘要",
  "keyPoints": ["要点1", "要点2"],
  "tags": ["标签1", "标签2"],
  "category": "后端开发|前端开发|移动开发|数据库|DevOps|云计算|AI与机器学习|安全|区块链|其他",
  "fullContent": "完整 Markdown 格式整理文章"
}"""

FEW_SHOT_EXAMPLE = """
## 输出示例
{
  "title": "Spring Boot 3 优雅停机配置详解",
  "summary": "本文讲解 Spring Boot 3 的优雅停机机制，包括 server.shutdown=graceful 配置、SmartLifecycle 资源释放，以及在 Docker 和 Kubernetes 环境中的协同策略。通过合理配置，可以让应用在关闭时安全释放资源并尽可能完成正在处理的请求。",
  "keyPoints": [
    "通过 server.shutdown=graceful 开启内置优雅停机",
    "使用 SmartLifecycle 处理线程池和连接等资源释放",
    "在 Kubernetes 中需要配合 terminationGracePeriodSeconds"
  ],
  "tags": ["Spring Boot 3", "优雅停机", "Kubernetes", "微服务"],
  "category": "后端开发",
  "fullContent": "## Spring Boot 3 优雅停机\\n\\n### 开启优雅停机\\n\\n在 application.yml 中配置：\\n\\n```yaml\\nserver:\\n  shutdown: graceful\\nspring:\\n  lifecycle:\\n    timeout-per-shutdown-phase: 30s\\n```\\n\\n启用后，应用关闭时 Web 服务器会拒绝新的请求，并等待正在处理的请求完成。\\n\\n### 使用 SmartLifecycle 释放资源\\n\\n对于需要自定义清理逻辑的组件，可以实现 SmartLifecycle 接口。\\n\\n### Kubernetes 中的配合\\n\\n需要在 Pod 配置中预留足够的终止窗口，避免流量仍然打到即将下线的实例。"
}"""

DIGEST_SYSTEM_PROMPT = """你是一位资深技术资讯编辑，负责生成每日技术日报。
## 任务
根据提供的多个来源内容，生成一份结构化、可读性强的中文技术日报。
## 输出规则
1. 严格输出 JSON，不要包裹在 markdown 代码块中
2. fullContent 使用 Markdown 格式，包含标题、列表和链接
3. 每个条目必须压缩为一句话摘要，突出核心信息
4. 对重复报道进行合并，优先保留信息更完整的来源
5. 使用中文表达，保留必要的技术专有名词原文
6. tags 使用具体技术关键词，建议 5-10 个
## 输出格式
{
  "title": "日报标题（含日期）",
  "summary": "200-300 字今日摘要",
  "sections": [
    {
      "category": "分类代码",
      "categoryName": "分类显示名",
      "emoji": "emoji",
      "items": [
        {
          "title": "文章标题",
          "oneLiner": "一句话摘要",
          "sourceUrl": "原文链接",
          "sourceName": "来源域名"
        }
      ]
    }
  ],
  "highlight": "今日最值得关注的一条亮点（100 字内）",
  "tags": ["标签1", "标签2"],
  "fullContent": "完整 Markdown 日报正文"
}

## 分类代码对照
- hot_trend -> 热点动态 -> 🔥
- open_source -> 开源项目 -> 🌟
- tech_article -> 技术文章 -> 📖
- dev_tool -> 开发工具 -> 🔧
- creative -> 创意发现 -> 💡
- paper -> 技术论文 -> 📄"""

TEMPLATE_PROMPTS = {
    "tech_summary": {
        "single": "请对以下网页内容进行深度阅读和结构化整理。\n重点：提炼核心技术要点，梳理逻辑脉络，补充必要背景，输出一篇结构清晰的技术摘要。",
        "multi": "以下是从多个来源收集的技术内容，请进行综合分析和结构化整理。\n重点：提炼共识，去重合并重复信息，保留互补细节，并形成一篇可直接沉淀的技术总结。",
    },
    "tutorial": {
        "single": "请将以下内容整理为循序渐进的 step-by-step 教程。\n重点：拆解学习路径，明确每一步的操作、代码和预期结果，并提示常见坑点。",
        "multi": "以下是从多个来源收集的教程相关内容，请整合为一篇循序渐进的教程。\n重点：统一步骤顺序，补足缺失环节，去除重复说明，保留关键代码与注意事项。",
    },
    "comparison": {
        "single": "请对以下内容进行分析，提取技术方案对比信息。\n重点：总结方案差异、适用场景、优缺点，并尽量形成可读的对比结构。",
        "multi": "以下是从多个来源收集的内容，请进行横向技术方案对比。\n重点：总结差异、适用场景和推荐建议，尽量用结构化方式呈现。",
    },
    "knowledge_report": {
        "single": "请对以下网页内容进行深度阅读和结构化整理。\n根据内容所属技术领域，自动选择最合适的分类和标签。",
        "multi": "以下是从多个来源收集的内容，请生成一份综合性的知识报告。\n重点：包含背景概览、核心原理、现状分析、趋势判断和主要参考来源。",
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

    @property
    def is_available(self) -> bool:
        return self._settings.is_configured

    # --- Single page ---

    async def organize(
        self, raw_markdown: str, template: str = "tech_summary",
        keyword_context: str = None
    ) -> OrganizedContent:
        import time
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
        import time
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
                "你是一名搜索关键词优化专家。\n"
                "任务：将用户输入的技术主题优化为更适合搜索引擎查询的关键词。\n"
                "规则：\n"
                "1. 补充必要的技术限定词，减少歧义\n"
                "2. 将口语化表达改写为专业术语\n"
                "3. 保持中文表达，长度尽量控制在 30 字内\n"
                "4. 不要输出解释、引号或代码块，只输出关键词本身"
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
                "你是一名搜索关键词扩展专家。\n"
                "场景：用户在技术博客系统中使用网页采集器，希望获取高质量技术资料。\n"
                "任务：基于输入关键词生成 2-3 个不同的搜索变体。\n"
                "规则：\n"
                "1. 优先保持技术语境，不要偏向泛化搜索\n"
                "2. 对多义词补足技术限定词，例如产品名、厂商名、技术领域\n"
                "3. 不要生成只有\"介绍\"\"功能\"之类的宽泛查询\n"
                "4. 严格输出 JSON 数组，不要包裹在 markdown 中\n"
                "5. 每个变体不超过 30 个字，变体之间要有明显差异"
            )
            user_prompt = f"用户关键词：{keyword}\n输出："
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
        import time
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

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=self._settings.ai_connect_timeout,
                read=self._settings.ai_read_timeout,
                write=30.0,
                pool=10.0,
            )
        ) as client:
            response = await client.post(
                f"{self._settings.ai_base_url.rstrip('/')}/chat/completions",
                json=request_body,
                headers={
                    "Authorization": f"Bearer {self._settings.ai_api_key}",
                    "Content-Type": "application/json",
                },
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

        has_valid = False
        for sec in c.sections:
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

    start = response.find("{")
    if start < 0:
        raise ValueError("No JSON found in AI response")

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
        if c == "{":
            depth += 1
        elif c == "}":
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
    return CATEGORY_ALIASES.get(raw.lower(), raw)


# ============== Module Singleton ==============

organizer = ContentOrganizer()
