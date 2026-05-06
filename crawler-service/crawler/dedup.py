"""
内容去重模块

提供多层级去重能力：
- Layer 1: URL精确去重
- Layer 2: 内容指纹去重（SimHash简化版）
- Layer 3: 标题相似度去重
"""

import hashlib
import re
from typing import List, Optional
import difflib
from collections import Counter


class ContentFingerprint:
    """内容指纹，用于检测重复/相似内容"""

    def __init__(self, text: str):
        self.text = text or ""
        self._hash = None
        self._simhash = None

    @property
    def exact_hash(self) -> str:
        """精确哈希（用于完全相同的文本）"""
        if self._hash is None:
            self._hash = hashlib.sha256(self.text.encode('utf-8')).hexdigest()
        return self._hash

    @property
    def simhash(self) -> int:
        """简化版SimHash（用于检测内容改写/转载）"""
        if self._simhash is None:
            self._simhash = self._compute_simhash()
        return self._simhash

    def _compute_simhash(self) -> int:
        """
        简化版SimHash算法：
        1. 提取特征词（2-gram，带词频权重）
        2. 每个特征词用稳定哈希（md5）后按位加权
        3. 结果归并为64位整数

        注意：使用 hashlib.md5 替代内置 hash()，避免 Python hash 随机化
        导致不同进程/重启后同一文本得到不同的 SimHash。
        """
        features = self._extract_features(self.text)
        if not features:
            return 0

        # 计算词频权重
        freq = Counter(features)

        # 64位向量
        vector = [0] * 64

        for feature in features:
            # 稳定哈希：md5 取前16个hex字符转int（64位）
            h = int(hashlib.md5(feature.encode('utf-8')).hexdigest()[:16], 16)
            weight = freq[feature]  # 词频越高权重越大

            for i in range(64):
                bit = (h >> i) & 1
                if bit:
                    vector[i] += weight
                else:
                    vector[i] -= weight

        # 生成simhash
        result = 0
        for i in range(64):
            if vector[i] > 0:
                result |= (1 << i)
        return result

    @staticmethod
    def _extract_features(text: str) -> List[str]:
        """提取文本特征词（简化版：按2-gram分词）"""
        if not text:
            return []

        # 清理文本
        cleaned = re.sub(r'[^一-鿿\w\s]', ' ', text.lower())
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        words = cleaned.split()
        if len(words) < 2:
            return words

        # 2-gram特征
        features = []
        for i in range(len(words) - 1):
            bigram = f"{words[i]}_{words[i + 1]}"
            features.append(bigram)

        return features


def hamming_distance(hash1: int, hash2: int) -> int:
    """计算两个64位整数的汉明距离"""
    return bin(hash1 ^ hash2).count('1')


