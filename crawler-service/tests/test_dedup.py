"""内容去重模块测试：ContentFingerprint / DedupEngine / hamming_distance / dedup_results"""

import pytest
from crawler.dedup import (
    ContentFingerprint,
    DedupEngine,
    hamming_distance,
    dedup_results,
)


# ============== 辅助 ==============

def _make_long_text(base: str, min_length: int = 150) -> str:
    """生成足够长的文本以满足 simhash 最低长度要求"""
    if len(base) >= min_length:
        return base
    return (base + " ") * (min_length // len(base) + 1)


# ============== ContentFingerprint ==============

class TestContentFingerprint:

    def test_exact_hash_deterministic(self):
        """同一文本两次调用 exact_hash 必须完全相同"""
        fp = ContentFingerprint("hello world 123")
        assert fp.exact_hash == fp.exact_hash

    def test_exact_hash_different_for_different_text(self):
        """不同文本必须产生不同的 exact_hash"""
        fp1 = ContentFingerprint("alpha content")
        fp2 = ContentFingerprint("beta content")
        assert fp1.exact_hash != fp2.exact_hash

    def test_simhash_stability(self):
        """SimHash 稳定性：同一文本两次构造必须得到完全相同的值（跨实例）"""
        text = _make_long_text("Python is a great programming language for web development")
        fp_a = ContentFingerprint(text)
        fp_b = ContentFingerprint(text)
        assert fp_a.simhash == fp_b.simhash

    def test_simhash_similar_content_small_distance(self):
        """相似内容的 SimHash 汉明距离应很小（<= 阈值）"""
        text_a = _make_long_text("Python is a great programming language for web development and data science")
        text_b = _make_long_text("Python is a great programming language for web development and machine learning")
        fp_a = ContentFingerprint(text_a)
        fp_b = ContentFingerprint(text_b)
        dist = hamming_distance(fp_a.simhash, fp_b.simhash)
        assert dist <= DedupEngine.SIMHASH_THRESHOLD

    def test_simhash_empty_text_returns_zero(self):
        """空文本的 simhash 应为 0"""
        fp = ContentFingerprint("")
        assert fp.simhash == 0

    def test_simhash_single_word_no_bigram_nonzero(self):
        """单词语无法生成 2-gram，但 _extract_features 返回该词自身，
        simhash 仍非零——验证这一行为符合实际实现"""
        fp = ContentFingerprint("word")
        # 单词只有 1 个 feature，无法形成 bigram，features 返回 ['word']
        # simhash 会对这单个 feature 计算哈希，结果非零
        assert fp.simhash != 0


# ============== hamming_distance ==============

class TestHammingDistance:

    def test_identical_hashes_zero(self):
        """相同的哈希汉明距离为 0"""
        h = 0b1010101010101010
        assert hamming_distance(h, h) == 0

    def test_all_bits_different(self):
        """所有位都不同的两个哈希，64 位全异"""
        assert hamming_distance(0, (1 << 64) - 1) == 64

    def test_one_bit_difference(self):
        """仅一位不同的汉明距离为 1"""
        h1 = 0b1000
        h2 = 0b0000
        assert hamming_distance(h1, h2) == 1


# ============== DedupEngine — Layer 1: URL 去重 ==============

class TestDedupEngineUrl:

    def test_exact_url_duplicate(self):
        """完全相同的 URL 应被标记为重复"""
        engine = DedupEngine()
        engine.add("https://example.com/article/1", "Title", "")
        result = engine.is_duplicate("https://example.com/article/1", "Other", "")
        assert result["is_duplicate"] is True
        assert result["reason"] == "url"
        assert result["confidence"] == 1.0

    def test_normalized_url_duplicate(self):
        """URL 标准化后相同的应被去重（协议/www/尾部斜杠/大小写）"""
        engine = DedupEngine()
        engine.add("https://www.Example.com/article/1/", "Title", "")
        result = engine.is_duplicate("http://example.com/article/1", "Other", "")
        assert result["is_duplicate"] is True
        assert result["reason"] == "url"

    def test_different_url_not_duplicate(self):
        """不同 URL 且不同标题不应被误判"""
        engine = DedupEngine()
        engine.add("https://example.com/a", "Alpha Article", "")
        result = engine.is_duplicate("https://example.com/b", "Beta Article", "")
        assert result["is_duplicate"] is False


# ============== DedupEngine — Layer 2: 内容 SimHash ==============

class TestDedupEngineContentSimhash:

    def test_similar_content_detected(self):
        """SimHash 相似的内容应被检测为重复"""
        engine = DedupEngine()
        text_a = _make_long_text("Python is a great programming language for web development and data science")
        text_b = _make_long_text("Python is a great programming language for web development and machine learning")
        engine.add("https://a.com", "Title A", text_a)
        result = engine.is_duplicate("https://b.com", "Title B", text_b)
        assert result["is_duplicate"] is True
        assert result["reason"] == "content_similar"

    def test_short_content_skips_simhash(self):
        """短内容（<100 字符）应跳过 simhash 层，不被误判"""
        engine = DedupEngine()
        engine.add("https://a.com", "Title A", "short")
        result = engine.is_duplicate("https://b.com", "Title B", "short")
        assert result["is_duplicate"] is False

    def test_empty_content_no_false_positive(self):
        """空内容不应触发内容去重"""
        engine = DedupEngine()
        engine.add("https://a.com", "Title A", "")
        result = engine.is_duplicate("https://b.com", "Title B", "")
        assert result["is_duplicate"] is False


# ============== DedupEngine — Layer 3: 标题 Jaccard ==============

class TestDedupEngineTitleSimilarity:

    def test_identical_title_duplicate(self):
        """完全相同的标题应被标记为重复"""
        engine = DedupEngine()
        engine.add("https://a.com", "Spring Boot 3 入门教程", "")
        result = engine.is_duplicate("https://b.com", "Spring Boot 3 入门教程", "")
        assert result["is_duplicate"] is True
        assert result["reason"] == "title_similar"
        assert result["confidence"] == 1.0

    def test_similar_title_above_threshold(self):
        """标题相似度 >= 0.8 应被检测为重复（仅空格/标点差异）"""
        engine = DedupEngine()
        engine.add("https://a.com", "Spring Boot 3 New Features Guide", "")
        result = engine.is_duplicate("https://b.com", "Spring Boot 3 New Features Guide!", "")
        assert result["is_duplicate"] is True
        assert result["reason"] == "title_similar"

    def test_different_title_not_duplicate(self):
        """差异明显的标题不应被误判"""
        engine = DedupEngine()
        engine.add("https://a.com", "Spring Boot 3 新特性", "")
        result = engine.is_duplicate("https://b.com", "Rust 异步编程实战指南", "")
        assert result["is_duplicate"] is False

    def test_empty_title_no_false_positive(self):
        """空标题不应触发标题去重"""
        engine = DedupEngine()
        engine.add("https://a.com", "", "")
        result = engine.is_duplicate("https://b.com", "", "")
        assert result["is_duplicate"] is False


# ============== DedupEngine — add_reference 跨任务去重 ==============

class TestDedupEngineReference:

    def test_history_engine_cross_task_dedup(self):
        """通过 add_reference 加载历史记录后，新 URL 应被检测为重复"""
        engine = DedupEngine()
        engine.add_reference("https://example.com/old", "Old Title", "")
        result = engine.is_duplicate("https://example.com/old", "New Title", "")
        assert result["is_duplicate"] is True
        assert result["reason"] == "url"


# ============== dedup_results 便捷函数 ==============

class TestDedupResults:

    def test_dict_list_dedup(self):
        """dict 列表输入应正常去重"""
        items = [
            {"url": "https://a.com/1", "title": "Title A", "markdown": "content a"},
            {"url": "https://a.com/1", "title": "Title A Dup", "markdown": "content b"},
            {"url": "https://b.com/2", "title": "Title B", "markdown": "content c"},
        ]
        result = dedup_results(items)
        assert len(result) == 2
        assert result[0]["url"] == "https://a.com/1"
        assert result[1]["url"] == "https://b.com/2"

    def test_object_list_dedup(self):
        """对象列表（含 .url/.title/.markdown 属性）应正常去重"""

        class FakeResult:
            def __init__(self, url, title, markdown):
                self.url = url
                self.title = title
                self.markdown = markdown

        items = [
            FakeResult("https://a.com/1", "Title A", "content"),
            FakeResult("https://a.com/1", "Title A Dup", "other"),
        ]
        result = dedup_results(items)
        assert len(result) == 1

    def test_history_engine_filters_cross_task(self):
        """history_engine 参数应实现跨任务去重"""
        history = DedupEngine()
        history.add("https://history.com/old", "Old Title", "")

        items = [
            {"url": "https://history.com/old", "title": "Old Title", "markdown": "old content"},
            {"url": "https://new.com/1", "title": "New Title", "markdown": "new content"},
        ]
        result = dedup_results(items, history_engine=history)
        assert len(result) == 1
        assert result[0]["url"] == "https://new.com/1"

    def test_empty_input_returns_empty(self):
        """空列表输入应返回空列表"""
        assert dedup_results([]) == []
