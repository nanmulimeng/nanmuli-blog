# Search Algorithm Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the digest search pipeline from keyword fan-out plus cleanup into a measured, adaptive, relevance-ranked search system.

**Architecture:** Keep the current digest chain: `DigestOrchestrator` plans sections, `SourceAgent` adapts sources, `CrawlerAgent` executes keyword/url/rss crawling, and `KnowledgeBase` feeds next-run actions. Add a narrow search-planning layer, deterministic result scoring, search diagnostics, and event-level grouping without adding a new database table in the first pass.

**Tech Stack:** Python FastAPI crawler service, SQLite repository layer, existing crawler/search/dedup modules, pytest, Vue admin diagnostics already backed by crawler APIs.

## Global Constraints

- Do not change public `/api/digest*` parameters.
- Do not introduce a new database table in this optimization pass.
- Keep Java backend as proxy/config owner unless a crawler API contract requires type changes.
- Keep search engines optional and failure-isolated; one failed engine or RSS feed must not fail the section.
- Use deterministic tests before changing ranking behavior.
- Preserve current digest categories: `hot_trend`, `open_source`, `dev_tool`, `tech_article`, `paper`.

---

## File Structure

- Modify `crawler-service/crawler/search.py`: keep low-level search execution, expose normalized search result diagnostics.
- Create `crawler-service/crawler/search_planner.py`: build section-aware query variants and engine/time budgets.
- Create `crawler-service/crawler/search_ranker.py`: score and sort candidates before page crawling and after page crawling.
- Modify `crawler-service/crawler/crawler_agent.py`: consume search plans and ranker output while preserving URL/RSS behavior.
- Modify `crawler-service/crawler/digest_orchestrator.py`: add plan log entries and aggregate search diagnostics per section.
- Modify `crawler-service/crawler/dedup.py`: add event-level grouping helpers separate from strict URL/content dedup.
- Modify `crawler-service/optimization/knowledge_base.py`: persist and derive next-run search actions from diagnostics already stored in `optimization_record.strategy_detail`.
- Modify `crawler-service/standalone/routes.py`: expose search diagnostics through existing digest task detail payload.
- Test `crawler-service/tests/test_search_planner.py`, `test_search_ranker.py`, `test_digest_orchestrator.py`, `test_task_executor.py`, and `test_digest_api.py`.

---

### Task 1: Search Quality Baseline Harness

**Files:**
- Create: `crawler-service/tests/fixtures/search_quality_cases.json`
- Create: `crawler-service/tests/test_search_quality_baseline.py`
- Modify: `crawler-service/crawler/search.py`

**Interfaces:**
- Produces: `normalize_search_result(raw: dict, *, keyword: str, engine: str, rank: int) -> dict`
- Consumes: existing `CrawlResult` fields and `filters.is_excluded_domain()`.

- [ ] **Step 1: Add fixture cases**

Create `crawler-service/tests/fixtures/search_quality_cases.json` with representative cases:

```json
[
  {
    "section": "open_source",
    "keyword": "AI developer tools open source",
    "engine": "bing",
    "raw": {"title": "microsoft/playwright: Fast and reliable end-to-end testing", "url": "https://github.com/microsoft/playwright", "snippet": "Open source automation for modern web apps."},
    "expected_keep": true
  },
  {
    "section": "tech_article",
    "keyword": "AI agent architecture engineering",
    "engine": "bing",
    "raw": {"title": "What is software? Definition and examples", "url": "https://www.geeksforgeeks.org/computer-science-fundamentals/software-and-its-types/", "snippet": "Introductory explanation."},
    "expected_keep": false
  },
  {
    "section": "paper",
    "keyword": "LLM agent benchmark paper",
    "engine": "google",
    "raw": {"title": "SWE-bench: Can Language Models Resolve Real-World GitHub Issues?", "url": "https://arxiv.org/abs/2310.06770", "snippet": "Benchmark for language model agents."},
    "expected_keep": true
  }
]
```

- [ ] **Step 2: Write failing baseline tests**

Create `crawler-service/tests/test_search_quality_baseline.py`:

```python
import json
from pathlib import Path

from crawler.search import normalize_search_result
from crawler.filters import is_excluded_domain


def test_normalize_search_result_preserves_engine_keyword_rank():
    item = normalize_search_result(
        {"title": "GitHub Copilot coding agent", "url": "https://github.blog/changelog/x", "snippet": "New coding agent."},
        keyword="github copilot coding agent",
        engine="bing",
        rank=2,
    )
    assert item["title"] == "GitHub Copilot coding agent"
    assert item["metadata"]["search_keyword"] == "github copilot coding agent"
    assert item["metadata"]["search_engine"] == "bing"
    assert item["metadata"]["search_rank"] == 2


def test_fixture_low_value_domains_are_rejected():
    cases = json.loads(Path("crawler-service/tests/fixtures/search_quality_cases.json").read_text(encoding="utf-8"))
    rejected = [case for case in cases if not case["expected_keep"]]
    assert rejected
    for case in rejected:
        assert is_excluded_domain(case["raw"]["url"])
```

