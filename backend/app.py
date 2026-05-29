"""
app.py — Flask API Server

所有端點前綴為 /api，回傳格式一律為 JSON。
啟用 flask-cors 允許 Vite dev server（localhost:5173）跨來源請求。
app 啟動時自動初始化 SQLite 資料庫。
"""

import os
import uuid
import json
import threading
import shutil
from pathlib import Path

# load_dotenv 必須在 custom module import 之前，確保 USE_MOCK_AI 等環境變數已就緒
from dotenv import load_dotenv
load_dotenv(override=True)

from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
import db_manager
from verilog_parser import parse_verilog
from workflow_engine import run_pipeline
from ai_engine import AIEngine

app = Flask(__name__)
CORS(app, origins=["http://localhost:5173"])

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads", "runs")
os.makedirs(UPLOAD_DIR, exist_ok=True)

db_manager.init_db()

# 延遲初始化 AIEngine（避免啟動時因 API key 缺失崩潰）
_ai_engine: AIEngine | None = None

def get_ai_engine() -> AIEngine:
    global _ai_engine
    if _ai_engine is None:
        _ai_engine = AIEngine()
    return _ai_engine


@app.route("/", methods=["GET"])
def health_check():
    """Simple backend landing endpoint for browser/manual checks."""
    return jsonify({
        "service": "EDA Insight Backend",
        "status": "ok",
        "api_base": "/api",
        "endpoints": [
            "/api/history",
            "/api/upload",
            "/api/run",
            "/api/status/<run_id>",
            "/api/result/<run_id>",
            "/api/stream/<run_id>",
            "/api/compare",
        ],
    })


# ------------------------------------------------------------------
# POST /api/upload
# ------------------------------------------------------------------

@app.route("/api/upload", methods=["POST"])
def upload():
    """
    接收一或多個 .v 檔案（multipart/form-data），執行靜態解析，回傳 module 結構。
    支援同時上傳主電路 + testbench（欄位名稱都叫 "file"）。
    以第一個非 testbench 的檔案作為主檔案名稱。

    Response:
        {"run_id": str, "filename": str, "parser_result": dict, "preview": str}
    """
    files = request.files.getlist("file")
    if not files:
        return jsonify({"error": "未找到上傳檔案", "code": "NO_FILE"}), 400

    for f in files:
        if not f.filename.endswith(".v"):
            return jsonify({"error": f"只接受 .v 檔案，收到：{f.filename}", "code": "INVALID_EXT"}), 400

    run_id = str(uuid.uuid4())
    run_dir = os.path.join(UPLOAD_DIR, run_id)
    os.makedirs(run_dir, exist_ok=True)

    # 儲存所有上傳的檔案
    main_file = next((f for f in files if not _is_testbench_filename(f.filename)), files[0])
    main_filename = main_file.filename
    main_content = ""
    for f in files:
        save_path = os.path.join(run_dir, f.filename)
        f.save(save_path)
        if f == main_file:
            with open(save_path, "r", encoding="utf-8", errors="replace") as fp:
                main_content = fp.read()

    # 解析所有 .v 合併內容以取得完整 module 結構
    all_content = ""
    for fname in os.listdir(run_dir):
        if fname.endswith(".v"):
            with open(os.path.join(run_dir, fname), "r", encoding="utf-8", errors="replace") as fp:
                all_content += fp.read() + "\n"

    parser_result = parse_verilog(all_content)
    db_manager.create_run(run_id, main_filename, main_content)
    db_manager.update_run_field(run_id, "parser_result", parser_result)

    return jsonify({
        "run_id": run_id,
        "filename": main_filename,
        "uploaded_files": [f.filename for f in files],
        "parser_result": parser_result,
        "preview": main_content[:300],
    })


# ------------------------------------------------------------------
# POST /api/run
# ------------------------------------------------------------------

@app.route("/api/run", methods=["POST"])
def run():
    """
    觸發固定 EDA pipeline（lint → simulate → synthesize）。
    在背景 Thread 中執行，立即回傳 202 Accepted。

    Request:  {"run_id": str, "goals": [str]}
    Response: {"run_id": str, "status": "started"}
    """
    body = request.get_json(silent=True) or {}
    run_id = body.get("run_id")
    if not run_id:
        return jsonify({"error": "缺少 run_id", "code": "MISSING_RUN_ID"}), 400

    run_record = db_manager.get_run(run_id)
    if not run_record:
        return jsonify({"error": "run_id 不存在", "code": "RUN_NOT_FOUND"}), 404

    run_dir = os.path.join(UPLOAD_DIR, run_id)
    verilog_path = os.path.join(run_dir, run_record["filename"])

    t = threading.Thread(
        target=run_pipeline,
        args=(run_id, verilog_path, run_record["verilog_content"]),
        daemon=True,
    )
    t.start()

    return jsonify({"run_id": run_id, "status": "started"}), 202


# ------------------------------------------------------------------
# GET /api/status/<run_id>
# ------------------------------------------------------------------

