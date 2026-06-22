import json
import re
from typing import Any, Generator


def safe_parse_json(text: str) -> Any:
    """清除 AI 可能附加的 markdown fence 後解析 JSON；解析失敗回傳空 dict。

    回傳型別標為 Any，因為 json.loads 可解析出 dict / list / str / number。
    """
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError, TypeError):
        return {}


def mock_stream(text: str) -> Generator[str, None, None]:
    """回傳假串流資料，逐字元輸出以模擬 LLM streaming 效果（對中文更自然）。"""
    for ch in text:
        yield ch
