"""
workflow_engine.py — EDA 工具執行控制器

MVP 版本：固定依序執行 lint → simulate → synthesize pipeline。
每個 stage 完成後更新 SQLite 狀態，失敗時自動觸發 AI debug_advisor。

進階版本（MVP 完成後）：可接收 ai_engine.workflow_planner() 回傳的步驟清單，
並透過環境變數 USE_FIXED_PIPELINE 切換固定 / 動態模式。
"""

import os
import json
import shutil
import subprocess
import time

from db_manager import update_run_field, update_run_status, upsert_stage_log, get_stage_logs, get_run
from verilog_parser import parse_verilog
from vcd_parser import parse_vcd
from report_parser import parse_synthesis_report, parse_synthesis_json
from dependency_analyzer import build_dag

# 固定 pipeline 步驟順序
FIXED_PIPELINE = ["lint", "simulate", "synthesize"]
VALID_STEPS = {"lint", "simulate", "synthesize"}
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
    update_run_status(run_id, "running")

    try:
        # Stage 1: Verilog 靜態解析（失敗則整個 pipeline 終止）
        parser_result = _stage_verilog_parse(run_id, verilog_content, run_dir)
    except Exception as e:
        upsert_stage_log(run_id, "verilog_parse", "error", f"{type(e).__name__}: {e}")
        update_run_status(run_id, "error")
        return

    pipeline = _stage_ai_plan(run_id, parser_result, steps)

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
            err = f"{type(e).__name__}: {e}"
            upsert_stage_log(run_id, "simulation", "error", err)
            _save_debug_advice(run_id, "simulation", err, run_dir)

    # Stage 4: Dependency analysis（只需 parser_result，與 yosys 無關，先跑）
    try:
        _stage_dependency(run_id, parser_result)
    except Exception as e:
        upsert_stage_log(run_id, "dep_analysis", "error", f"{type(e).__name__}: {e}")

    # Stage 5: Synthesize（yosys，不阻斷其他 stage）
    if "synthesize" in pipeline:
        try:
            _stage_synthesize(run_id, verilog_path, run_dir, parser_result)
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            upsert_stage_log(run_id, "synthesis", "error", err)
            _save_debug_advice(run_id, "synthesis", err, run_dir)

    # 若所有 stage 沒有 error 則標記 done，否則 error
    stage_logs = {s["stage"]: s["status"] for s in get_stage_logs(run_id)}
    has_core_error = any(
        status == "error"
        for stage, status in stage_logs.items()
        if stage != "ai_report"
    )
    if not has_core_error:
        _stage_ai_report(run_id)
    update_run_status(run_id, "error" if has_core_error else "done")


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


