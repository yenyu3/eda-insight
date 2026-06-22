import json
import time

from flask import Blueprint, Response, jsonify, stream_with_context

import db_manager
from services.ai_service import get_ai_engine

bp = Blueprint("ai", __name__)


@bp.route("/api/stream/<run_id>", methods=["GET"])
def stream(run_id: str):
    """
    Stream the AI report for a run with Server-Sent Events.

    The endpoint waits for the pipeline-generated report when possible. If a
    completed run has no stored report, it falls back to generating insight
    from the parser result.
    """
    run = db_manager.get_run(run_id)
    if not run:
        return jsonify({"error": "run_id not found", "code": "RUN_NOT_FOUND"}), 404

    def generate():
        try:
            latest = None
            for _ in range(120):
                latest = db_manager.get_run(run_id)
                if not latest:
                    yield _sse({"type": "error", "content": "run_id not found"})
                    return

                summary = latest.get("ai_summary")
                if summary:
                    yield _sse({"type": "text", "content": summary})
                    yield _sse({"type": "done"})
                    return

                status = latest.get("status")
                if status == "error":
                    yield _sse({
                        "type": "error",
                        "content": "pipeline failed; AI report unavailable",
                    })
                    return

                if status == "done":
                    break

                yield ": keep-alive\n\n"
                time.sleep(1)

            if not latest or latest.get("status") != "done":
                yield _sse({"type": "error", "content": "pipeline timeout"})
                return

            latest = latest or db_manager.get_run(run_id) or run
            parser_result = latest.get("parser_result") or {}

            if not parser_result:
                yield _sse({
                    "type": "error",
                    "content": "parser_result is empty; cannot generate AI report",
                })
                return

            engine = get_ai_engine()
            for chunk in engine.verilog_insight(parser_result):
                if chunk:
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
