from flask import Blueprint, jsonify

import db_manager
from services.parser_service import get_flowchart

bp = Blueprint("analysis", __name__)


@bp.route("/api/result/<run_id>", methods=["GET"])
def get_result(run_id: str):
    """回傳完整執行結果：波形、PPA 指標、dependency graph、AI 摘要等。"""
    run = db_manager.get_run(run_id)
    if not run:
        return jsonify({"error": "run_id 不存在", "code": "RUN_NOT_FOUND"}), 404

    flowchart = None
    verilog_content = run.get("design_content") or run.get("verilog_content")
    if verilog_content:
        try:
            flowchart = get_flowchart(verilog_content)
        except Exception as e:
            flowchart = {"error": True, "message": str(e)}

    sim_result = run.get("sim_result")
    waveform = sim_result.get("stats") if isinstance(sim_result, dict) else sim_result
    sim_status = _simulation_status(sim_result)

    return jsonify({
        "run_id": run_id,
        "filename": run.get("filename"),
        "parser_result": run.get("parser_result"),
        "workflow_plan": run.get("workflow_plan"),
        "waveform": waveform,
        "sim_status": sim_status,
        "synthesis": run.get("synthesis_result"),
        "dependency_graph": run.get("dependency_graph"),
        "ai_summary": run.get("ai_summary"),
        "risk_scores": run.get("risk_scores"),
        "bottleneck_analysis": run.get("bottleneck_analysis"),
        "lint_issues": (run.get("parser_result") or {}).get("lint_issues", []),
        "flowchart": flowchart,
    })


def _simulation_status(sim_result) -> dict | None:
    if not isinstance(sim_result, dict):
        return None
    return {
        "status": sim_result.get("status"),
        "passed": sim_result.get("passed"),
        "warning": sim_result.get("warning"),
        "error": sim_result.get("error"),
    }


@bp.route("/api/logs/<run_id>", methods=["GET"])
def get_logs(run_id: str):
    run = db_manager.get_run(run_id)
    if not run:
        return jsonify({"error": "run_id 不存在", "code": "RUN_NOT_FOUND"}), 404
    return jsonify({"run_id": run_id, "logs": db_manager.get_stage_logs(run_id)})
