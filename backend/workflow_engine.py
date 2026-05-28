"""
workflow_engine.py — EDA 工具執行控制器

MVP 版本：固定依序執行 lint → simulate → synthesize pipeline。
每個 stage 完成後更新 SQLite 狀態，失敗時自動觸發 AI debug_advisor。

進階版本（MVP 完成後）：可接收 ai_engine.workflow_planner() 回傳的步驟清單，
並透過環境變數 USE_FIXED_PIPELINE 切換固定 / 動態模式。
"""

import os
import subprocess
import time
import uuid
import re

from db_manager import update_run_field, update_run_status, upsert_stage_log
from verilog_parser import parse_verilog
from vcd_parser import parse_vcd
from report_parser import parse_synthesis_report
from dependency_analyzer import build_dag

# 固定 pipeline 步驟順序
FIXED_PIPELINE = ["lint", "simulate", "synthesize"]
USE_FIXED_PIPELINE = os.environ.get("USE_FIXED_PIPELINE", "true").lower() == "true"


def run_pipeline(run_id: str, verilog_path: str, verilog_content: str, steps: list[str] | None = None) -> None:
    """
    執行完整 EDA pipeline，依序執行各 stage 並更新資料庫狀態。
    設計為在背景 Thread 中執行（由 app.py 的 POST /api/run 觸發）。

    Args:
        run_id: 本次執行的唯一識別碼（UUID）
        verilog_path: 上傳 .v 檔案的絕對路徑
        verilog_content: Verilog 原始碼字串
        steps: 動態 pipeline 步驟清單（None 時使用固定流程）
    """
    run_dir = os.path.dirname(verilog_path)
    pipeline = FIXED_PIPELINE if (USE_FIXED_PIPELINE or steps is None) else steps

    update_run_status(run_id, "running")

    try:
        # Stage 1: Verilog 靜態解析（失敗則整個 pipeline 終止）
        parser_result = _stage_verilog_parse(run_id, verilog_content, run_dir)
    except Exception as e:
        upsert_stage_log(run_id, "verilog_parse", "error", f"{type(e).__name__}: {e}")
        update_run_status(run_id, "error")
        return

    # Stage 2: Lint（不阻斷後續）
    if "lint" in pipeline:
        try:
            _stage_lint(run_id, parser_result)
        except Exception as e:
            upsert_stage_log(run_id, "lint", "error", f"{type(e).__name__}: {e}")

    # Stage 3: Simulate（不阻斷後續）
    if "simulate" in pipeline:
        try:
            _stage_simulate(run_id, verilog_path, run_dir)
        except Exception as e:
            upsert_stage_log(run_id, "simulation", "error", f"{type(e).__name__}: {e}")

    # Stage 4: Dependency analysis（只需 parser_result，與 yosys 無關，先跑）
    try:
        _stage_dependency(run_id, parser_result)
    except Exception as e:
        upsert_stage_log(run_id, "dep_analysis", "error", f"{type(e).__name__}: {e}")

    # Stage 5: Synthesize（yosys，不阻斷其他 stage）
    if "synthesize" in pipeline:
        try:
            _stage_synthesize(run_id, verilog_path, run_dir)
        except Exception as e:
            upsert_stage_log(run_id, "synthesis", "error", f"{type(e).__name__}: {e}")

    # 若所有 stage 沒有 error 則標記 done，否則 error
    stage_logs = {s["stage"]: s["status"] for s in __import__("db_manager").get_stage_logs(run_id)}
    has_error = any(v == "error" for v in stage_logs.values())
    update_run_status(run_id, "error" if has_error else "done")


# ------------------------------------------------------------------
# 各 Stage 實作
# ------------------------------------------------------------------

def _stage_verilog_parse(run_id: str, verilog_content: str, run_dir: str | None = None) -> dict:
    """
    執行 verilog_parser 靜態分析，儲存結果到 DB。
    若提供 run_dir，合併目錄下所有 .v 檔案一起解析（取得完整 module 依賴關係）。
    """
    t0 = time.time()
    upsert_stage_log(run_id, "verilog_parse", "running", "")

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

    update_run_field(run_id, "parser_result", result)
    upsert_stage_log(run_id, "verilog_parse", "done", f"解析完成，找到 {len(result['modules'])} 個 module", duration)
    return result


def _stage_lint(run_id: str, parser_result: dict) -> None:
    """記錄 Lint 結果到 stage_logs（lint 由 verilog_parser 一併執行）。"""
    issues = parser_result.get("lint_issues", [])
    msg = f"Lint 完成，發現 {len(issues)} 個問題" if issues else "Lint 通過，無問題"
    upsert_stage_log(run_id, "lint", "done", msg, 0)


