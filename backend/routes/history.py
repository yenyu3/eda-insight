from flask import Blueprint, jsonify

import db_manager

bp = Blueprint("history", __name__)


@bp.route("/api/history", methods=["GET"])
def get_history():
    """
    回傳所有執行紀錄，依建立時間倒序排列。

    回傳格式：
    {
        "runs": [...],
        "count": int
    }
    """
    try:
        runs = db_manager.get_all_runs() or []
        return jsonify({
            "runs": runs,
            "count": len(runs),
        })
    except Exception as e:
        return jsonify({
            "error": "無法取得歷史紀錄",
            "code": "HISTORY_FETCH_FAILED",
            "detail": str(e),
        }), 500
