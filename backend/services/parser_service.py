"""
services/parser_service.py — Verilog 靜態解析 Service

負責 verilog_parse stage 的完整生命週期：
解析 → 更新 DB → 回傳結果。
同時提供 flowchart 萃取功能。
"""

import os
import time

import db_manager
from eda_tools.verilog_parser import parse_verilog
from eda_tools.flowchart_extractor import extract_flowchart


def run_parse_stage(
    run_id: str,
    verilog_content: str,
    run_dir: str | None = None,
) -> dict:
    """
    執行 verilog_parse stage：合併目錄內所有 .v 後靜態分析，並寫入 DB。

    Args:
        run_id: 執行唯一識別碼
        verilog_content: 主 .v 內容（run_dir 為 None 時使用）
        run_dir: 若提供，合併目錄下所有 .v 檔案後再解析

    Returns:
        parse_verilog() 回傳的 dict
    """
    t0 = time.time()
    db_manager.upsert_stage_log(run_id, "verilog_parse", "running", "")

    combined = verilog_content
    if run_dir and os.path.isdir(run_dir):
        parts = []
        for fname in sorted(os.listdir(run_dir)):
            if fname.endswith(".v"):
                with open(os.path.join(run_dir, fname), "r", encoding="utf-8", errors="replace") as f:
                    parts.append(f.read())
        if parts:
            combined = "\n".join(parts)

    result = parse_verilog(combined)
    duration = int((time.time() - t0) * 1000)

    db_manager.update_run_field(run_id, "parser_result", result)
    db_manager.upsert_stage_log(
        run_id, "verilog_parse", "done",
        f"解析完成，找到 {len(result['modules'])} 個 module",
        duration,
    )
    return result


def get_flowchart(verilog_content: str) -> dict:
    """
    從 Verilog 原始碼萃取 always block flowchart 與 assign 關係圖。

    Args:
        verilog_content: 不含 testbench 的 design Verilog 字串

    Returns:
        extract_flowchart() 回傳的 dict
    """
    return extract_flowchart(verilog_content)