- [ ] **Step 3: Implement minimal normalization**

Add to `crawler-service/crawler/search.py`:

```python
def normalize_search_result(raw: dict, *, keyword: str, engine: str, rank: int) -> dict:
    title = (raw.get("title") or "").strip()
    url = (raw.get("url") or "").strip()
    snippet = (raw.get("snippet") or "").strip()
    return {
        "title": title,
        "url": url,
        "snippet": snippet,
        "metadata": {
            "search_keyword": keyword,
            "search_engine": engine,
            "search_rank": rank,
        },
    }
```

- [ ] **Step 4: Run tests**

Run:

```powershell
crawler-service\.venv\Scripts\python.exe -m pytest crawler-service\tests\test_search_quality_baseline.py -q --tb=short
```

Expected: all tests pass.

---

### Task 2: Section-Aware Query Planner

**Files:**
- Create: `crawler-service/crawler/search_planner.py`
- Test: `crawler-service/tests/test_search_planner.py`
- Modify: `crawler-service/crawler/crawler_agent.py`

**Interfaces:**
- Produces: `SearchQueryPlan(section_name: str, queries: list[SearchQueryVariant], max_total_results: int)`
- Produces: `build_search_query_plan(section: PlannedSection, crawl_plan: SourceCrawlPlan, *, config_snapshot: dict) -> SearchQueryPlan`
- Consumes: `PlannedSection`, `SourceCrawlPlan.active_keywords`, `recommended_engine`, `adjusted_max_items`.

- [ ] **Step 1: Write tests for query variants**

Create `crawler-service/tests/test_search_planner.py`:

```python
from crawler.digest_orchestrator import PlannedSection
from crawler.source_agent import SourceCrawlPlan
from crawler.search_planner import build_search_query_plan


def test_open_source_adds_project_intent_variants():
    section = PlannedSection(name="open_source", source_type="keyword", keywords=["AI developer tools"], max_items=4, engine="bing")
    plan = SourceCrawlPlan(section_name="open_source", active_keywords=["AI developer tools"], recommended_engine="bing", adjusted_max_items=4)
    query_plan = build_search_query_plan(section, plan, config_snapshot={})
    queries = [q.query for q in query_plan.queries]
    assert "AI developer tools github" in queries
    assert "AI developer tools release" in queries
    assert query_plan.max_total_results == 8


def test_paper_adds_academic_domains_without_dropping_original():
    section = PlannedSection(name="paper", source_type="keyword", keywords=["LLM agent benchmark"], max_items=3, engine="bing")
    plan = SourceCrawlPlan(section_name="paper", active_keywords=["LLM agent benchmark"], recommended_engine="bing", adjusted_max_items=3)
    query_plan = build_search_query_plan(section, plan, config_snapshot={})
    queries = [q.query for q in query_plan.queries]
    assert "LLM agent benchmark" in queries
    assert "site:arxiv.org LLM agent benchmark" in queries
    assert "site:openreview.net LLM agent benchmark" in queries
```

- [ ] **Step 2: Implement planner**

Create `crawler-service/crawler/search_planner.py`:

```python
from dataclasses import dataclass

from crawler.digest_orchestrator import PlannedSection
from crawler.source_agent import SourceCrawlPlan
from config import settings


@dataclass(frozen=True)
class SearchQueryVariant:
    query: str
    engine: str
    max_results: int
    time_range: str
    intent: str


@dataclass(frozen=True)
class SearchQueryPlan:
    section_name: str
    queries: list[SearchQueryVariant]
    max_total_results: int


def _section_variants(section_name: str, keyword: str) -> list[tuple[str, str]]:
    base = keyword.strip()
    if not base:
        return []
    if section_name == "open_source":
        return [(base, "base"), (f"{base} github", "project"), (f"{base} release", "release")]
    if section_name == "paper":
        return [(base, "base"), (f"site:arxiv.org {base}", "arxiv"), (f"site:openreview.net {base}", "openreview")]
    if section_name == "dev_tool":
        return [(base, "base"), (f"{base} changelog", "release"), (f"{base} docs", "docs")]
    return [(base, "base"), (f"{base} analysis", "analysis")]


def build_search_query_plan(section: PlannedSection, crawl_plan: SourceCrawlPlan, *, config_snapshot: dict) -> SearchQueryPlan:
    seen: set[str] = set()
    variants: list[SearchQueryVariant] = []
    total_budget = max(crawl_plan.adjusted_max_items, section.max_items) * settings.digest_section_result_multiplier
    keywords = crawl_plan.active_keywords or section.keywords
    per_query = max(2, min(8, total_budget // max(1, len(keywords) * 2)))
    for keyword in keywords:
        for query, intent in _section_variants(section.name, keyword):
            if query.lower() in seen:
                continue
            seen.add(query.lower())
            variants.append(SearchQueryVariant(
                query=query,
                engine=crawl_plan.recommended_engine or section.engine or "bing",
                max_results=per_query,
                time_range=section.time_range,
                intent=intent,
            ))
    return SearchQueryPlan(section_name=section.name, queries=variants, max_total_results=total_budget)
```

