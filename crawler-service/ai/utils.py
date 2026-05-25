"""AI 模块公共工具函数"""

import json
import re

# 匹配 markdown 代码块中的 JSON
JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*\n?(.*?)```", re.DOTALL)


def extract_json(response: str) -> str:
    """从 AI 响应中提取 JSON 字符串

    优先级：markdown 代码块 → raw_decode → 手工括号匹配
    """
    matcher = JSON_BLOCK_RE.search(response)
    if matcher:
        candidate = matcher.group(1).strip()
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass

    # 查找第一个 JSON 起始符（对象或数组）
    obj_start = response.find("{")
    arr_start = response.find("[")
    if obj_start < 0 and arr_start < 0:
        raise ValueError("No JSON found in AI response")

    if obj_start < 0:
        start = arr_start
    elif arr_start < 0:
        start = obj_start
    else:
        start = min(obj_start, arr_start)

    # 优先使用标准库 raw_decode，正确处理嵌套转义
    decoder = json.JSONDecoder()
    try:
        obj, end = decoder.raw_decode(response, idx=start)
        return response[start:end]
    except json.JSONDecodeError:
        pass

    # Fallback: 手工括号匹配（覆盖 raw_decode 失败的边缘情况）
    open_ch = response[start]
    close_ch = "}" if open_ch == "{" else "]"

    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(response)):
        c = response[i]
        if escape:
            escape = False
            continue
        if c == "\\" and in_string:
            escape = True
            continue
        if c == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return response[start:i + 1]

    raise ValueError("No balanced JSON found in AI response")
