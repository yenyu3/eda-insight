import os
import time

import db_manager
from eda_tools.iverilog_runner import compile_verilog, run_simulation
from eda_tools.vcd_parser import parse_vcd
from utils.log_utils import format_tool_error
from utils.file_utils import read_verilog_sources


def run_simulation_stage(run_id: str, run_dir: str) -> str | None:
    """
    執行完整模擬 pipeline：
    1. iverilog 編譯
    2. vvp 執行
    3. VCD 解析

    Args:
        run_id: 執行唯一識別碼
        run_dir: 工作目錄（包含所有 .v 及輸出）

    Returns:
        VCD 檔案路徑（成功）或 None（失敗）
    """
    t0 = time.time()
    db_manager.upsert_stage_log(run_id, "simulation", "running", "")

    sim_result: dict = {
        "status": "running",
        "vcd_path": None,
        "passed": None,
        "stats": None,
    }

    # 編譯
    compile_result = compile_verilog(run_dir)
    if compile_result.returncode != 0:
        err = format_tool_error(compile_result)
        duration = int((time.time() - t0) * 1000)

        sim_result.update({
            "status": "error",
            "passed": False,
            "error": err,
        })

        db_manager.upsert_stage_log(run_id, "simulation", "error", err, duration)
        db_manager.update_run_field(run_id, "sim_result", sim_result)
        _save_debug_advice(run_id, "simulation", err, run_dir)
        return None

    # 執行
    sim_proc = run_simulation(run_dir)
    if sim_proc.returncode != 0:
        err = format_tool_error(sim_proc)
        duration = int((time.time() - t0) * 1000)

        sim_result.update({
            "status": "error",
            "passed": False,
            "error": err,
        })

        db_manager.upsert_stage_log(run_id, "simulation", "error", err, duration)
        db_manager.update_run_field(run_id, "sim_result", sim_result)
        _save_debug_advice(run_id, "simulation", err, run_dir)
        return None

    # 解析 VCD
    vcd_files = [
        os.path.join(run_dir, f)
        for f in os.listdir(run_dir)
        if f.endswith(".vcd")
    ]

    if vcd_files:
        # 多個 VCD 暫取第一個
        vcd_path = vcd_files[0]
        try:
            vcd_data = parse_vcd(vcd_path)
            sim_result.update({
                "status": "ok",
                "passed": True,
                "vcd_path": vcd_path,
                "stats": vcd_data,
            })
        except Exception as e:
            sim_result.update({
                "status": "warning",
                "passed": False,
                "vcd_path": vcd_path,
                "error": str(e),
            })
    else:
        sim_result.update({
            "status": "warning",
            "warning": "未找到 VCD 檔案，testbench 可能缺少 $dumpfile 宣告",
        })
        vcd_path = None

    if sim_result.get("status") == "warning" and sim_result.get("passed") is not False:
        sim_result["passed"] = False

    duration = int((time.time() - t0) * 1000)
    db_manager.update_run_field(run_id, "sim_result", sim_result)

    final_status = sim_result.get("status")
    if final_status == "ok":
        log_status = "done"
        msg = sim_proc.stdout[:500] if getattr(sim_proc, "stdout", None) else "Simulation completed."
    elif final_status == "warning":
        log_status = "warning"
        msg = sim_result.get("warning") or sim_result.get("error", "Simulation completed with warning.")
    else:
        log_status = "done"
        msg = sim_result.get("error", "Simulation failed.")

    db_manager.upsert_stage_log(run_id, "simulation", log_status, msg, duration)
    return vcd_path


def _save_debug_advice(run_id: str, stage: str, stderr_text: str, run_dir: str) -> None:
    """模擬 stage 失敗後，呼叫 AI debug_advisor 並將建議存入 DB。"""
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
