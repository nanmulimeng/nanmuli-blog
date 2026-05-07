import unittest
from unittest.mock import AsyncMock, patch

from crawler import search


class _FakeResponse:
    def __init__(self, text: str = "<html></html>", status_code: int = 200, url: str = "https://example.com"):
        self.text = text
        self.status_code = status_code
        self.url = url

    def raise_for_status(self):
        return None


class _FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, headers=None, timeout=None):
        self.calls.append(("get", url))
        return _FakeResponse()


class _BaiduDecodeClient:
    async def head(self, *args, **kwargs):
        return _FakeResponse(status_code=502, url="http://www.baidu.com/link?url=encoded")

    async def get(self, *args, **kwargs):
        return _FakeResponse(status_code=502, url="http://www.baidu.com/link?url=encoded")


class SearchTests(unittest.IsolatedAsyncioTestCase):
    def test_single_keyword_must_match_title_or_snippet(self):
        self.assertFalse(
            search._is_relevant_to_keyword(
                "Docker",
                "Kubernetes Networking Guide",
                "CNI and ingress overview",
            )
        )
        self.assertTrue(
            search._is_relevant_to_keyword(
                "Docker",
                "Docker Compose Tutorial",
                "Container workflow guide",
            )
        )

    async def test_search_results_do_not_stop_after_first_empty_page(self):
        parse_results = AsyncMock(side_effect=[
            (10, 0),
            (10, 1),
        ])

        with patch.object(search, "_parse_search_results", parse_results), \
                patch.object(search.httpx, "AsyncClient", _FakeAsyncClient), \
                patch.object(search.asyncio, "sleep", AsyncMock()):
            urls = await search._get_search_results(
                keyword="docker",
                engine="bing",
                max_results=5,
                time_range="week",
            )

        self.assertGreaterEqual(parse_results.await_count, 2)
        self.assertEqual(len(urls), 0)

    async def test_baidu_unresolved_redirect_is_skipped(self):
        html = """
        <html><body>
          <div class="result">
            <h3><a href="http://www.baidu.com/link?url=encoded">Example</a></h3>
            <div class="c-abstract">Spring Boot tutorial guide</div>
          </div>
        </body></html>
        """

        urls = []
        raw_count, added_count = await search._parse_search_results(
            html=html,
            engine="baidu",
            config=search.SEARCH_ENGINES["baidu"],
            keyword="Spring Boot tutorial",
            max_results=5,
            seen_domains={},
            urls=urls,
            search_url="http://www.baidu.com/s?wd=Spring+Boot+tutorial",
            headers={"User-Agent": "Mozilla/5.0"},
            client=_BaiduDecodeClient(),
        )

        self.assertEqual(raw_count, 1)
        self.assertEqual(added_count, 0)
        self.assertEqual(urls, [])


if __name__ == "__main__":
    unittest.main()
