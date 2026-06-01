"""
日报爬取逻辑

从 TaskExecutor 提取的日报专用爬取、去重和优化逻辑。
"""

import copy
import logging

from config import settings

logger = logging.getLogger(__name__)


async def build_digest_history_engine():
    """从 Java API 加载持久化指纹，回退到本地 SQLite 历史，用于跨日去重"""
    from crawler.dedup import DedupEngine
    from standalone import repository as repo

    engine = DedupEngine()

    # 优先从 Java API 加载持久化指纹
    java_url = settings.java_api_url
    if java_url:
        try:
            import httpx
            headers = {"Content-Type": "application/json"}
            if settings.callback_api_key:
                headers["X-Callback-Key"] = settings.callback_api_key
            async with httpx.AsyncClient(timeout=settings.sources_api_timeout) as client:
                resp = await client.get(
                    f"{java_url}/api/internal/collector/digest/fingerprints?days=3",
                    headers=headers,
                )
                if resp.status_code == 200:
                    data = resp.json().get("data") or []
                    for fp in data:
                        url = fp.get("url", "")
                        title = fp.get("title", "")
                        simhash_val = fp.get("simhash")
                        if url:
                            if simhash_val and isinstance(simhash_val, (int, float)):
                                engine.add_precomputed_simhash(url, title=title, simhash=int(simhash_val))
                            else:
                                engine.add_reference(url, title=title, content="")
                    if data:
                        logger.info("Digest history engine: %d fingerprints loaded from Java API", len(data))
                    return engine
        except Exception as e:
            logger.warning("Failed to load fingerprints from Java API: %s, falling back to local", e)

    # 回退：从本地 SQLite 加载历史日报页面
    try:
        pages = await repo.get_history_digest_pages(count=settings.digest_history_load_count)
        for p in pages:
            url = p.get("url", "")
            title = p.get("page_title", "")
            content = p.get("raw_markdown", "")
            if url:
                engine.add_reference(url, title=title, content=content)
        if pages:
            logger.info("Digest history engine: %d reference pages loaded from local SQLite", len(pages))
    except Exception as e:
        logger.warning("Failed to load digest history for dedup: %s", e)
    return engine


async def save_digest_fingerprints(task_id: int, results: list, digest_date: str):
    """日报完成后将指纹保存到 Java PostgreSQL（跨日持久化去重）"""
    from crawler.dedup import ContentFingerprint

    java_url = settings.java_api_url
    if not java_url:
        return

    import hashlib
    fingerprints = []
    for r in results:
        url = r.get('url', '') if isinstance(r, dict) else getattr(r, 'url', '')
        title = r.get('title', '') if isinstance(r, dict) else getattr(r, 'title', '')
        content = r.get('markdown', '') if isinstance(r, dict) else getattr(r, 'markdown', '')
        if not url:
            continue
        url_hash = hashlib.sha256(url.encode('utf-8')).hexdigest()
        # 优先从 metadata 读取已缓存的 simhash（避免重复计算）
        metadata = r.get('metadata', {}) if isinstance(r, dict) else getattr(r, 'metadata', {})
        simhash_val = metadata.get("_simhash") if isinstance(metadata, dict) else None
        if simhash_val is None and content and len(content) >= 100:
            simhash_val = ContentFingerprint(content).simhash
        fingerprints.append({
            "taskId": task_id,
            "urlHash": url_hash,
            "url": url,
            "title": (title or "")[:500],
            "simhash": simhash_val,
            "digestDate": digest_date,
        })

    if not fingerprints:
        return

    try:
        import httpx
        headers = {"Content-Type": "application/json"}
        if settings.callback_api_key:
            headers["X-Callback-Key"] = settings.callback_api_key
        async with httpx.AsyncClient(timeout=settings.sources_api_timeout) as client:
            resp = await client.post(
                f"{java_url}/api/internal/collector/digest/fingerprints",
                json=fingerprints,
                headers=headers,
            )
            if resp.status_code == 200:
                logger.info("[DigestFingerprints] Saved %d fingerprints to Java API", len(fingerprints))
            else:
                logger.warning("[DigestFingerprints] Save failed: status=%d", resp.status_code)
    except Exception as e:
        logger.warning("[DigestFingerprints] Save failed: %s", e)


def _extract_digest_keyword(sections: list[dict] | None) -> str:
    """从板块配置中提取最具代表性的关键词用于优化评估"""
    if not sections:
        return "technology"
    for section in sections:
        kw = section.get("keyword", "")
        if kw and section.get("source_type") in ("keyword", "mixed"):
            parts = [p.strip() for p in kw.split(" OR ") if p.strip()]
            if not parts:
                continue
            # 取第一个关键词（最具体的搜索意图）
            first = parts[0][:100]
            if len(first) >= 2:
                return first
    for section in sections:
        name = section.get("name", "")
        if name:
            return name
    return "technology"


def copy_config(config):
    """复制配置对象"""
    from api.crawl import CrawlConfig
    if hasattr(config, 'model_dump'):
        return CrawlConfig(**config.model_dump())
    elif hasattr(config, '__dict__'):
        return CrawlConfig(**{k: v for k, v in config.__dict__.items()
                              if k in CrawlConfig.model_fields})
    return CrawlConfig()


def apply_overrides(section: dict, overrides: dict | None) -> dict:
    """根据自适应参数覆盖修改 section 副本。"""
    if not overrides:
        return section

    sec = copy.deepcopy(section)

    freshness_mult = overrides.get("freshness_multiplier", 1.0)
    if freshness_mult != 1.0:
        for rss_src in sec.get("rss_sources", []):
            original = rss_src.get("freshness_hours", 24)
            rss_src["freshness_hours"] = int(original * freshness_mult)

    items_mult = overrides.get("max_items_multiplier", 1.0)
    if items_mult != 1.0:
        original_max = sec.get("max_items", 5)
        sec["max_items"] = max(int(original_max * items_mult), 1)

    skip_ids = set(overrides.get("skip_source_ids", []))
    if skip_ids:
        sec["url_sources"] = [
            s for s in sec.get("url_sources", [])
            if s.get("source_id") not in skip_ids
        ]
        sec["rss_sources"] = [
            s for s in sec.get("rss_sources", [])
            if s.get("source_id") not in skip_ids
        ]

    return sec
