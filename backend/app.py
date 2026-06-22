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


def _ensure_directories() -> None:
    """建立必要資料夾，避免後續 stage 寫檔失敗。"""
    paths = [
        config.UPLOAD_DIR,
        getattr(config, "RUN_DIR", None),
        getattr(config, "LOG_DIR", None),
        getattr(config, "REPORT_DIR", None),
    ]
    for path in paths:
        if path:
            os.makedirs(path, exist_ok=True)


def _cleanup_stale_pending_runs() -> None:
    """啟動時清除超過指定時間的 pending runs（使用者關掉 tab 留下的殘留）。"""
    try:
        stale_ids = db_manager.get_stale_pending_run_ids(max_age_hours=2)
        if not stale_ids:
            return

        for run_id in stale_ids:
            run_dir = os.path.join(config.UPLOAD_DIR, run_id)
            if os.path.exists(run_dir):
                shutil.rmtree(run_dir, ignore_errors=True)

        deleted = db_manager.delete_runs(stale_ids)
        if deleted:
            print(f"[startup] Cleaned up {deleted} stale pending run(s)")
    except Exception as e:
        # cleanup 是 best effort，不應阻止服務啟動
        print(f"[startup] Cleanup stale runs failed: {e}")


def create_app() -> Flask:
    """Application factory。"""
    app = Flask(__name__)
    CORS(app, origins=config.CORS_ORIGINS)

    _ensure_directories()
    db_manager.init_db()
    _cleanup_stale_pending_runs()
    register_blueprints(app)

    @app.route("/", methods=["GET"])
    def health_check():
        """Backend 健康檢查端點，供瀏覽器或手動驗證使用。"""
        return jsonify({
            "service": "VeriFlow Insight Backend",
            "status": "ok",
            "api_base": "/api",
            "endpoints": [
                "GET /",
                "GET /api/history",
                "POST /api/upload",
                "POST /api/run",
                "DELETE /api/run/<run_id>",
                "GET /api/status/<run_id>",
                "GET /api/result/<run_id>",
                "GET /api/logs/<run_id>",
                "GET /api/stream/<run_id>",
                "POST /api/compare",
            ],
        })

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=config.FLASK_DEBUG, host="0.0.0.0", port=config.FLASK_PORT)
