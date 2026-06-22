from flask import Blueprint, request, jsonify

import db_manager
from services.ai_service import get_ai_engine

bp = Blueprint("compare", __name__)


@bp.route("/api/compare", methods=["POST"])
def compare():
    """
    比較兩個 run 的 PPA 指標差異。

    Request:
        {"run_id_a": str, "run_id_b": str}

    Response:
        {
            "version_a": {...},
            "version_b": {...},
            "diff": {...},
            "complexity_scores": {...},
            "recommended": "a" | "b" | None,
            "ai_tradeoff": str
        }
    """
    body = request.get_json(silent=True) or {}
    run_id_a = body.get("run_id_a")
    run_id_b = body.get("run_id_b")

    if not run_id_a or not run_id_b:
        return jsonify({"error": "需要提供 run_id_a 和 run_id_b", "code": "MISSING_IDS"}), 400

    if run_id_a == run_id_b:
        return jsonify({"error": "run_id_a 與 run_id_b 不能相同", "code": "DUPLICATE_IDS"}), 400

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
    complexity_scores = _complexity_scores(ver_a, ver_b)

    return jsonify({
        "version_a": ver_a,
        "version_b": ver_b,
        "diff": diff,
        "complexity_scores": complexity_scores,
        "recommended": recommended,
        "ai_tradeoff": _compare_tradeoff(ver_a, ver_b, diff, recommended),
    })


# ─── 輔助函式 ───

def _extract_ppa(run: dict) -> dict:
    """從 run dict 擷取比較所需的摘要欄位。"""
    synth = run.get("synthesis_result") or {}
    parser_result = run.get("parser_result") or {}

    return {
        "run_id": run.get("run_id"),
        "filename": run.get("filename"),
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
        "sim_result": run.get("sim_result"),
    }


def _run_sim_passed(run: dict) -> bool | None:
    """
    回傳 simulation 是否通過：

    - True: 明確通過
    - False: 明確失敗
    - None: 尚無法判斷 / 尚未執行
    """
    sim = run.get("sim_result")

    if not sim:
        return None

    if not isinstance(sim, dict):
        return None

    # 優先使用明確欄位
    if "passed" in sim:
        return bool(sim.get("passed"))

    if "success" in sim:
        return bool(sim.get("success"))

    sim_status = str(sim.get("status") or "").lower()
    if sim_status == "warning":
        return False

    if "error" in sim and sim.get("error"):
        return False

    # 若 schema 沒有明確欄位，盡量用 status 做保守判斷
    status = (run.get("status") or "").lower()
    if status == "error":
        return False
    if status == "done":
        return True

    return None


def _compute_diff(a: dict, b: dict) -> dict:
    diff = {}

    numeric_keys = ("cell_count", "flip_flop_count", "wire_count", "critical_path_ns", "slack_ns")
    for key in numeric_keys:
        va, vb = a.get(key), b.get(key)
        if va is None or vb is None:
            diff[key] = None
            continue

        delta = vb - va
        pct = round((delta / va) * 100, 1) if va not in (0, 0.0) else None

        # 對大多數指標：越小越好；但 slack 越大越好
        better = (delta < 0) if key != "slack_ns" else (delta > 0)

        diff[key] = {
            "delta": round(delta, 3),
            "pct": pct,
            "better": better,
        }

    diff["simulation"] = _simulation_diff(a, b)
    diff["warnings"] = {
        "a": a.get("warning_count"),
        "b": b.get("warning_count"),
        "delta": (
            None if a.get("warning_count") is None or b.get("warning_count") is None
            else b.get("warning_count") - a.get("warning_count")
        ),
        "better": (
            None if a.get("warning_count") is None or b.get("warning_count") is None
            else b.get("warning_count") < a.get("warning_count")
        ),
    }

    return diff


def _simulation_diff(a: dict, b: dict) -> dict | None:
    va, vb = a.get("sim_passed"), b.get("sim_passed")
    if va is None or vb is None:
        return None

    return {
        "delta": 0 if va == vb else 1,
        "pct": None,
        "better": bool(vb) and not bool(va),
    }


def _complexity_scores(a: dict, b: dict) -> dict:
    """用簡單加權方式估計 complexity score，分數越高代表越複雜。"""
    sa = _compute_complexity(a)
    sb = _compute_complexity(b)
    max_score = max(sa, sb)

    if max_score <= 0:
        return {"a": 0, "b": 0}

    return {
        "a": round((sa / max_score) * 10, 1),
        "b": round((sb / max_score) * 10, 1),
    }


def _recommend_version(a: dict, b: dict) -> str | None:
    """
    推薦版本的簡單規則：

    1. simulation 明確通過者優先
    2. 若都通過，再比較 complexity（越小越好）
    3. 若仍 tie，再比較 critical_path（越小越好）
    """
    a_sim = a.get("sim_passed")
    b_sim = b.get("sim_passed")

    if a_sim is not None and b_sim is not None and a_sim != b_sim:
        return "a" if a_sim else "b"

    ca = _compute_complexity(a)
    cb = _compute_complexity(b)
    if ca != cb:
        return "a" if ca < cb else "b"

    ta = a.get("critical_path_ns")
    tb = b.get("critical_path_ns")
    if ta is not None and tb is not None and ta != tb:
        return "a" if ta < tb else "b"

    return None


def _compute_complexity(x: dict) -> float:
    cell = x.get("cell_count") or 0
    ff = x.get("flip_flop_count") or 0
    wire = x.get("wire_count") or 0
    warn = x.get("warning_count") or 0
    return cell * 1.0 + ff * 2.0 + wire * 0.2 + warn * 0.5


def _compare_tradeoff(a: dict, b: dict, diff: dict, recommended: str | None) -> str:
    """先嘗試用 AI engine 產生 tradeoff 說明，失敗時回退到簡單文字。"""
    try:
        return get_ai_engine().compare_tradeoff(a, b, diff, recommended)
    except Exception:
        if recommended == "a":
            return (
                f"{a.get('filename', 'Version A')} is the recommended choice "
                f"based on the available correctness and complexity metrics."
            )
        if recommended == "b":
            return (
                f"{b.get('filename', 'Version B')} is the recommended choice "
                f"based on the available correctness and complexity metrics."
            )
        return (
            "The two runs are close on the available metrics. "
            "Review simulation results, warnings, and waveform behavior before choosing one."
        )
