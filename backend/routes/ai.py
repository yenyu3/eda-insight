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

    流程：
    1. 檢查 run 是否存在
    2. 若已有 ai_summary，直接串流輸出
    3. 若尚未完成，短暫輪詢等待 pipeline 完成
    4. 若仍無 ai_summary，fallback 到 AI engine 即時生成
    """
    run = db_manager.get_run(run_id)
    if not run:
        return jsonify({"error": "run_id 不存在", "code": "RUN_NOT_FOUND"}), 404

    def generate():
        try:
            # 等待既有 ai_summary 或 pipeline 結束
            latest = None
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

                status = latest.get("status")
                if status == "error":
                    yield _sse({
                        "type": "error",
                        "content": "pipeline failed; AI summary unavailable",
                    })
                    return

                if status == "done":
                    break

                yield ": keep-alive\n\n"
                time.sleep(1)

            # fallback 用 parser_result 即時生成摘要
            if not latest or latest.get("status") != "done":
                yield _sse({"type": "error", "content": "pipeline timeout"})
                return

            latest = latest or db_manager.get_run(run_id) or run
            parser_result = latest.get("parser_result") or {}

            if not parser_result:
                yield _sse({
                    "type": "error",
                    "content": "parser_result is empty; cannot generate AI summary",
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
    """將 payload 包裝成 SSE data event。"""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _stream_text(text: str, chunk_size: int = 80):
    """
    將長文字切塊並串流輸出，模擬打字機效果。

    chunk_size:
        每次輸出的字元數，預設 80。
    """
    for i in range(0, len(text), chunk_size):
        yield _sse({"type": "text", "content": text[i:i + chunk_size]})
        time.sleep(0.02)