def _stage_ai_plan(run_id: str, parser_result: dict, goals) -> list[str]:
    """Select pipeline steps using fixed mode or AI workflow_planner."""
    t0 = time.time()
    requested_steps = _normalize_requested_steps(goals)

    if USE_FIXED_PIPELINE:
        plan = {
            "steps": FIXED_PIPELINE,
            "reason": "fixed pipeline mode",
            "source": "fixed",
        }
        update_run_field(run_id, "workflow_plan", plan)
        upsert_stage_log(run_id, "ai_plan", "done", plan["reason"], 0)
        return plan["steps"]

    upsert_stage_log(run_id, "ai_plan", "running", "")
    try:
        from ai_engine import AIEngine

        insight_text = _parser_result_summary(parser_result)
        user_goals = ", ".join(requested_steps) if requested_steps else "simulate, synthesize"
        ai_plan = AIEngine().workflow_planner(insight_text, user_goals)
        planned_steps = _normalize_requested_steps(ai_plan.get("steps"))
        if not planned_steps:
            planned_steps = requested_steps or FIXED_PIPELINE
        plan = {
            "steps": planned_steps,
            "reason": ai_plan.get("reason") or "AI planner selected pipeline steps.",
            "source": "ai",
        }
        update_run_field(run_id, "workflow_plan", plan)
        duration = int((time.time() - t0) * 1000)
        upsert_stage_log(run_id, "ai_plan", "done", plan["reason"], duration)
        return planned_steps
    except Exception as e:
        fallback = requested_steps or FIXED_PIPELINE
        plan = {
            "steps": fallback,
            "reason": f"planner fallback: {type(e).__name__}: {e}",
            "source": "fallback",
        }
        update_run_field(run_id, "workflow_plan", plan)
        duration = int((time.time() - t0) * 1000)
        upsert_stage_log(run_id, "ai_plan", "error", plan["reason"], duration)
        return fallback


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

    # Use relative paths throughout and run with cwd=run_dir to avoid
    # Windows Unicode/backslash issues in iverilog/vvp command arguments.
    sim_out_rel = "sim.out"
    vcd_path = None

    # 找出所有 .v 檔案（包含 testbench），使用相對路徑
    verilog_filenames = sorted(f for f in os.listdir(run_dir) if f.endswith(".v"))

    # 編譯
    iverilog_cmd = _resolve_tool("iverilog")
    compile_result = subprocess.run(
        [iverilog_cmd, "-o", sim_out_rel, "-g2012"] + verilog_filenames,
        capture_output=True, text=True, timeout=60,
        cwd=run_dir,
        env=_tool_env(iverilog_cmd),
    )
    if compile_result.returncode != 0:
        duration = int((time.time() - t0) * 1000)
        err = _format_tool_error(compile_result)
        upsert_stage_log(run_id, "simulation", "error", err, duration)
        update_run_field(run_id, "sim_result", {"error": err})
        _save_debug_advice(run_id, "simulation", err, run_dir)
        return None

    # 執行模擬
    vvp_cmd = _resolve_tool("vvp")
    sim_result = subprocess.run(
        [vvp_cmd, sim_out_rel],
        capture_output=True, text=True, timeout=60,
        cwd=run_dir,
        env=_tool_env(vvp_cmd),
    )
    duration = int((time.time() - t0) * 1000)

    if sim_result.returncode != 0:
        err = _format_tool_error(sim_result)
        upsert_stage_log(run_id, "simulation", "error", err, duration)
        update_run_field(run_id, "sim_result", {"error": err})
        _save_debug_advice(run_id, "simulation", err, run_dir)
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


def _stage_synthesize(run_id: str, verilog_path: str, run_dir: str, parser_result: dict | None = None) -> None:
    """
    執行 Yosys 合成，取得 PPA 指標。
    使用 synth 指令搭配 stat 取得 cell count 等資訊。
    """
    t0 = time.time()
    upsert_stage_log(run_id, "synthesis", "running", "")

    # Use relative paths and cwd=run_dir to avoid Windows Unicode/backslash issues
    # in the Yosys -p script string.
    synth_json_rel = "synth.json"
    synth_json = os.path.join(run_dir, synth_json_rel)

    # Only synthesize non-testbench design files; testbench 'initial' blocks
    # are not synthesizable and will cause Yosys errors.
    design_files = sorted(
        f for f in os.listdir(run_dir)
        if f.endswith(".v") and not _is_testbench_file(f)
    )
    if not design_files:
        # Fallback: if every file looks like a testbench, use the primary file anyway
        design_files = [os.path.basename(verilog_path)]

    top_module = _select_synthesis_top(parser_result, design_files)
    read_cmds = "; ".join(f"read_verilog {f}" for f in design_files)
    synth_cmd = f"synth -top {top_module}" if top_module else "synth"
    yosys_script = f"{read_cmds}; {synth_cmd}; write_json {synth_json_rel}; stat"

    yosys_cmd = _resolve_tool("yosys")
    result = subprocess.run(
        [yosys_cmd, "-p", yosys_script],
        capture_output=True, text=True, timeout=120,
        cwd=run_dir,
        env=_tool_env(yosys_cmd),
    )
    duration = int((time.time() - t0) * 1000)

    if result.returncode != 0:
        err = _format_tool_error(result)
        upsert_stage_log(run_id, "synthesis", "error", err, duration)
        update_run_field(run_id, "synthesis_result", {"error": err})
        _save_debug_advice(run_id, "synthesis", err, run_dir)
        return

    # 優先從 JSON 解析（不受 Yosys stdout/stderr 分流影響）
    if os.path.exists(synth_json):
        synth_data = parse_synthesis_json(synth_json)
    else:
        synth_data = parse_synthesis_report(result.stdout + "\n" + result.stderr)
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

