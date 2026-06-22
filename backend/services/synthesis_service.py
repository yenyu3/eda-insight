import os
import time

import db_manager
from eda_tools.yosys_runner import (
    run_synthesis,
    select_synthesis_top,
    parse_synthesis_json,
    parse_synthesis_report,
)
from utils.log_utils import format_tool_error
from utils.file_utils import read_verilog_sources, is_testbench_filename


def run_synthesis_stage(
    run_id: str,
    verilog_path: str,
    run_dir: str,
    parser_result: dict | None = None,
) -> None:
    """
    執行 Yosys 合成，萃取 PPA 指標後寫入 DB。

    Args:
        run_id: 執行唯一識別碼
        verilog_path: 主 .v 檔案路徑
        run_dir: 工作目錄
        parser_result: 用來選出 top module；可為 None

    說明：
        - design_files 主要用於 top module 推斷
        - 真正的 synthesis 執行與輸出檔位置由 run_synthesis() 控制
    """
    t0 = time.time()
    db_manager.upsert_stage_log(run_id, "synthesis", "running", "")

    synth_json_rel = "synth.json"
    synth_json = os.path.join(run_dir, synth_json_rel)

    design_files = sorted(
        f for f in os.listdir(run_dir)
        if f.endswith(".v") and not is_testbench_filename(f)
    )
    if not design_files:
        design_files = [os.path.basename(verilog_path)]

    top_module = select_synthesis_top(parser_result, design_files)
    result = run_synthesis(run_dir, verilog_path, top_module, synth_json_rel)

    if result.returncode != 0:
        duration = int((time.time() - t0) * 1000)
        err = format_tool_error(result)
        db_manager.upsert_stage_log(run_id, "synthesis", "error", err, duration)
        db_manager.update_run_field(run_id, "synthesis_result", {"error": err})
        _save_debug_advice(run_id, "synthesis", err, run_dir)
        return

    # 優先解析 synth.json，不完整時 fallback 到文字 report
    synth_data = {}
    if os.path.exists(synth_json):
        try:
            synth_data = parse_synthesis_json(synth_json) or {}
        except Exception:
            synth_data = {}

    if not synth_data:
        synth_data = parse_synthesis_report(result.stdout + "\n" + result.stderr) or {}

    db_manager.update_run_field(run_id, "synthesis_result", synth_data)

    if synth_data.get("cell_count") is not None:
        db_manager.update_run_field(run_id, "ppa_cell_count", synth_data["cell_count"])
    if synth_data.get("critical_path_ns") is not None:
        db_manager.update_run_field(run_id, "ppa_critical_path_ns", synth_data["critical_path_ns"])
    if synth_data.get("slack_ns") is not None:
        db_manager.update_run_field(run_id, "ppa_slack_ns", synth_data["slack_ns"])

    duration = int((time.time() - t0) * 1000)
    db_manager.upsert_stage_log(run_id, "synthesis", "done", result.stdout[:500], duration)


def _save_debug_advice(run_id: str, stage: str, stderr_text: str, run_dir: str) -> None:
    """合成 stage 失敗後，呼叫 AI debug_advisor 並將建議存入 DB。"""
    db_manager.upsert_stage_log(
        run_id,
        "ai_report",
        "running",
        f"Generating debug advice for {stage} failure.",
    )
    try:
        from services.ai_service import get_ai_engine

        verilog_content = read_verilog_sources(run_dir)
        engine = get_ai_engine()
        advice = "".join(
            engine.debug_advisor(stderr_text[:2000], verilog_content[:4000])
        ).strip()

        summary = (
            f"[{stage} debug advisor]\n{advice}"
            if advice
            else f"[{stage} debug advisor]\nNo advice generated."
        )

        db_manager.update_run_field(run_id, "ai_summary", summary)
        db_manager.upsert_stage_log(run_id, "ai_report", "done", summary[:1000])
    except Exception as e:
        msg = f"{type(e).__name__}: {e}"
        db_manager.update_run_field(run_id, "ai_summary", f"[{stage} debug advisor failed]\n{msg}")
        db_manager.upsert_stage_log(run_id, "ai_report", "error", msg)