- [ ] **Step 3: Integrate into crawler agent behind existing behavior**

In `crawler-service/crawler/crawler_agent.py`, replace the direct `for kw in plan.active_keywords` search loop with query-plan iteration. Preserve `crawl_by_keyword(..., skip_dedup=True)`.

- [ ] **Step 4: Verify**

Run:

```powershell
crawler-service\.venv\Scripts\python.exe -m pytest crawler-service\tests\test_search_planner.py crawler-service\tests\test_task_executor.py -q --tb=short
```

Expected: all tests pass.

---

### Task 3: Deterministic Search Result Ranker

**Files:**
- Create: `crawler-service/crawler/search_ranker.py`
- Test: `crawler-service/tests/test_search_ranker.py`
- Modify: `crawler-service/crawler/crawler_agent.py`

**Interfaces:**
- Produces: `score_search_candidate(section_name: str, keyword: str, title: str, url: str, snippet: str, metadata: dict | None = None) -> dict`
- Produces: `rank_search_candidates(section_name: str, keyword: str, candidates: list) -> list`

- [ ] **Step 1: Write ranking tests**

Create `crawler-service/tests/test_search_ranker.py`:

```python
from crawler.search_ranker import rank_search_candidates, score_search_candidate


def test_ranker_prefers_primary_sources_over_generic_definitions():
    candidates = [
        {"title": "What is software?", "url": "https://www.geeksforgeeks.org/computer-science-fundamentals/software-and-its-types/", "snippet": "Definition."},
        {"title": "GitHub Copilot adds coding agent workflow", "url": "https://github.blog/changelog/copilot-agent", "snippet": "Developer workflow update."},
    ]
    ranked = rank_search_candidates("hot_trend", "GitHub Copilot coding agent", candidates)
    assert ranked[0]["url"].startswith("https://github.blog")
    assert ranked[0]["metadata"]["relevance_score"] > ranked[1]["metadata"]["relevance_score"]


def test_paper_ranker_boosts_arxiv_and_openreview():
    scored = score_search_candidate("paper", "LLM agent benchmark", "SWE-bench", "https://arxiv.org/abs/2310.06770", "benchmark paper")
    assert scored["score"] >= 0.7
```

- [ ] **Step 2: Implement ranker**

Create `crawler-service/crawler/search_ranker.py` with deterministic features: section domain boost, title keyword overlap, snippet overlap, low-value path penalty, generic homepage penalty, and original search rank penalty.

- [ ] **Step 3: Apply before page crawling expansion**

In `CrawlerAgent._crawl`, sort keyword search results with `rank_search_candidates()` before `results.extend(...)`. Keep final `dedup_results()` unchanged.

- [ ] **Step 4: Verify**

Run:

```powershell
crawler-service\.venv\Scripts\python.exe -m pytest crawler-service\tests\test_search_ranker.py crawler-service\tests\test_search.py crawler-service\tests\test_crawler_agent.py -q --tb=short
```

Expected: all tests pass.

---

### Task 4: Adaptive Budget and Engine Health

**Files:**
- Modify: `crawler-service/crawler/search.py`
- Modify: `crawler-service/crawler/search_planner.py`
- Test: `crawler-service/tests/test_search_planner.py`

**Interfaces:**
- Consumes: existing `get_selector_health()`.
- Produces: `choose_engine(primary: str, *, keyword: str, section_name: str, selector_health: dict) -> str`.

- [ ] **Step 1: Add tests for unhealthy engine fallback**

In `crawler-service/tests/test_search_planner.py`, add:

```python
from crawler.search_planner import choose_engine


def test_choose_engine_avoids_repeated_zero_result_engine():
    health = {"bing": {"total_attempts": 5, "zero_results": 5}, "sogou": {"total_attempts": 2, "zero_results": 0}}
    assert choose_engine("bing", keyword="AI coding agent", section_name="hot_trend", selector_health=health) == "sogou"
```

- [ ] **Step 2: Implement conservative engine choice**

Add `choose_engine()` to `search_planner.py`. Switch only when primary has at least 3 attempts and zero-result ratio is at least 0.8.

- [ ] **Step 3: Wire into query planning**

Call `get_selector_health()` from `search.py` inside `build_search_query_plan()` and set each variant engine through `choose_engine()`.

- [ ] **Step 4: Verify**

