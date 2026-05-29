"""
report_parser.py — Yosys 合成報告解析模組

使用 re 模組解析 Yosys `stat` 指令輸出的純文字報告，
萃取 cell count、wire count、flip-flop count 等關鍵 PPA 指標。
"""

import re
import json
import os
from typing import Optional


def parse_synthesis_json(json_path: str) -> dict:
    """
    直接從 Yosys write_json 產生的 JSON 檔解析 PPA 指標。
    比解析文字輸出更可靠，不受 stdout/stderr 分流影響。
    """
    try:
        with open(json_path, "r", encoding="utf-8", errors="replace") as f:
            data = json.load(f)
    except Exception:
        return _empty_result()

    cell_count = 0
    wire_count = 0
    flip_flop_count = 0

    dff_prefixes = ("$_DFF_", "$_SDFF_", "$_SDFFE_", "$_DFFE_")

    for mod_data in data.get("modules", {}).values():
        cells = mod_data.get("cells", {})
        cell_count += len(cells)
        for cell_data in cells.values():
            t = cell_data.get("type", "")
            if any(t.startswith(p) for p in dff_prefixes):
                flip_flop_count += 1
        wire_count += len(mod_data.get("netnames", {}))

    return {
        "cell_count": cell_count,
        "wire_count": wire_count,
        "flip_flop_count": flip_flop_count,
        "critical_path_ns": None,
        "slack_ns": None,
        "area_estimate": _estimate_area(cell_count),
    }


def _empty_result() -> dict:
    return {
        "cell_count": 0,
        "wire_count": 0,
        "flip_flop_count": 0,
        "critical_path_ns": None,
        "slack_ns": None,
        "area_estimate": "unknown",
    }


def parse_synthesis_report(yosys_output: str) -> dict:
    """
    解析 Yosys stat 輸出文字，回傳結構化 PPA 指標 dict。

    回傳格式：
    {
        "cell_count": int,
        "wire_count": int,
        "flip_flop_count": int,
        "critical_path_ns": float | null,
        "slack_ns": float | null,
        "area_estimate": "small" | "medium" | "large"
    }

    注意：Yosys 免費版不輸出時序資訊，critical_path_ns / slack_ns 若無法萃取則為 null。
    """
    cell_count = _parse_cell_count(yosys_output)
    wire_count = _parse_wire_count(yosys_output)
    flip_flop_count = _parse_flip_flop_count(yosys_output)
    critical_path_ns = _parse_critical_path(yosys_output)
    slack_ns = _parse_slack(yosys_output)
    area_estimate = _estimate_area(cell_count)

    return {
        "cell_count": cell_count,
        "wire_count": wire_count,
        "flip_flop_count": flip_flop_count,
        "critical_path_ns": critical_path_ns,
        "slack_ns": slack_ns,
        "area_estimate": area_estimate,
    }


def _parse_cell_count(output: str) -> int:
    """萃取 'Number of cells: N' 或 'Number of cells (by type):' 前的數字。"""
    match = re.search(r'Number of cells:\s+(\d+)', output)
    if match:
        return int(match.group(1))
    return 0


def _parse_wire_count(output: str) -> int:
    """萃取 'Number of wires: N'。"""
    match = re.search(r'Number of wires:\s+(\d+)', output)
    if match:
        return int(match.group(1))
    return 0


def _parse_flip_flop_count(output: str) -> int:
    """
    計算所有 $_DFF_*_ 類型的 cell 數量（D flip-flop）。
    Yosys 會列出如：$_DFF_P_ 4
    """
    total = 0
    for m in re.finditer(r'\$_DFF_\w+_\s+(\d+)', output):
        total += int(m.group(1))
    return total


def _parse_critical_path(output: str) -> Optional[float]:
    """
    嘗試從 Yosys 輸出中萃取關鍵路徑延遲（ns）。
    Yosys 免費版通常不輸出此資訊，回傳 None 為正常。
    """
    match = re.search(r'(?:critical path|max delay)[^\d]*([\d.]+)\s*ns', output, re.IGNORECASE)
    if match:
        return float(match.group(1))
    return None


def _parse_slack(output: str) -> Optional[float]:
    """嘗試萃取 slack（ns）；Yosys 免費版通常無此資訊。"""
    match = re.search(r'slack[^\d]*([\d.]+)\s*ns', output, re.IGNORECASE)
    if match:
        return float(match.group(1))
    return None


def _estimate_area(cell_count: int) -> str:
    """依 cell_count 粗略估算電路面積等級。"""
    if cell_count == 0:
        return "unknown"
    if cell_count < 50:
        return "small"
    if cell_count < 500:
        return "medium"
    return "large"


# ---------- 測試入口 ----------

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        with open(sys.argv[1], "r", encoding="utf-8") as f:
            raw = f.read()
    else:
        # 最小化測試字串
        raw = """
        Number of wires:                 32
        Number of cells:                 47
          $_DFF_P_                         4
          $_NOT_                           8
          $_AND_                          35
        """
    result = parse_synthesis_report(raw)
    print(json.dumps(result, ensure_ascii=False, indent=2))