def _normalize_requested_steps(goals) -> list[str]:
    if goals is None:
        return []
    raw = goals if isinstance(goals, list) else [goals]
    normalized = []
    aliases = {
        "simulation": "simulate",
        "sim": "simulate",
        "synthesis": "synthesize",
        "synth": "synthesize",
        "lint only": "lint",
        "dependency": None,
        "dependency graph": None,
        "dep_analysis": None,
    }
    for item in raw:
        if not isinstance(item, str):
            continue
        key = item.strip().lower().replace("_", " ")
        step = aliases.get(key, key)
        if step in VALID_STEPS and step not in normalized:
            normalized.append(step)
    return normalized


def _parser_result_summary(parser_result: dict) -> str:
    modules = parser_result.get("modules", [])
    compact = {
        "module_count": len(modules),
        "modules": [
            {
                "name": m.get("name"),
                "logic_type": m.get("logic_type"),
                "ports": len(m.get("ports", [])),
                "instantiations": m.get("instantiations", []),
            }
            for m in modules
        ],
        "lint_issue_count": len(parser_result.get("lint_issues", [])),
    }
    return json.dumps(compact, ensure_ascii=False)


def _stage_ai_report(run_id: str) -> None:
    """Generate post-run log insight and risk scores after core EDA stages pass."""
    t0 = time.time()
    upsert_stage_log(run_id, "ai_report", "running", "Generating log insight and risk scores.")
    try:
        from ai_engine import AIEngine

        run = get_run(run_id) or {}
        logs = get_stage_logs(run_id)
        log_text = _format_stage_logs_for_ai(logs)
        synthesis = run.get("synthesis_result") or {}
        waveform = run.get("sim_result") or {}
        waveform_stats = waveform.get("stats", {}) if isinstance(waveform, dict) else {}
        dependency_graph = run.get("dependency_graph") or {}

        engine = AIEngine()
        log_insight = engine.log_insight(log_text)
        risk_scores = engine.risk_analyzer(synthesis, waveform_stats)
        bottleneck_analysis = engine.bottleneck_detector(dependency_graph)
        summary = _format_ai_summary(log_insight, risk_scores, bottleneck_analysis)

        update_run_field(run_id, "ai_summary", summary)
        update_run_field(run_id, "risk_scores", risk_scores)
        update_run_field(run_id, "bottleneck_analysis", bottleneck_analysis)
        duration = int((time.time() - t0) * 1000)
        upsert_stage_log(run_id, "ai_report", "done", summary[:1000], duration)
    except Exception as e:
        duration = int((time.time() - t0) * 1000)
        msg = f"{type(e).__name__}: {e}"
        upsert_stage_log(run_id, "ai_report", "error", msg, duration)


def _find_verilog_files(run_dir: str) -> list[str]:
    """找出指定目錄下的所有 .v 檔案（絕對路徑）。"""
    files = []
    for fname in os.listdir(run_dir):
        if fname.endswith(".v"):
            files.append(os.path.join(run_dir, fname))
    return files


def _format_stage_logs_for_ai(logs: list[dict]) -> str:
    lines = []
    for log in logs:
        stage = log.get("stage", "unknown")
        status = log.get("status", "unknown")
        output = (log.get("log_output") or "").strip()
        if output:
            lines.append(f"[{stage}:{status}]\n{output}")
        else:
            lines.append(f"[{stage}:{status}]")
    return "\n\n".join(lines)


def _format_ai_summary(log_insight: dict, risk_scores: dict, bottleneck_analysis: dict | None = None) -> str:
    summary = (log_insight or {}).get("summary") or "Log analysis completed."
    warnings = (log_insight or {}).get("warnings") or []
    events = (log_insight or {}).get("events") or []
    parts = ["AI LOG INTERPRETATION", summary]
    if warnings:
        parts.append("WARNINGS\n" + "\n".join(f"- {w}" for w in warnings[:5]))
    if events:
        parts.append("EVENTS\n" + "\n".join(f"- {e}" for e in events[:5]))
    if risk_scores:
        parts.append(
            "RISK SCORES\n"
            f"Timing: {risk_scores.get('timing_risk', 'N/A')}\n"
            f"Area: {risk_scores.get('area_risk', 'N/A')}\n"
            f"Function: {risk_scores.get('function_risk', 'N/A')}\n"
            f"{risk_scores.get('summary', '')}".strip()
        )
    if bottleneck_analysis:
        bottlenecks = bottleneck_analysis.get("bottlenecks") or []
        impact = bottleneck_analysis.get("impact") or ""
        suggestions = bottleneck_analysis.get("suggestions") or ""
        parts.append(
            "BOTTLENECK ANALYSIS\n"
            f"Nodes: {', '.join(bottlenecks) if bottlenecks else 'None'}\n"
            f"Impact: {impact}\n"
            f"Suggestions: {suggestions}".strip()
        )
    return "\n\n".join(parts)


