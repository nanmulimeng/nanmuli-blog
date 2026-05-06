#!/usr/bin/env python3
"""Phase 1-3 全面验证脚本"""
import sys
sys.path.insert(0, '.')

print('=== 1. 验证 dedup.py ===')
from crawler.dedup import DedupEngine, hamming_distance, ContentFingerprint, dedup_results

# 测试1: hamming_distance
d = hamming_distance(0b1010, 0b1000)
assert d == 1, f'hamming_distance failed: {d}'
print(f'  hamming_distance: OK (d={d})')

# 测试2: SimHash 稳定性（核心修复：hash() → hashlib.md5）
fp1 = ContentFingerprint('hello world test content')
fp2 = ContentFingerprint('hello world test content')
assert fp1.simhash == fp2.simhash, f'SimHash不稳定: {fp1.simhash} != {fp2.simhash}'
print(f'  SimHash稳定性: OK (hash={fp1.simhash})')

# 测试3: 标题相似度（含编辑距离辅助）
engine = DedupEngine()
sim = engine._title_similarity('spring boot 3', 'spring boot 3 的新特性')
print(f'  标题相似度(空格差异): {sim:.3f}')
assert sim > 0.5, f'标题相似度过低: {sim}'

# 测试4: 跨任务去重（history_engine参数）
dedup_engine = DedupEngine()
dedup_engine.add_reference('https://example.com/a', 'Test Title', 'Test content here')
results = [
    {'url': 'https://example.com/a', 'title': 'Test Title', 'markdown': 'Test content'},
    {'url': 'https://example.com/b', 'title': 'Another Title', 'markdown': 'Different content'},
]
deduped = dedup_results(results, history_engine=dedup_engine)
assert len(deduped) == 1, f'跨任务去重失败: {len(deduped)}'
print(f'  跨任务去重: OK (1/2保留)')

print()
print('=== 2. 验证 quality.py ===')
from crawler.quality import evaluate_content, ContentQuality

# 测试5: 字数统计（中英文加权 1.0 / 1.5）
wc = ContentQuality._count_words('Hello world 这是一个测试')
print(f'  字数统计: {wc} (中文6 + 英文2*1.5=3 = 9)')
assert wc == 9, f'字数统计错误: {wc}'

# 测试6: 时效性检测
import datetime
CURRENT_YEAR = datetime.datetime.now().year

fresh = ContentQuality._detect_freshness(f'https://example.com/{CURRENT_YEAR}/05/article.html', 'content')
print(f'  时效性(今年URL): {fresh}')
assert fresh['bonus'] == 5, f'时效性bonus错误: {fresh}'

fresh_old = ContentQuality._detect_freshness('https://example.com/2020/05/article.html', 'content')
print(f'  时效性(旧URL): {fresh_old}')
assert fresh_old['bonus'] == 0, f'过时内容bonus错误: {fresh_old}'

fresh2 = ContentQuality._detect_freshness('https://example.com/article.html', 'Updated: 2020-05-01 content')
print(f'  时效性(内容日期): {fresh2}')
assert fresh2['bonus'] == 0, f'过时内容bonus错误: {fresh2}'

# 测试7: 综合评估（官方文档应通过）
eval_result = evaluate_content(
    url='https://docs.spring.io/spring-boot/docs/current/reference/html/',
    title='Spring Boot Reference Documentation',
    content='## Overview\n\nSpring Boot makes it easy.\n\n```java\n@SpringBootApplication\npublic class Demo {\n}\n```\n\n- Feature 1\n- Feature 2\n\nThis is a comprehensive guide.'
)
print(f'  综合评估(官方文档): final_score={eval_result["final_score"]}, verdict={eval_result["verdict"]}')
assert eval_result['verdict'] == 'pass', f'官方文档应通过: {eval_result}'

# 测试8: 内容农场严格过滤
eval_low = evaluate_content(
    url='https://baijiahao.baidu.com/s?id=123',
    title='震惊！99%的人不知道的编程技巧',
    content='这是一个很短的内容。限时优惠，点击购买！'
)
print(f'  综合评估(内容农场): final_score={eval_low["final_score"]}, verdict={eval_low["verdict"]}')
assert eval_low['verdict'] == 'reject', f'内容农场应拒绝: {eval_low}'

# 测试9: 内容农场边界（质量分50+但综合分不够）
eval_border = evaluate_content(
    url='https://toutiao.com/article/123',
    title='技术分享',
    content='这是一篇中等质量的技术文章，有一些代码示例和说明。' * 20  # 增加长度
)
print(f'  综合评估(低来源边界): final_score={eval_border["final_score"]}, verdict={eval_border["verdict"]}')
# low来源即使分数高也只给review，不会pass
assert eval_border['verdict'] != 'pass', f'low来源不应直接pass: {eval_border}'

print()
print('=== 3. 验证 search.py 辅助函数 ===')
from crawler.search import _is_whole_word_match, _is_relevant_to_keyword

# 测试10: 整词匹配（核心修复：子串→整词）
assert _is_whole_word_match('javascript tutorial', 'java') == False, 'Java不应匹配JavaScript'
assert _is_whole_word_match('java tutorial', 'java') == True, 'Java应匹配java'
assert _is_whole_word_match('spring boot 3', 'spring boot') == True, '多词应匹配'
print('  整词匹配: OK')

# 测试11: 相关性判断
assert _is_relevant_to_keyword('Java', 'JavaScript Tutorial', 'Learn JS') == False
assert _is_relevant_to_keyword('Java', 'Java Tutorial', 'Learn Java') == True
assert _is_relevant_to_keyword('Spring Boot', 'Spring Boot 3 New Features', 'Guide') == True
print('  相关性判断: OK')

print()
print('=== 所有验证通过 ===')
