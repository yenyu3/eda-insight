"""
services/workflow_service.py — EDA Pipeline 執行協調器

整合所有 stage service，依序執行完整 pipeline 並維護整體狀態。
設計為在背景 Thread 中執行（由 routes/upload.py 的 POST /api/run 觸發）。
"""

import os
import json
import time

import db_manager
import config
from services.parser_service import run_parse_stage
from services.lint_service import run_lint_stage
from services.simulation_service import run_simulation_stage
from services.synthesis_service import run_synthesis_stage
from utils.graph_utils import build_dag
from utils.log_utils import format_stage_logs_for_ai, format_ai_summary


def run_pipeline(
    run_id: str,
    verilog_path: str,
    verilog_content: str,
    steps: list[str] | None = None,
) -> None:
    """
    執行完整 EDA pipeline，依序更新 DB 狀態。

    Args:
        run_id: 執行唯一識別碼
        verilog_path: 上傳 .v 檔案的絕對路徑
        verilog_content: Verilog 原始碼字串
        steps: 動態 pipeline 步驟清單（None 時使用固定流程）
    """
    run_dir = os.path.dirname(verilog_path)
    db_manager.update_run_status(run_id, "running")

    # Stage 1: Verilog 靜態解析（失敗則整個 pipeline 終止）
    try:
        parser_result = run_parse_stage(run_id, verilog_content, run_dir)
    except Exception as e:
        db_manager.upsert_stage_log(run_id, "verilog_parse", "error", f"{type(e).__name__}: {e}")
        db_manager.update_run_status(run_id, "error")
        return

    pipeline = _select_pipeline(run_id, parser_result, steps)

    # Stage 2: Lint
    if "lint" in pipeline:
        try:
            run_lint_stage(run_id, parser_result)
        except Exception as e:
            db_manager.upsert_stage_log(run_id, "lint", "error", f"{type(e).__name__}: {e}")

    # Stage 3: Simulate
    if "simulate" in pipeline:
        try:
            run_simulation_stage(run_id, verilog_path, run_dir)
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            db_manager.upsert_stage_log(run_id, "simulation", "error", err)

    # Stage 4: Dependency analysis
    if "dependency" in pipeline:
        try:
            _stage_dependency(run_id, parser_result)
        except Exception as e:
            db_manager.upsert_stage_log(run_id, "dep_analysis", "error", f"{type(e).__name__}: {e}")

    # Stage 5: Synthesize
    if "synthesize" in pipeline:
        try:
            run_synthesis_stage(run_id, verilog_path, run_dir, parser_result)
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            db_manager.upsert_stage_log(run_id, "synthesis", "error", err)

    # 判斷整體結果並觸發 AI 報告
    stage_logs = {s["stage"]: s["status"] for s in db_manager.get_stage_logs(run_id)}
    has_core_error = any(
        status == "error"
        for stage, status in stage_logs.items()
        if stage != "ai_report"
    )
    if not has_core_error:
        _stage_ai_report(run_id)
    db_manager.update_run_status(run_id, "error" if has_core_error else "done")


# ------------------------------------------------------------------
# 內部 stage 實作
# ------------------------------------------------------------------

def _stage_dependency(run_id: str, parser_result: dict) -> dict:
    t0 = time.time()
    db_manager.upsert_stage_log(run_id, "dep_analysis", "running", "")

    dag = build_dag(parser_result)
    duration = int((time.time() - t0) * 1000)

    db_manager.update_run_field(run_id, "dependency_graph", dag)
    db_manager.upsert_stage_log(
        run_id, "dep_analysis", "done",
        f"DAG 建立完成，{len(dag['nodes'])} 個節點",
        duration,
    )
    return dag


