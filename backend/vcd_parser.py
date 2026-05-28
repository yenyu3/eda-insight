"""
vcd_parser.py — 波形資料處理模組

使用 vcdvcd 套件讀取 VCD 檔案，再用 pandas 整理時序資料，
最後輸出符合 Plotly 格式的 JSON-compatible dict。
"""

import json
from typing import Optional

try:
    import vcdvcd
except ImportError:
    vcdvcd = None  # 允許在未安裝套件時 import 不崩潰，執行時才報錯

try:
    import pandas as pd
except ImportError:
    pd = None


def parse_vcd(vcd_path: str) -> dict:
    """
    解析 VCD 波形檔案，回傳 Plotly-compatible 時序資料。

    回傳格式：
    {
        "signals": ["clk", "reset", "count"],
        "timeline": {
            "clk":   {"times": [0, 5, 10, ...], "values": [0, 1, 0, ...]},
            "reset": {"times": [0, 20],          "values": [1, 0]},
            "count": {"times": [0, 10, ...],     "values": [0, 1, ...]}
        },
        "stats": {
            "sim_duration_ns": 200,
            "clock_period_ns": 10,
            "switching_activity": {"clk": 40, "count": 15}
        }
    }
    """
    if vcdvcd is None:
        raise ImportError("vcdvcd 套件未安裝，請執行 pip install vcdvcd")

    vcd = vcdvcd.VCDVCD(vcd_path)
    signal_names = _get_signal_names(vcd)
    timeline = _build_timeline(vcd, signal_names)
    stats = _compute_stats(timeline)

    return {
        "signals": signal_names,
        "timeline": timeline,
        "stats": stats,
    }


def _get_signal_names(vcd) -> list[str]:
    """從 VCD 物件中取出所有訊號名稱，去除層級前綴（取最後一個欄位）。"""
    names = []
    for ref in vcd.references_to_ids:
        # vcdvcd 以 "scope.signal" 格式表示訊號，取最後一段
        short_name = ref.split(".")[-1]
        names.append(short_name)
    return list(dict.fromkeys(names))  # 去重保序


def _build_timeline(vcd, signal_names: list[str]) -> dict:
    """
    將每個訊號的 (time, value) 事件序列整理成 times 陣列與 values 陣列。
    多位元訊號的 value 轉換為十進位整數。
    """
    timeline = {}
    for ref in vcd.references_to_ids:
        short_name = ref.split(".")[-1]
        if short_name not in signal_names:
            continue
        try:
            signal = vcd[ref]
            times = []
            values = []
            for time, value in signal.tv:
                times.append(int(time))
                values.append(_parse_value(value))
            timeline[short_name] = {"times": times, "values": values}
        except Exception:
            pass
    return timeline


def _parse_value(raw_value) -> int | None:
    """將 VCD value（字串或整數）轉為 int，無法解析時回傳 None。"""
    if isinstance(raw_value, int):
        return raw_value
    if isinstance(raw_value, str):
        v = raw_value.strip().lower()
        if set(v) <= {'0', '1'}:
            return int(v, 2)
        try:
            return int(v, 2)
        except ValueError:
            return None
    return None


def _compute_stats(timeline: dict) -> dict:
    """
    計算模擬統計資訊：
    - sim_duration_ns：最大時間戳記
    - clock_period_ns：clk 訊號的平均半週期 × 2（若存在）
    - switching_activity：每個訊號的翻轉次數
    """
    max_time = 0
    switching_activity = {}
    clock_period_ns = None

    for sig, data in timeline.items():
        times = data["times"]
        values = data["values"]
        if times:
            max_time = max(max_time, times[-1])

        # 翻轉次數
        transitions = sum(
            1 for i in range(1, len(values)) if values[i] != values[i - 1]
        )
        switching_activity[sig] = transitions

        # 估算 clock period（clk 訊號的前兩次翻轉間距 × 2）
        if sig == "clk" and len(times) >= 3:
            rising_edges = [times[i] for i in range(1, len(values)) if values[i] == 1 and values[i - 1] == 0]
            if len(rising_edges) >= 2:
                clock_period_ns = rising_edges[1] - rising_edges[0]

    return {
        "sim_duration_ns": max_time,
        "clock_period_ns": clock_period_ns,
        "switching_activity": switching_activity,
    }


# ---------- 測試入口 ----------

if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "uploads/runs/test/counter.vcd"
    result = parse_vcd(path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
