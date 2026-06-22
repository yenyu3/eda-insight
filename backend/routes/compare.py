"""
routes/compare.py — 兩版本 PPA 比較路由

Blueprint: compare
  POST /api/compare   比較兩個 run 的 PPA 指標差異
"""

from flask import Blueprint, request, jsonify

import db_manager
from services.ai_service import get_ai_engine

bp = Blueprint("compare", __name__)


@bp.route("/api/compare", methods=["POST"])
def compare():
    """
    比較兩個 run 的 PPA 指標差異。

    Request:  {"run_id_a": str, "run_id_b": str}
    Response: {"version_a": {...}, "version_b": {...}, "diff": {...}, "ai_tradeoff": str}
    """
    body = request.get_json(silent=True) or {}
    run_id_a = body.get("run_id_a")
    run_id_b = body.get("run_id_b")

    if not run_id_a or not run_id_b:
        return jsonify({"error": "需要提供 run_id_a 和 run_id_b", "code": "MISSING_IDS"}), 400

    run_a = db_manager.get_run(run_id_a)
    run_b = db_manager.get_run(run_id_b)

    if not run_a:
        return jsonify({"error": f"run_id_a '{run_id_a}' 不存在", "code": "RUN_NOT_FOUND"}), 404
    if not run_b:
        return jsonify({"error": f"run_id_b '{run_id_b}' 不存在", "code": "RUN_NOT_FOUND"}), 404

    ver_a = _extract_ppa(run_a)
    ver_b = _extract_ppa(run_b)
    diff = _compute_diff(ver_a, ver_b)
    recommended = _recommend_version(ver_a, ver_b)

    return jsonify({
        "version_a": ver_a,
        "version_b": ver_b,
        "diff": diff,
        "complexity_scores": _complexity_scores(ver_a, ver_b),
        "recommended": recommended,
        "ai_tradeoff": _compare_tradeoff(ver_a, ver_b, diff, recommended),
    })


# ------------------------------------------------------------------
# 輔助函式
# ------------------------------------------------------------------

def _extract_ppa(run: dict) -> dict:
    synth = run.get("synthesis_result") or {}
    parser_result = run.get("parser_result") or {}
    return {
        "run_id": run["run_id"],
        "filename": run["filename"],
        "created_at": run.get("created_at"),
        "status": run.get("status"),
        "sim_passed": _run_sim_passed(run),
        "warning_count": len(parser_result.get("lint_issues") or []),
        "cell_count": synth.get("cell_count"),
        "wire_count": synth.get("wire_count"),
        "flip_flop_count": synth.get("flip_flop_count"),
        "critical_path_ns": synth.get("critical_path_ns"),
        "slack_ns": synth.get("slack_ns"),
        "synthesis": synth or None,
    }


def _run_sim_passed(run: dict) -> bool | None:
    sim = run.get("sim_result") or {}
    if not sim:
        return None
    if isinstance(sim, dict) and "error" in sim:
        return False
    if run.get("status") in {"done", "error"}:
        return True
    return None


def _compute_diff(a: dict, b: dict) -> dict:
    diff = {}
    for key in ("cell_count", "flip_flop_count", "wire_count", "critical_path_ns", "slack_ns"):
        va, vb = a.get(key), b.get(key)
        if va is None or vb is None:
            diff[key] = None
            continue
        delta = vb - va
        pct = round((delta / va) * 100, 1) if va != 0 else None
        better = (delta < 0) if key != "slack_ns" else (delta > 0)
        diff[key] = {"delta": round(delta, 3), "pct": pct, "better": better}
    diff["simulation"] = _simulation_diff(a, b)
    return diff


def _simulation_diff(a: dict, b: dict) -> dict | None:
    va, vb = a.get("sim_passed"), b.get("sim_passed")
    if va is None or vb is None:
        return None
    return {"delta": 0 if va == vb else 1, "pct": None, "better": vb and not va}


def _complexity_scores(a: dict, b: dict) -> dict:
    ca = a.get("cell_count") or 0
    cb = b.get("cell_count") or 0
    max_cells = max(ca, cb)
    if max_cells <= 0:
        return {"a": 0, "b": 0}
    return {
        "a": round((ca / max_cells) * 10, 1),
        "b": round((cb / max_cells) * 10, 1),
    }


def _recommend_version(a: dict, b: dict) -> str | None:
    a_ok = a.get("sim_passed") is not False
    b_ok = b.get("sim_passed") is not False
    if a_ok != b_ok:
        return "a" if a_ok else "b"
    ca = a.get("cell_count")
    cb = b.get("cell_count")
    if ca is not None and cb is not None and ca != cb:
        return "a" if ca < cb else "b"
    return None


def _compare_tradeoff(a: dict, b: dict, diff: dict, recommended: str | None) -> str:
    try:
        return get_ai_engine().compare_tradeoff(a, b, diff, recommended)
    except Exception:
        if recommended == "a":
            return f"{a['filename']} is the recommended choice based on available correctness and cell-count data."
        if recommended == "b":
            return f"{b['filename']} is the recommended choice based on available correctness and cell-count data."
        return "The two runs are close on the available metrics. Review function, warnings, and waveform behavior before choosing one."
