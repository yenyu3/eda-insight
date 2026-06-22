import os
import uuid
import shutil
import threading

from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename

import db_manager
import config
from eda_tools.verilog_parser import parse_verilog
from services.workflow_service import run_pipeline
from utils.file_utils import is_testbench_filename

bp = Blueprint("upload", __name__)


@bp.route("/api/upload", methods=["POST"])
def upload():
    """
    接收一或多個 .v 檔案，執行靜態解析，回傳 module 結構。
    支援同時上傳主電路 + testbench（欄位名稱都叫 "file"）。
    """
    files = request.files.getlist("file")
    if not files:
        return jsonify({"error": "未找到上傳檔案", "code": "NO_FILE"}), 400

    seen_filenames = set()
    for f in files:
        safe_name, error = _safe_upload_filename(f.filename)
        if error:
            return jsonify({"error": error, "code": "INVALID_FILENAME"}), 400
        if safe_name in seen_filenames:
            return jsonify({"error": f"duplicate filename: {safe_name}", "code": "DUPLICATE_FILENAME"}), 400
        seen_filenames.add(safe_name)
        f.filename = safe_name

    run_id = str(uuid.uuid4())
    run_dir = os.path.join(config.UPLOAD_DIR, run_id)
    os.makedirs(run_dir, exist_ok=True)

    main_file = next((f for f in files if not is_testbench_filename(f.filename)), files[0])
    main_filename = main_file.filename
    main_content = ""
    for f in files:
        save_path = os.path.join(run_dir, f.filename)
        f.save(save_path)
        if f == main_file:
            with open(save_path, "r", encoding="utf-8", errors="replace") as fp:
                main_content = fp.read()

    all_content = ""
    design_content = ""
    for fname in os.listdir(run_dir):
        if fname.endswith(".v"):
            with open(os.path.join(run_dir, fname), "r", encoding="utf-8", errors="replace") as fp:
                content = fp.read()
                all_content += content + "\n"
                if not is_testbench_filename(fname):
                    design_content += content + "\n"
    if not design_content:
        design_content = main_content

    parser_result = parse_verilog(all_content)
    db_manager.create_run_with_design(run_id, main_filename, main_content, design_content)
    db_manager.update_run_field(run_id, "parser_result", parser_result)

    return jsonify({
        "run_id": run_id,
        "filename": main_filename,
        "uploaded_files": [f.filename for f in files],
        "parser_result": parser_result,
        "preview": main_content[:300],
    })


def _safe_upload_filename(filename: str | None) -> tuple[str | None, str | None]:
    raw = (filename or "").strip()
    if not raw:
        return None, "missing filename"

    if raw != os.path.basename(raw):
        return None, f"invalid filename path: {raw}"

    safe_name = secure_filename(raw)
    if not safe_name:
        return None, "invalid filename"
    if safe_name != raw:
        return None, f"unsupported filename characters: {raw}"
    if not safe_name.lower().endswith(".v"):
        return None, f"only .v files are supported: {raw}"

    return safe_name, None


@bp.route("/api/run", methods=["POST"])
def run():
    """
    觸發固定 EDA pipeline（lint → simulate → synthesize）。
    在背景 Thread 中執行，立即回傳 202 Accepted。
    """
    body = request.get_json(silent=True) or {}
    run_id = body.get("run_id")
    goals = body.get("goals")
    if not run_id:
        return jsonify({"error": "缺少 run_id", "code": "MISSING_RUN_ID"}), 400

    run_record = db_manager.get_run(run_id)
    if not run_record:
        return jsonify({"error": "run_id 不存在", "code": "RUN_NOT_FOUND"}), 404

    if run_record.get("status") == "running":
        return jsonify({"run_id": run_id, "status": "already_running"}), 202

    run_dir = os.path.join(config.UPLOAD_DIR, run_id)
    verilog_path = os.path.join(run_dir, run_record["filename"])
    if not os.path.exists(verilog_path):
        return jsonify({"error": "uploaded Verilog file not found", "code": "SOURCE_NOT_FOUND"}), 404

    db_manager.update_run_status(run_id, "running")
    t = threading.Thread(
        target=run_pipeline,
        args=(run_id, verilog_path, run_record["verilog_content"], goals),
        name=f"eda-run-{run_id[:8]}",
        daemon=True,
    )
    t.start()

    return jsonify({"run_id": run_id, "status": "started"}), 202


@bp.route("/api/run/<run_id>", methods=["DELETE"])
def delete_run(run_id: str):
    """刪除 pending 狀態的 run 及其上傳檔案（前端取消上傳時呼叫）。"""
    run = db_manager.get_run(run_id)
    if not run:
        return jsonify({"error": "run_id 不存在", "code": "RUN_NOT_FOUND"}), 404

    if run.get("status") != "pending":
        return jsonify({"error": "只能刪除 pending 狀態的 run", "code": "INVALID_STATUS"}), 409

    run_dir = os.path.join(config.UPLOAD_DIR, run_id)
    if os.path.exists(run_dir):
        shutil.rmtree(run_dir, ignore_errors=True)

    db_manager.delete_run(run_id)
    return jsonify({"run_id": run_id, "deleted": True})


@bp.route("/api/status/<run_id>", methods=["GET"])
def get_status(run_id: str):
    """回傳各 stage 即時狀態，供前端每 2 秒 polling。"""
    run = db_manager.get_run(run_id)
    if not run:
        return jsonify({"error": "run_id 不存在", "code": "RUN_NOT_FOUND"}), 404

    stage_logs = db_manager.get_stage_logs(run_id)
    stage_map = {s["stage"]: s for s in stage_logs}

    stages = []
    for name in _status_stages(run):
        entry = stage_map.get(name, {})
        stages.append({
            "name": name,
            "status": entry.get("status", "pending"),
            "duration_ms": entry.get("duration_ms"),
        })

    return jsonify({
        "run_id": run_id,
        "overall": run.get("status") or "pending",
        "stages": stages,
    })


def _status_stages(run: dict) -> list[str]:
    workflow_plan = run.get("workflow_plan") or {}
    planned_steps = workflow_plan.get("steps") if isinstance(workflow_plan, dict) else None
    if not planned_steps:
        return ["verilog_parse", "ai_plan", "lint", "simulation", "synthesis", "dep_analysis", "ai_report"]

    stage_names = ["verilog_parse", "ai_plan"]
    step_to_stage = {
        "lint": "lint",
        "simulate": "simulation",
        "synthesize": "synthesis",
        "dependency": "dep_analysis",
    }
    selected_steps = set(planned_steps)
    for step in ("lint", "simulate", "dependency", "synthesize"):
        if step not in selected_steps:
            continue
        stage = step_to_stage.get(step)
        if stage and stage not in stage_names:
            stage_names.append(stage)
    stage_names.append("ai_report")
    return stage_names
