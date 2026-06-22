"""
app.py — Flask API Server（精簡版）

只負責：
1. 載入 .env 環境變數（必須在其他 module import 之前）
2. 建立 Flask app 並設定 CORS
3. 初始化資料庫
4. 清理殘留 pending run
5. 註冊所有 Blueprint（路由定義於 routes/ 套件）
6. 提供 health check 端點
"""

# load_dotenv 必須在所有自訂 module import 之前，確保 USE_MOCK_AI 等環境變數已就緒
from dotenv import load_dotenv
load_dotenv(override=True)

import os
import shutil

from flask import Flask, jsonify
from flask_cors import CORS

import config
import db_manager
from routes import register_blueprints

app = Flask(__name__)
CORS(app, origins=config.CORS_ORIGINS)

os.makedirs(config.UPLOAD_DIR, exist_ok=True)


def _cleanup_stale_pending_runs() -> None:
    """啟動時清除超過 2 小時的 pending runs（使用者關掉 tab 留下的殘留）。"""
    stale_ids = db_manager.get_stale_pending_run_ids(max_age_hours=2)
    for run_id in stale_ids:
        run_dir = os.path.join(config.UPLOAD_DIR, run_id)
        if os.path.exists(run_dir):
            shutil.rmtree(run_dir, ignore_errors=True)
    deleted = db_manager.delete_runs(stale_ids)
    if deleted:
        print(f"[startup] Cleaned up {deleted} stale pending run(s)")


db_manager.init_db()
_cleanup_stale_pending_runs()

register_blueprints(app)


@app.route("/", methods=["GET"])
def health_check():
    """Backend 健康檢查端點，供瀏覽器或手動驗證使用。"""
    return jsonify({
        "service": "EDA Insight Backend",
        "status": "ok",
        "api_base": "/api",
        "endpoints": [
            "/api/history",
            "/api/upload",
            "POST /api/run",
            "DELETE /api/run/<run_id>",
            "/api/status/<run_id>",
            "/api/result/<run_id>",
            "/api/logs/<run_id>",
            "/api/stream/<run_id>",
            "/api/compare",
        ],
    })


if __name__ == "__main__":
    app.run(debug=config.FLASK_DEBUG, host="0.0.0.0", port=config.FLASK_PORT)