Run:

```powershell
crawler-service\.venv\Scripts\python.exe -m pytest crawler-service\tests\test_search_planner.py crawler-service\tests\test_digest_orchestrator.py -q --tb=short
```

Expected: all tests pass.

---

### Task 5: Event-Level Grouping Before Digest Generation

**Files:**
- Modify: `crawler-service/crawler/dedup.py`
- Modify: `crawler-service/crawler/digest_orchestrator.py`
- Test: `crawler-service/tests/test_digest_orchestrator.py`

**Interfaces:**
- Produces: `group_event_candidates(results: list, *, section_name: str) -> list[dict]`
- Consumes: title, URL domain, canonical URL, and markdown/snippet text.

- [ ] **Step 1: Write tests for multi-source same-event grouping**

Add to `crawler-service/tests/test_digest_orchestrator.py`:

```python
from crawler.dedup import group_event_candidates


def test_group_event_candidates_merges_same_release_from_multiple_sources():
    results = [
        {"title": "OpenAI releases new Responses API features", "url": "https://openai.com/index/a", "markdown": "Responses API features for developers"},
        {"title": "Responses API gets new developer features", "url": "https://github.blog/index/b", "markdown": "OpenAI Responses API developer update"},
    ]
    groups = group_event_candidates(results, section_name="hot_trend")
    assert len(groups) == 1
    assert len(groups[0]["source_urls"]) == 2
```

- [ ] **Step 2: Implement grouping helper**

In `crawler-service/crawler/dedup.py`, add a helper that builds a normalized event key from title tokens plus product/project tokens. It must not replace strict dedup; it only supplies grouping metadata.

- [ ] **Step 3: Attach grouping metadata to section documents**

In `DigestOrchestrator._merge_results()` or the nearest section-document build path, attach `event_group_key` and `related_source_urls` to item metadata where available.

- [ ] **Step 4: Verify**

Run:

```powershell
crawler-service\.venv\Scripts\python.exe -m pytest crawler-service\tests\test_digest_orchestrator.py crawler-service\tests\test_digest_gen_agent.py -q --tb=short
```

Expected: all tests pass.

---

### Task 6: Search Diagnostics in Digest Detail

**Files:**
- Modify: `crawler-service/crawler/digest_orchestrator.py`
- Modify: `crawler-service/standalone/routes.py`
- Modify: `frontend/src/views/admin/digest/Detail.vue`
- Test: `crawler-service/tests/test_digest_api.py`

**Interfaces:**
- Produces in `ai_search_metadata.orchestrator_plan`: `search_diagnostics` entries containing section, query, engine, requested, returned, kept, filtered, top_domains.
- Consumes existing `/digests/task/{id}` detail payload.

- [ ] **Step 1: Add API test**

In `crawler-service/tests/test_digest_api.py`, create a failed or completed task with metadata:

```python
await repo.save_ai_search_metadata(task_id, {
    "orchestrator_plan": {
        "search_diagnostics": [
            {"section": "hot_trend", "query": "AI coding agent", "engine": "bing", "returned": 6, "kept": 3}
        ]
    }
})
```

Assert `/digests/task/{task_id}` returns `orchestrator_plan.search_diagnostics[0].kept == 3`.

- [ ] **Step 2: Persist diagnostics**

In `DigestOrchestrator`, append search diagnostics to `plan_log` and `config_snapshot` metadata before task completion. Use existing metadata save path; do not add a table.

- [ ] **Step 3: Render diagnostics**

In `frontend/src/views/admin/digest/Detail.vue`, show a compact table: section, query, engine, returned, kept, top domains. Keep it behind existing detail view; no public UI changes.

- [ ] **Step 4: Verify**

Run:

```powershell
crawler-service\.venv\Scripts\python.exe -m pytest crawler-service\tests\test_digest_api.py -q --tb=short
cd frontend; npm run build
```

Expected: API test passes and frontend build passes.

---

## Final Regression

Run the full verification set:

```powershell
crawler-service\.venv\Scripts\python.exe -m pytest crawler-service\tests -q --tb=short
```

```powershell
cd D:\software\item\nanmuli-blog\backend
mvn test
```

```powershell
cd D:\software\item\nanmuli-blog\frontend
npm run build
```

Expected:
- crawler tests pass.
- backend tests pass.
- frontend build passes.
- Public `/api/digest*` remains publishable-only.
- Admin `/api/v1/digests/task/{id}` shows search diagnostics for failed and completed digest tasks.

## Rollout Notes

- Ship Tasks 1-3 first behind deterministic tests; they improve relevance without changing public contracts.
- Ship Tasks 4-6 after observing at least one real digest run, because engine health and diagnostics need live behavior to tune.
- Do not tune thresholds from intuition alone; compare digest quality score, number of publishable sections, duplicate count, and source diversity before and after.