def _stage_simulate(run_id: str, verilog_path: str, run_dir: str) -> str | None:
    """
    執行 Icarus Verilog 模擬：
    1. iverilog 編譯 .v 檔案
    2. vvp 執行並產生 .vcd
    3. 用 vcd_parser 解析波形，儲存到 DB

    Returns:
        VCD 檔案路徑，或失敗時回傳 None
    """
    t0 = time.time()
    upsert_stage_log(run_id, "simulation", "running", "")

    sim_out = os.path.join(run_dir, "sim.out")
    # VCD 路徑由 testbench 的 $dumpfile 決定，先預設找 run_dir 下的任何 .vcd
    vcd_path = None

    # 找出所有 .v 檔案（包含 testbench）
    verilog_files = _find_verilog_files(run_dir)

    # 編譯
    compile_result = subprocess.run(
        ["iverilog", "-o", sim_out, "-g2012"] + verilog_files,
        capture_output=True, text=True, timeout=60,
    )
    if compile_result.returncode != 0:
        duration = int((time.time() - t0) * 1000)
        upsert_stage_log(run_id, "simulation", "error", compile_result.stderr, duration)
        update_run_field(run_id, "sim_result", {"error": compile_result.stderr})
        return None

    # 執行模擬
    sim_result = subprocess.run(
        ["vvp", sim_out],
        capture_output=True, text=True, timeout=60,
        cwd=run_dir,
    )
    duration = int((time.time() - t0) * 1000)

    if sim_result.returncode != 0:
        upsert_stage_log(run_id, "simulation", "error", sim_result.stderr, duration)
        update_run_field(run_id, "sim_result", {"error": sim_result.stderr})
        return None

    # 解析 VCD：掃描 run_dir 下所有 .vcd 檔案（testbench 可能用任意名稱）
    vcd_files = [os.path.join(run_dir, f) for f in os.listdir(run_dir) if f.endswith(".vcd")]
    vcd_data = {}
    if vcd_files:
        vcd_path = vcd_files[0]  # 通常只會有一個
        try:
            vcd_data = parse_vcd(vcd_path)
        except Exception as e:
            vcd_data = {"error": str(e)}
    else:
        vcd_data = {"warning": "未找到 VCD 檔案，testbench 可能缺少 $dumpfile 宣告"}

    update_run_field(run_id, "sim_result", vcd_data)
    upsert_stage_log(run_id, "simulation", "done", sim_result.stdout[:500], duration)
    return vcd_path


def _stage_synthesize(run_id: str, verilog_path: str, run_dir: str) -> None:
    """
    執行 Yosys 合成，取得 PPA 指標。
    使用 synth 指令搭配 stat 取得 cell count 等資訊。
    """
    t0 = time.time()
    upsert_stage_log(run_id, "synthesis", "running", "")

    synth_json = os.path.join(run_dir, "synth.json")
    yosys_script = f"read_verilog {verilog_path}; synth; write_json {synth_json}; stat"

    result = subprocess.run(
        ["yosys", "-p", yosys_script],
        capture_output=True, text=True, timeout=120,
    )
    duration = int((time.time() - t0) * 1000)

    if result.returncode != 0:
        upsert_stage_log(run_id, "synthesis", "error", result.stderr, duration)
        update_run_field(run_id, "synthesis_result", {"error": result.stderr})
        return

    synth_data = parse_synthesis_report(result.stdout)
    update_run_field(run_id, "synthesis_result", synth_data)

    # 同步更新 PPA 快速查詢欄位
    if synth_data.get("cell_count"):
        update_run_field(run_id, "ppa_cell_count", synth_data["cell_count"])
    if synth_data.get("critical_path_ns") is not None:
        update_run_field(run_id, "ppa_critical_path_ns", synth_data["critical_path_ns"])
    if synth_data.get("slack_ns") is not None:
        update_run_field(run_id, "ppa_slack_ns", synth_data["slack_ns"])

    upsert_stage_log(run_id, "synthesis", "done", result.stdout[:500], duration)


def _stage_dependency(run_id: str, parser_result: dict) -> dict:
    """建立 Module dependency DAG 並儲存到 DB。"""
    t0 = time.time()
    upsert_stage_log(run_id, "dep_analysis", "running", "")

    dag = build_dag(parser_result)
    duration = int((time.time() - t0) * 1000)

    update_run_field(run_id, "dependency_graph", dag)
    upsert_stage_log(run_id, "dep_analysis", "done", f"DAG 建立完成，{len(dag['nodes'])} 個節點", duration)
    return dag


# ------------------------------------------------------------------
# 工具函式
# ------------------------------------------------------------------

def _find_verilog_files(run_dir: str) -> list[str]:
    """找出指定目錄下的所有 .v 檔案。"""
    files = []
    for fname in os.listdir(run_dir):
        if fname.endswith(".v"):
            files.append(os.path.join(run_dir, fname))
    return files
