from crawler.search_ranker import rank_search_candidates, score_search_candidate


def test_ranker_prefers_primary_sources_over_generic_definitions():
    candidates = [
        {
            "title": "What is software?",
            "url": "https://www.geeksforgeeks.org/computer-science-fundamentals/software-and-its-types/",
            "snippet": "Definition.",
        },
        {
            "title": "GitHub Copilot adds coding agent workflow",
            "url": "https://github.blog/changelog/copilot-agent",
            "snippet": "Developer workflow update.",
        },
    ]

    ranked = rank_search_candidates("hot_trend", "GitHub Copilot coding agent", candidates)

    assert ranked[0]["url"].startswith("https://github.blog")
    assert ranked[0]["metadata"]["relevance_score"] > ranked[1]["metadata"]["relevance_score"]


def test_paper_ranker_boosts_arxiv_and_openreview():
    scored = score_search_candidate(
        "paper",
        "LLM agent benchmark",
        "SWE-bench",
        "https://arxiv.org/abs/2310.06770",
        "benchmark paper",
    )

    assert scored["score"] >= 0.7
