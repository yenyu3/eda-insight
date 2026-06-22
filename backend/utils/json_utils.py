"""utils/json_utils.py — JSON 解析與 mock 串流工具函式。"""

import re
import json
from typing import Generator


def safe_parse_json(text: str) -> dict:
    """清除 AI 可能附加的 markdown fence 後解析 JSON；解析失敗回傳空 dict。"""
    cleaned = text.strip()
    cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
    cleaned = re.sub(r'\s*```$', '', cleaned)
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        return {}


def mock_stream(text: str) -> Generator[str, None, None]:
    """回傳假串流資料，每次 yield 一個詞（以空格分割）。"""
    for word in text.split():
        yield word + " "