@app.route("/api/status/<run_id>", methods=["GET"])
def get_status(run_id: str):
    """
    回傳各 stage 即時狀態，供前端每 2 秒 polling。

    Response:
        {"run_id": str, "overall": str, "stages": [{name, status, duration_ms}]}
    """
    run = db_manager.get_run(run_id)
    if not run:
        return jsonify({"error": "run_id 不存在", "code": "RUN_NOT_FOUND"}), 404

    stage_logs = db_manager.get_stage_logs(run_id)
    stage_map = {s["stage"]: s for s in stage_logs}

    all_stages = ["verilog_parse", "lint", "simulation", "synthesis", "dep_analysis", "ai_report"]
    stages = []
    for name in all_stages:
        entry = stage_map.get(name, {})
        stages.append({
            "name": name,
            "status": entry.get("status", "pending"),
            "duration_ms": entry.get("duration_ms"),
        })

    return jsonify({
        "run_id": run_id,
        "overall": run["status"],
        "stages": stages,
    })


# ------------------------------------------------------------------
# GET /api/stream/<run_id>  — Server-Sent Events
# ------------------------------------------------------------------

@app.route("/api/stream/<run_id>", methods=["GET"])
def stream(run_id: str):
    """
    串流推送 AI 分析文字（Server-Sent Events）。
    前端使用 EventSource API 接收，呈現打字機效果。
    """
    run = db_manager.get_run(run_id)
    if not run:
        return jsonify({"error": "run_id 不存在", "code": "RUN_NOT_FOUND"}), 404

    def generate():
        try:
            engine = get_ai_engine()
            parser_result = run.get("parser_result") or {}
            for chunk in engine.verilog_insight(parser_result):
                data = json.dumps({"type": "text", "content": chunk}, ensure_ascii=False)
                yield f"data: {data}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ------------------------------------------------------------------
# GET /api/result/<run_id>
# ------------------------------------------------------------------

@app.route("/api/result/<run_id>", methods=["GET"])
def get_result(run_id: str):
    """
    回傳完整執行結果：波形、PPA 指標、dependency graph、AI 摘要等。
    """
    run = db_manager.get_run(run_id)
    if not run:
        return jsonify({"error": "run_id 不存在", "code": "RUN_NOT_FOUND"}), 404

    return jsonify({
        "run_id": run_id,
        "filename": run["filename"],
        "parser_result": run.get("parser_result"),
        "waveform": run.get("sim_result"),
        "synthesis": run.get("synthesis_result"),
        "dependency_graph": run.get("dependency_graph"),
        "ai_summary": run.get("ai_summary"),
        "risk_scores": None,  # Phase 2 填入 ai_engine.risk_analyzer() 結果
        "lint_issues": (run.get("parser_result") or {}).get("lint_issues", []),
    })


# ------------------------------------------------------------------
# GET /api/history
# ------------------------------------------------------------------

@app.route("/api/history", methods=["GET"])
def get_history():
    """回傳所有執行紀錄，依建立時間倒序排列。"""
    runs = db_manager.get_all_runs()
    return jsonify({"runs": runs})


# ------------------------------------------------------------------
# POST /api/compare
# ------------------------------------------------------------------

@app.route("/api/compare", methods=["POST"])
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

    def extract_ppa(run: dict) -> dict:
        synth = run.get("synthesis_result") or {}
        return {
            "filename": run["filename"],
            "cell_count": synth.get("cell_count"),
            "critical_path_ns": synth.get("critical_path_ns"),
            "slack_ns": synth.get("slack_ns"),
        }

    ver_a = extract_ppa(run_a)
    ver_b = extract_ppa(run_b)
    diff = _compute_diff(ver_a, ver_b)

    return jsonify({
        "version_a": ver_a,
        "version_b": ver_b,
        "diff": diff,
        "ai_tradeoff": None,  # Phase 2 填入 AI 分析
    })


def _compute_diff(a: dict, b: dict) -> dict:
    """計算兩個版本 PPA 指標的差異百分比與改善方向。"""
    diff = {}
    for key in ("cell_count", "critical_path_ns", "slack_ns"):
        va, vb = a.get(key), b.get(key)
        if va is None or vb is None:
            diff[key] = {"delta": None, "pct": None, "better": None}
            continue
        delta = vb - va
        pct = round((delta / va) * 100, 1) if va != 0 else None
        # cell_count 和 critical_path_ns 越小越好；slack_ns 越大越好
        better = (delta < 0) if key != "slack_ns" else (delta > 0)
        diff[key] = {"delta": round(delta, 3), "pct": pct, "better": better}
    return diff


def _is_testbench_filename(filename: str) -> bool:
    name = filename.lower()
    return (
        name.endswith("_tb.v")
        or name.startswith("tb_")
        or "testbench" in name
        or name.endswith("_test.v")
    )


# ------------------------------------------------------------------
# 啟動
# ------------------------------------------------------------------

if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    port = int(os.environ.get("FLASK_PORT", "5000"))
    app.run(debug=debug, host="0.0.0.0", port=port)
