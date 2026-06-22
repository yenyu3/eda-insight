"""
routes/ai.py — AI 串流分析路由

Blueprint: ai
  GET /api/stream/<run_id>   Server-Sent Events 串流 AI 分析文字
"""

import json
import time

from flask import Blueprint, jsonify, Response, stream_with_context

import db_manager
from services.ai_service import get_ai_engine

bp = Blueprint("ai", __name__)


@bp.route("/api/stream/<run_id>", methods=["GET"])
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
            for _ in range(120):
                latest = db_manager.get_run(run_id)
                if not latest:
                    yield _sse({"type": "error", "content": "run_id not found"})
                    return

                summary = latest.get("ai_summary")
                if summary:
                    yield from _stream_text(summary)
                    yield _sse({"type": "done"})
                    return

                if latest.get("status") in {"done", "error"}:
                    break

                yield ": keep-alive\n\n"
                time.sleep(1)

            latest = db_manager.get_run(run_id) or run
            parser_result = latest.get("parser_result") or {}
            engine = get_ai_engine()
            for chunk in engine.verilog_insight(parser_result):
                yield _sse({"type": "text", "content": chunk})
            yield _sse({"type": "done"})
        except Exception as e:
            yield _sse({"type": "error", "content": str(e)})

    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _stream_text(text: str, chunk_size: int = 80):
    for i in range(0, len(text), chunk_size):
        yield _sse({"type": "text", "content": text[i:i + chunk_size]})
        time.sleep(0.02)