def _format_tool_error(result: subprocess.CompletedProcess) -> str:
    """Keep enough EDA output for AI diagnosis without flooding the database."""
    parts = []
    if result.stderr:
        parts.append(result.stderr.strip())
    if result.stdout:
        parts.append(result.stdout.strip())
    return "\n\n".join(parts).strip() or f"Tool exited with code {result.returncode}"


def _read_verilog_sources(run_dir: str) -> str:
    parts = []
    for fname in sorted(os.listdir(run_dir)):
        if not fname.endswith(".v"):
            continue
        path = os.path.join(run_dir, fname)
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            parts.append(f"// File: {fname}\n{f.read()}")
    return "\n\n".join(parts)


def _save_debug_advice(run_id: str, stage: str, stderr_text: str, run_dir: str) -> None:
    """
    Run AI debug_advisor after an EDA stage fails and persist the guidance.
    The AI engine already falls back to mock output when no API key is configured.
    """
    upsert_stage_log(run_id, "ai_report", "running", f"Generating debug advice for {stage} failure.")
    try:
        from ai_engine import AIEngine

        verilog_content = _read_verilog_sources(run_dir)
        engine = AIEngine()
        advice = "".join(engine.debug_advisor(stderr_text[:2000], verilog_content[:4000])).strip()
        summary = f"[{stage} debug advisor]\n{advice}" if advice else f"[{stage} debug advisor]\nNo advice generated."
        update_run_field(run_id, "ai_summary", summary)
        upsert_stage_log(run_id, "ai_report", "done", summary[:1000])
    except Exception as e:
        msg = f"{type(e).__name__}: {e}"
        update_run_field(run_id, "ai_summary", f"[{stage} debug advisor failed]\n{msg}")
        upsert_stage_log(run_id, "ai_report", "error", msg)


def _resolve_tool(tool_name: str) -> str:
    """Resolve EDA tool executables even when Flask starts with a minimal PATH."""
    found = shutil.which(tool_name)
    if found:
        return found

    exe_name = f"{tool_name}.exe" if os.name == "nt" else tool_name
    candidates = []
    if os.name == "nt":
        candidates.extend([
            os.path.join("C:\\", "oss-cad-suite", "bin", exe_name),
            os.path.join("C:\\", "ProgramData", "chocolatey", "bin", exe_name),
        ])

    for path in candidates:
        if os.path.exists(path):
            return path

    raise FileNotFoundError(
        f"{tool_name} not found. Install it or add its bin directory to PATH."
    )


def _tool_env(tool_path: str) -> dict[str, str]:
    env = os.environ.copy()
    tool_dir = os.path.dirname(tool_path)
    suite_root = os.path.dirname(tool_dir)
    suite_lib = os.path.join(suite_root, "lib")
    current_path = env.get("PATH", "")
    path_parts = [p for p in current_path.split(os.pathsep) if p]
    prepend = [
        p for p in (tool_dir, suite_lib)
        if p and os.path.exists(p) and p not in path_parts
    ]
    if prepend:
        env["PATH"] = os.pathsep.join(prepend + ([current_path] if current_path else []))
    return env


def _select_synthesis_top(parser_result: dict | None, design_files: list[str]) -> str | None:
    """Choose a non-testbench root module for Yosys synthesis."""
    if not parser_result:
        return None

    design_stems = {os.path.splitext(f)[0] for f in design_files}
    modules = [
        m for m in parser_result.get("modules", [])
        if not _is_testbench_file(f"{m.get('name', '')}.v")
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


def _is_testbench_file(filename: str) -> bool:
    """
    依檔名慣例判斷是否為 testbench 檔案。
    常見命名：foo_tb.v / tb_foo.v / foo_testbench.v / foo_test.v
    """
    name = filename.lower()
    return (
        name.endswith("_tb.v")
        or name.startswith("tb_")
        or "testbench" in name
        or name.endswith("_test.v")
    )
