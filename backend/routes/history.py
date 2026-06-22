"""
routes/history.py — 執行歷史查詢路由

Blueprint: history
  GET /api/history   列出所有執行紀錄（依建立時間倒序）
"""

from flask import Blueprint, jsonify

import db_manager

bp = Blueprint("history", __name__)


@bp.route("/api/history", methods=["GET"])
def get_history():
    """回傳所有執行紀錄，依建立時間倒序排列。"""
    runs = db_manager.get_all_runs()
    return jsonify({"runs": runs})