class DedupEngine:
    """去重引擎"""

    # 汉明距离阈值：≤3视为高度相似（可能是转载/改写）
    SIMHASH_THRESHOLD = 3
    # 标题相似度阈值：≥0.8视为相似
    TITLE_SIMILARITY_THRESHOLD = 0.8

    def __init__(self):
        self._url_seen: set = set()
        self._fingerprint_seen: List[ContentFingerprint] = []
        self._title_seen: List[str] = []

    def add_reference(self, url: str, title: str = "", content: str = ""):
        """添加参考内容（如历史采集记录），用于跨任务去重"""
        self._url_seen.add(self._normalize_url(url))
        if title:
            self._title_seen.append(title.lower().strip())
        if content:
            self._fingerprint_seen.append(ContentFingerprint(content))

    def is_duplicate(self, url: str, title: str = "", content: str = "") -> dict:
        """
        检测是否为重复内容

        Returns:
            {
                "is_duplicate": bool,
                "reason": str,  # "url" | "content_similar" | "title_similar" | "none"
                "confidence": float,  # 0-1
            }
        """
        # Layer 1: URL精确去重
        normalized_url = self._normalize_url(url)
        if normalized_url in self._url_seen:
            return {
                "is_duplicate": True,
                "reason": "url",
                "confidence": 1.0
            }

        # Layer 2: 内容相似度去重（需要content）
        if content and len(content) >= 100:
            fp = ContentFingerprint(content)
            for seen_fp in self._fingerprint_seen:
                distance = hamming_distance(fp.simhash, seen_fp.simhash)
                if distance <= self.SIMHASH_THRESHOLD:
                    confidence = 1.0 - (distance / self.SIMHASH_THRESHOLD) * 0.3
                    return {
                        "is_duplicate": True,
                        "reason": "content_similar",
                        "confidence": min(confidence, 0.95)
                    }

        # Layer 3: 标题相似度去重
        if title:
            title_lower = title.lower().strip()
            for seen_title in self._title_seen:
                similarity = self._title_similarity(title_lower, seen_title)
                if similarity >= self.TITLE_SIMILARITY_THRESHOLD:
                    return {
                        "is_duplicate": True,
                        "reason": "title_similar",
                        "confidence": similarity
                    }

        return {
            "is_duplicate": False,
            "reason": "none",
            "confidence": 0.0
        }

    def add(self, url: str, title: str = "", content: str = ""):
        """添加新内容到去重库"""
        self._url_seen.add(self._normalize_url(url))
        if title:
            self._title_seen.append(title.lower().strip())
        if content and len(content) >= 100:
            self._fingerprint_seen.append(ContentFingerprint(content))

    @staticmethod
    def _normalize_url(url: str) -> str:
        """URL标准化：去协议、去www、去尾部斜杠、去追踪参数"""
        url = url.lower().strip()
        # 去协议
        url = re.sub(r'^https?://', '', url)
        # 去www
        url = re.sub(r'^www\.', '', url)
        # 去尾部斜杠
        url = url.rstrip('/')
        # 去常见追踪参数
        url = re.sub(r'[?&](utm_[^&=]*|ref|source)=[^&]*', '', url)
        url = re.sub(r'\?+$', '', url)
        return url

    @staticmethod
    def _title_similarity(title1: str, title2: str) -> float:
        """
        计算两个标题的相似度（Jaccard系数 60% + 编辑距离 40%）
        返回 0-1 的浮点数

        编辑距离辅助解决 "Spring Boot 3" vs "Spring Boot 3 的新特性"
        这类空格/小差异导致的 Jaccard 低估问题。
        """
        if not title1 or not title2:
            return 0.0

        # 如果完全相同
        if title1 == title2:
            return 1.0

        # 提取关键词集合（去除常见停用词）
        stopwords = {'的', '了', '在', '是', '我', '有', '和', '就', '不', '人',
                     '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去',
                     '你', '会', '着', '没有', '看', '好', '自己', '这', '那',
                     'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
                     'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                     'would', 'could', 'should', 'may', 'might', 'must', 'shall',
                     'can', 'need', 'dare', 'ought', 'used', 'to', 'of', 'in',
                     'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into',
                     'through', 'during', 'before', 'after', 'above', 'below',
                     'between', 'under', 'again', 'further', 'then', 'once'}

        words1 = set(w for w in re.findall(r'[一-鿿\w]+', title1) if w not in stopwords)
        words2 = set(w for w in re.findall(r'[一-鿿\w]+', title2) if w not in stopwords)

        if not words1 or not words2:
            return 0.0

        # Jaccard系数
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        jaccard = intersection / union if union > 0 else 0

        # 编辑距离相似度（对空格/标点差异更敏感）
        seq_ratio = difflib.SequenceMatcher(None, title1, title2).ratio()

        # 综合：Jaccard 60% + 编辑距离 40%
        return jaccard * 0.6 + seq_ratio * 0.4


# 便捷函数：对搜索结果列表进行去重
def dedup_results(
    results: list,
    content_preview_length: int = 500,
    history_engine: Optional[DedupEngine] = None
) -> list:
    """
    对爬取结果列表进行去重，支持跨任务历史去重。

    Args:
        results: CrawlResult字典列表或对象列表
        content_preview_length: 用于相似度计算的内容预览长度
        history_engine: 历史去重引擎（传入则可与历史记录去重，适合日报跨板块/跨日去重）

    Returns:
        去重后的结果列表
    """
    engine = history_engine if history_engine else DedupEngine()
    unique_results = []

    for result in results:
        # 兼容字典和对象
        url = result.get('url', '') if isinstance(result, dict) else getattr(result, 'url', '')
        title = result.get('title', '') if isinstance(result, dict) else getattr(result, 'title', '')
        content = result.get('markdown', '') if isinstance(result, dict) else getattr(result, 'markdown', '')

        # 使用内容前N个字符作为指纹
        content_preview = content[:content_preview_length] if content else ""

        check = engine.is_duplicate(url, title, content_preview)

        if not check["is_duplicate"]:
            unique_results.append(result)
            engine.add(url, title, content_preview)

    return unique_results
