"""
eda_tools/yosys_runner.py — Yosys 合成工具呼叫封裝與 PPA 報告解析

包含：
- Yosys subprocess 呼叫
- synth.json / stat 文字輸出解析（PPA 指標萃取）
- Top module 自動選擇
"""

import os
import re
import json
import subprocess
from typing import Optional

from eda_tools.iverilog_runner import resolve_tool, tool_env
from utils.file_utils import is_testbench_filename


def run_synthesis(
    run_dir: str,
    verilog_path: str,
    top_module: str | None,
    output_json: str = "synth.json",
) -> subprocess.CompletedProcess:
    """
    執行 Yosys 合成，輸出 synth.json 與 stat 資訊。

    Args:
        run_dir: 工作目錄（包含 .v 檔案）
        verilog_path: 主 .v 檔案路徑（用於 fallback 檔名）
        top_module: Yosys synth 指定的頂層 module 名稱（可 None）
        output_json: Yosys write_json 的輸出檔名（相對 run_dir）

    Returns:
        subprocess.CompletedProcess
    """
    design_files = sorted(
        f for f in os.listdir(run_dir)
        if f.endswith(".v") and not is_testbench_filename(f)
    )
    if not design_files:
        design_files = [os.path.basename(verilog_path)]

    read_cmds = "; ".join(f"read_verilog {f}" for f in design_files)
    synth_cmd = f"synth -top {top_module}" if top_module else "synth"
    yosys_script = f"{read_cmds}; {synth_cmd}; write_json {output_json}; stat"

    yosys_cmd = resolve_tool("yosys")
    return subprocess.run(
        [yosys_cmd, "-p", yosys_script],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=run_dir,
        env=tool_env(yosys_cmd),
    )


def select_synthesis_top(
    parser_result: dict | None,
    design_files: list[str],
) -> str | None:
    """
    依模組依賴關係選出合適的頂層 module 供 Yosys synth -top 使用。
    採用「沒有被任何其他 module 例化」的模組作為根節點。
    """
    if not parser_result:
        return None

    design_stems = {os.path.splitext(f)[0] for f in design_files}
    modules = [
        m for m in parser_result.get("modules", [])
        if not is_testbench_filename(f"{m.get('name', '')}.v")
    ]
    if not modules:
        return None

    module_names = {m["name"] for m in modules}
    instantiated = {
        inst
        for m in modules
        for inst in m.get("instantiations", [])
        if inst in module_names
    }
    roots = [m["name"] for m in modules if m["name"] not in instantiated]

    stem_roots = [name for name in roots if name in design_stems]
    if len(stem_roots) == 1:
        return stem_roots[0]
    if len(roots) == 1:
        return roots[0]

    primary_matches = [m["name"] for m in modules if m["name"] in design_stems]
    if primary_matches:
        return primary_matches[0]
    return modules[0]["name"]


# ------------------------------------------------------------------
# PPA 報告解析
# ------------------------------------------------------------------

def parse_synthesis_json(json_path: str) -> dict:
    """
    從 Yosys write_json 產生的 JSON 檔直接解析 PPA 指標。
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


def parse_synthesis_report(yosys_output: str) -> dict:
    """解析 Yosys stat 文字輸出，萃取 PPA 指標（parse_synthesis_json 的 fallback）。"""
    cell_count = _parse_cell_count(yosys_output)
    wire_count = _parse_wire_count(yosys_output)
    flip_flop_count = _parse_flip_flop_count(yosys_output)
    return {
        "cell_count": cell_count,
        "wire_count": wire_count,
        "flip_flop_count": flip_flop_count,
        "critical_path_ns": _parse_critical_path(yosys_output),
        "slack_ns": _parse_slack(yosys_output),
        "area_estimate": _estimate_area(cell_count),
    }


# ------------------------------------------------------------------
# 內部工具函式
# ------------------------------------------------------------------

def _empty_result() -> dict:
    return {
        "cell_count": 0,
        "wire_count": 0,
        "flip_flop_count": 0,
        "critical_path_ns": None,
        "slack_ns": None,
        "area_estimate": "unknown",
    }


def _estimate_area(cell_count: int) -> str:
    if cell_count == 0:
        return "unknown"
    if cell_count < 50:
        return "small"
    if cell_count < 500:
        return "medium"
    return "large"


def _parse_cell_count(output: str) -> int:
    match = re.search(r'Number of cells:\s+(\d+)', output)
    return int(match.group(1)) if match else 0


def _parse_wire_count(output: str) -> int:
    match = re.search(r'Number of wires:\s+(\d+)', output)
    return int(match.group(1)) if match else 0


def _parse_flip_flop_count(output: str) -> int:
    total = 0
    for m in re.finditer(r'\$_DFF_\w+_\s+(\d+)', output):
        total += int(m.group(1))
    return total


def _parse_critical_path(output: str) -> Optional[float]:
    match = re.search(r'(?:critical path|max delay)[^\d]*([\d.]+)\s*ns', output, re.IGNORECASE)
    return float(match.group(1)) if match else None


def _parse_slack(output: str) -> Optional[float]:
    match = re.search(r'slack[^\d]*([\d.]+)\s*ns', output, re.IGNORECASE)
    return float(match.group(1)) if match else None