def _stage_ai_report(run_id: str) -> None:
    """所有核心 stage 完成後，執行 log insight + risk scoring + bottleneck detection。"""
    t0 = time.time()
    db_manager.upsert_stage_log(run_id, "ai_report", "running", "Generating log insight and risk scores.")
    try:
        from services.ai_service import get_ai_engine

        run = db_manager.get_run(run_id) or {}
        logs = db_manager.get_stage_logs(run_id)
        log_text = format_stage_logs_for_ai(logs)
        synthesis = run.get("synthesis_result") or {}
        waveform = run.get("sim_result") or {}
        waveform_stats = waveform.get("stats", {}) if isinstance(waveform, dict) else {}
        dependency_graph = run.get("dependency_graph") or {}

        engine = get_ai_engine()
        log_insight = engine.log_insight(log_text)
        risk_scores = engine.risk_analyzer(synthesis, waveform_stats)
        bottleneck_analysis = engine.bottleneck_detector(dependency_graph)
        summary = format_ai_summary(log_insight, risk_scores, bottleneck_analysis)

        db_manager.update_run_field(run_id, "ai_summary", summary)
        db_manager.update_run_field(run_id, "risk_scores", risk_scores)
        db_manager.update_run_field(run_id, "bottleneck_analysis", bottleneck_analysis)
        duration = int((time.time() - t0) * 1000)
        db_manager.upsert_stage_log(run_id, "ai_report", "done", summary[:1000], duration)
    except Exception as e:
        duration = int((time.time() - t0) * 1000)
        msg = f"{type(e).__name__}: {e}"
        db_manager.upsert_stage_log(run_id, "ai_report", "error", msg, duration)


# ------------------------------------------------------------------
# Pipeline 步驟選擇
# ------------------------------------------------------------------

def _select_pipeline(run_id: str, parser_result: dict, goals) -> list[str]:
    """依環境變數決定使用固定 pipeline 或 AI 動態規劃。"""
    t0 = time.time()
    requested_steps = _normalize_steps(goals)

    if config.USE_FIXED_PIPELINE:
        selected = requested_steps or config.FIXED_PIPELINE
        plan = {
            "steps": selected,
            "reason": "fixed pipeline mode with requested goals" if requested_steps else "fixed pipeline mode",
            "source": "fixed",
        }
        db_manager.update_run_field(run_id, "workflow_plan", plan)
        db_manager.upsert_stage_log(run_id, "ai_plan", "done", plan["reason"], 0)
        return plan["steps"]

    db_manager.upsert_stage_log(run_id, "ai_plan", "running", "")
    try:
        from services.ai_service import get_ai_engine

        insight_text = _parser_result_summary(parser_result)
        user_goals = ", ".join(requested_steps) if requested_steps else "simulate, synthesize"
        ai_plan = get_ai_engine().workflow_planner(insight_text, user_goals)
        planned_steps = _normalize_steps(ai_plan.get("steps"))
        if not planned_steps:
            planned_steps = requested_steps or config.FIXED_PIPELINE
        plan = {
            "steps": planned_steps,
            "reason": ai_plan.get("reason") or "AI planner selected pipeline steps.",
            "source": "ai",
        }
        db_manager.update_run_field(run_id, "workflow_plan", plan)
        db_manager.upsert_stage_log(run_id, "ai_plan", "done", plan["reason"], int((time.time() - t0) * 1000))
        return planned_steps
    except Exception as e:
        fallback = requested_steps or config.FIXED_PIPELINE
        plan = {
            "steps": fallback,
            "reason": f"planner fallback: {type(e).__name__}: {e}",
            "source": "fallback",
        }
        db_manager.update_run_field(run_id, "workflow_plan", plan)
        db_manager.upsert_stage_log(run_id, "ai_plan", "error", plan["reason"], int((time.time() - t0) * 1000))
        return fallback


def _normalize_steps(goals) -> list[str]:
    if goals is None:
        return []
    raw = goals if isinstance(goals, list) else [goals]
    aliases = {
        "simulation": "simulate", "sim": "simulate",
        "synthesis": "synthesize", "synth": "synthesize",
        "lint only": "lint",
        "dependency graph": "dependency",
        "dep analysis": "dependency", "dep_analysis": "dependency",
    }
    normalized = []
    for item in raw:
        if not isinstance(item, str):
            continue
        key = item.strip().lower().replace("_", " ")
        step = aliases.get(key, key)
        if step in config.VALID_STEPS and step not in normalized:
            normalized.append(step)
    return [step for step in config.FIXED_PIPELINE if step in set(normalized)]


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
