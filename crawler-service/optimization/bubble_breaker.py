"""信息茧房突破模块 — 检测来源/语言单一性并补充跨语言搜索"""

import logging
import re
from collections.abc import Callable

from config import settings
from optimization.evaluator import CoverageEvaluator
from crawler.utils import get_result_url, get_result_success, dedup_results_into

logger = logging.getLogger(__name__)

TRANSLATE_SYSTEM_PROMPT = """你是搜索关键词翻译专家。
将给定的中文搜索关键词翻译为最适合搜索引擎的英文搜索词。
规则：
1. 只输出英文关键词，不要解释
2. 保留技术专有名词（如 React、Kubernetes）
3. 使用搜索引擎友好的短语格式（如 "Spring Boot tutorial" 而非完整句子）
4. 如果关键词已经是英文，原样返回"""


class BubbleBreaker:
    """信息茧房突破器：检测并突破搜索结果的来源/语言单一性"""

    def __init__(self, organizer=None):
        self._organizer = organizer
        self._evaluator = CoverageEvaluator(organizer=organizer)

    async def check_and_expand(
        self,
        keyword: str,
        results: list,
        crawl_fn: Callable,
        context: dict,
    ) -> list:
        """检查搜索结果的信息茧房风险，必要时补充搜索"""
        if not settings.bubble_breaker_enabled:
            return results

        expanded = list(results)
        seen_urls = {
            url
            for r in results
            if get_result_success(r)
            for url in [get_result_url(r) or ""]
            if url
        }

        # 跨语言扩展
        if settings.bubble_cross_language and self._needs_cross_language(results):
            translated = await self.translate_keyword(keyword)
            if translated:
                logger.info(
                    "[BubbleBreaker] Cross-language: '%s' -> '%s'", keyword, translated,
                )
                try:
                    new = await crawl_fn(
                        keyword=translated,
                        engine=context.get("engine", "bing"),
                        max_results=10,
                        time_range=context.get("time_range", "week"),
                        config=context.get("config"),
                        crawler=context.get("crawler"),
                    )
                    added = dedup_results_into(new, seen_urls, expanded)
                    logger.info(
                        "[BubbleBreaker] Added %d cross-language results", added,
                    )
                except Exception as e:
                    logger.warning("[BubbleBreaker] Cross-language search failed: %s", e)

        return expanded

    async def translate_keyword(self, keyword: str) -> str | None:
        """用 AI 将中文关键词翻译为英文搜索词，失败静默降级"""
        if not self._organizer or not self._organizer.is_available:
            return None
        try:
            response = await self._organizer._call_ai(TRANSLATE_SYSTEM_PROMPT, keyword)
            translated = response.get("content", "").strip()
            if translated and translated != keyword and re.search(r"[a-zA-Z]{2,}", translated):
                return translated
            return None
        except Exception as e:
            logger.debug("[BubbleBreaker] Translation failed: %s", e)
            return None

    def _needs_cross_language(self, results: list) -> bool:
        """检查结果是否语言单一（language_coverage 维度低）"""
        titles = []
        for r in results:
            rdict = r if isinstance(r, dict) else (r.__dict__ if hasattr(r, "__dict__") else {})
            if rdict.get("success", False):
                titles.append(rdict.get("title", "") or "")
        if not titles:
            return False
        language_mix = CoverageEvaluator._calc_language_mix(titles)
        return language_mix < 0.5
