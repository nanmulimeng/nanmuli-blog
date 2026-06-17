"""Publish gate for generated digest content."""

from config import settings


def _configured_core_sections() -> list[str]:
    raw = getattr(settings, "digest_publish_core_sections", "") or ""
    return [item.strip() for item in raw.split(",") if item.strip()]


def _present_sections(digest_content) -> set[str]:
    sections = getattr(digest_content, "sections", []) or []
    present = set()
    for section in sections:
        if getattr(section, "items", None):
            category = (getattr(section, "category", "") or "").strip()
            if category:
                present.add(category)
    return present


def evaluate_digest_publish_quality(digest_content) -> tuple[dict, bool]:
    from crawler.digest_orchestrator import _calculate_digest_output_quality

    quality = _calculate_digest_output_quality(digest_content)
    threshold = float(getattr(settings, "digest_optimization_target_score", 0.65) or 0.65)
    core_sections = _configured_core_sections()
    min_core_sections = int(getattr(settings, "digest_publish_min_core_sections", 0) or 0)
    min_core_sections = min(min_core_sections, len(core_sections)) if core_sections else 0

    present = _present_sections(digest_content)
    present_core = [section for section in core_sections if section in present]
    missing_core = [section for section in core_sections if section not in present]

    gate_failures = []
    if min_core_sections and len(present_core) < min_core_sections:
        gate_failures.append("core_section_coverage")
        quality.setdefault("suggestions", []).append(
            "核心日报板块覆盖不足，建议补充 AI 动态、开源项目、开发工具、技术文章或论文来源"
        )

    quality.update({
        "core_sections": core_sections,
        "core_section_count": len(present_core),
        "min_core_sections": min_core_sections,
        "missing_core_sections": missing_core,
        "gate_failures": gate_failures,
    })
    publishable = quality.get("score", 0.0) >= threshold and not gate_failures
    return quality, publishable


def digest_quality_error_message(quality: dict) -> str:
    score = quality.get("score", 0.0)
    suggestions = quality.get("suggestions") or []
    first_suggestion = f"; {suggestions[0]}" if suggestions else ""
    return f"Digest quality below publish threshold (score={score:.3f}){first_suggestion}"


async def save_digest_publish_quality(
    repository,
    task_id: int,
    quality: dict,
    publishable: bool,
    stage: str,
) -> None:
    """Persist the publish gate result into task metadata for diagnostics."""
    if repository is None or not hasattr(repository, "save_ai_search_metadata"):
        return
    await repository.save_ai_search_metadata(task_id, {
        "digest_publishable": publishable,
        "digest_publish_stage": stage,
        "digest_publish_quality": quality,
    })
