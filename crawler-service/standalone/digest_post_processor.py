"""日报后处理器 — 预生成日报保存 + AI 整理

从 TaskExecutor 拆分，负责日报任务的 AI 整理阶段：
1. 预生成日报保存（DigestOrchestrator 已预生成时优先使用）
2. AI 内容整理回退
"""

import asyncio
import logging
from urllib.parse import urlsplit, urlunsplit

from config import settings
from ai.config import ai_settings
from standalone import repository as repo

logger = logging.getLogger(__name__)


def _normalize_url(url: str) -> str:
    """规范化 URL 用于匹配：小写 scheme+netloc，去尾斜杠，去 fragment，去 query"""
    if not url:
        return ""
    try:
        parts = urlsplit(url.strip())
        scheme = parts.scheme.lower()
        netloc = parts.netloc.lower()
        path = parts.path.rstrip("/")
        return urlunsplit((scheme, netloc, path, "", ""))
    except Exception:
        return url.strip().lower().rstrip("/").split("#")[0]


class DigestPostProcessor:
    """日报后处理器：预生成日报保存 + AI 整理回退"""

    def __init__(self, repository=None):
        self.repo = repository

    def _repo(self):
        return self.repo or repo

    async def save_pre_generated(self, task_id: int, task: dict, pre_generated) -> bool:
        """保存 Orchestrator 预生成的日报结果（回填 page_id）"""
        from standalone.organizer_helper import (
            serialize_digest_sections, _is_highlight_duplicate, _replace_duplicate_highlight,
        )

        try:
            digest = pre_generated.digest_content
            if not digest:
                return False

            date = task.get("digest_date") or task.get("keyword") or ""

            # 从已保存的 DB 页面获取 URL → page_id 映射（使用规范化 URL 匹配）
            repository = self._repo()
            pages = await repository.get_pages_by_task(task_id)
            url_to_page_id = {}
            for p in pages:
                if p.get("crawl_status") == 2 and p.get("url"):
                    url_to_page_id[_normalize_url(p["url"])] = p["id"]

            # Highlight 去重
            recent_highlights = await repository.get_recent_highlights(count=3)
            if recent_highlights and digest.highlight:
                if _is_highlight_duplicate(digest.highlight, recent_highlights):
                    _replace_duplicate_highlight(digest, recent_highlights)

            # 序列化 sections 并回填 page_id
            sections_data = serialize_digest_sections(digest, url_to_page_id=url_to_page_id)

            await repository.save_digest_results(
                task_id,
                ai_title=digest.title,
                ai_summary=digest.summary,
                ai_tags=digest.tags,
                ai_full_content=digest.full_content,
                ai_duration=digest.duration_ms,
                ai_tokens_used=digest.tokens_used,
                digest_date=date,
                highlight=digest.highlight,
                sections=sections_data,
            )
            logger.info("Task %d pre-generated digest saved: title='%s'", task_id, digest.title)
            return True

        except Exception as e:
            logger.error("Task %d pre-generated digest save failed: %s", task_id, e, exc_info=True)
            return False

    async def organize_with_ai(self, task_id: int, task: dict) -> bool:
        """AI 内容整理（含重试）"""
        from ai import content_organizer as organizer
        from ai.organizer import (
            OrganizerError, RateLimitError, TruncatedError, UnrecoverableError, InvalidOutputError,
        )
        from standalone.organizer_helper import organize_content_and_save, organize_digest_and_save

        if not organizer.is_available:
            logger.info("AI not configured, skipping organization for task %d", task_id)
            repository = self._repo()
            await repository.save_ai_error(task_id, "AI 未配置")
            return False

        task_type = task["task_type"]
        max_retries = ai_settings.ai_max_retries

        repository = self._repo()
        pages = await repository.get_pages_by_task(task_id)
        if not pages or not any(p.get("crawl_status") == 2 and p.get("raw_markdown") for p in pages):
            await repository.save_ai_error(task_id, "没有成功的页面可供 AI 整理")
            return False

        for attempt in range(max_retries + 1):
            try:
                if task_type == "digest":
                    result = await organize_digest_and_save(task_id, task, pages, organizer)
                else:
                    result = await organize_content_and_save(task_id, task, pages, organizer)

                logger.info("Task %d AI organized: title='%s', duration=%dms, tokens=%d",
                            task_id, result.title, result.duration_ms, result.tokens_used)
                return True

            except TruncatedError as e:
                logger.warning("Task %d AI truncated, retrying with larger max_tokens: %s",
                               task_id, e)
                try:
                    original_max = ai_settings.ai_digest_max_tokens
                    retry_max_tokens = int(original_max * 1.5)
                    if task_type == "digest":
                        result = await organize_digest_and_save(
                            task_id, task, pages, organizer,
                            max_tokens_override=retry_max_tokens,
                        )
                    else:
                        result = await organize_content_and_save(
                            task_id, task, pages, organizer,
                            max_tokens_override=retry_max_tokens,
                        )
                    logger.info("Task %d AI re-organized after truncation recovery: title='%s'",
                                task_id, result.title)
                    return True
                except Exception as retry_err:
                    msg = f"AI 输出被截断且重试失败，原始爬取结果已保留：{retry_err}"
                    logger.warning("Task %d AI truncation retry also failed: %s", task_id, retry_err)
                    await repository.save_ai_error(task_id, msg)
                    return False

            except UnrecoverableError as e:
                msg = f"AI API 请求被拒绝：{e}"
                logger.warning("Task %d AI unrecoverable: %s, skipping retry", task_id, e)
                await repository.save_ai_error(task_id, msg)
                return False

            except InvalidOutputError as e:
                msg = f"AI 输出格式校验失败：{e}"
                logger.warning("Task %d AI invalid output: %s, skipping retry", task_id, e)
                await repository.save_ai_error(task_id, msg)
                return False

            except RateLimitError as e:
                backoff = settings.ai_rate_limit_backoff_ms / 1000.0 * (attempt + 1)
                logger.warning("Task %d AI rate limited, retry in %.1fs (attempt %d/%d)",
                               task_id, backoff, attempt + 1, max_retries + 1)
                if attempt < max_retries:
                    await asyncio.sleep(backoff)
                    continue
                await repository.save_ai_error(task_id, "AI API 频率限制，已重试仍失败，请稍后再试")

            except OrganizerError as e:
                backoff = 2 ** attempt
                logger.warning("Task %d AI error, retry in %ds (attempt %d/%d): %s",
                               task_id, backoff, attempt + 1, max_retries + 1, e)
                if attempt < max_retries:
                    await asyncio.sleep(backoff)
                    continue
                await repository.save_ai_error(task_id, f"AI 整理失败 (已重试 {max_retries} 次)：{e}")

            except Exception as e:
                logger.error("Task %d AI unexpected error: %s", task_id, e, exc_info=True)
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
                await repository.save_ai_error(task_id, f"AI 整理异常：{e}")

        return False
