import subprocess


def format_stage_logs_for_ai(logs: list[dict]) -> str:
    """將所有 stage logs 合併為 AI 可讀的純文字。

    格式設計目標：
    - 保留 stage 與 status，方便 AI 判讀流程位置
    - 若有 duration 也一起保留，利於瓶頸分析
    - 若 log_output 為空，仍保留 stage 標記
    """
    lines = []
    for log in logs:
        stage = log.get("stage", "unknown")
        status = log.get("status", "unknown")
        duration_ms = log.get("duration_ms")
        output = (log.get("log_output") or "").strip()

        header = f"[{stage}:{status}]"
        if duration_ms is not None:
            header += f" ({duration_ms} ms)"

        if output:
            lines.append(f"{header}\n{output}")
        else:
            lines.append(header)

    return "\n\n".join(lines)


def format_tool_error(result: subprocess.CompletedProcess) -> str:
    """擷取 EDA 工具 stderr/stdout 作為錯誤摘要，避免 DB 儲存過量內容。"""
    parts = []

    if result.stderr:
        stderr = result.stderr.strip()
        if stderr:
            parts.append(f"stderr:\n{stderr}")

    if result.stdout:
        stdout = result.stdout.strip()
        if stdout:
            parts.append(f"stdout:\n{stdout}")

    if parts:
        return "\n\n".join(parts)

    return f"Tool exited with code {result.returncode}"


def format_ai_summary(
    log_insight: dict,
    risk_scores: dict,
    bottleneck_analysis: dict | None = None,
) -> str:
    """將 log_insight / risk_scores / bottleneck_analysis 組裝成可供前端展示的純文字摘要。

    注意：section 標題（AI LOG INTERPRETATION / WARNINGS / RISK SCORES 等）
    為固定英文字串，供 frontend/AIFormattedText.tsx 解析用，請勿更改。
    """
    summary = (log_insight or {}).get("summary") or "Log analysis completed."
    warnings = (log_insight or {}).get("warnings") or []
    events = (log_insight or {}).get("events") or []

    parts = ["AI LOG INTERPRETATION", summary]

    if warnings:
        warning_block = "\n".join(f"- {w}" for w in warnings[:5])
        parts.append("WARNINGS\n" + warning_block)

    if events:
        event_block = "\n".join(f"- {e}" for e in events[:5])
        parts.append("EVENTS\n" + event_block)

    if risk_scores:
        risk_summary = (risk_scores.get("summary") or "").strip()
        risk_block = (
            f"Timing: {risk_scores.get('timing_risk', 'N/A')}\n"
            f"Area: {risk_scores.get('area_risk', 'N/A')}\n"
            f"Function: {risk_scores.get('function_risk', 'N/A')}"
        )
        if risk_summary:
            risk_block += f"\n{risk_summary}"
        parts.append("RISK SCORES\n" + risk_block)

    if bottleneck_analysis:
        bottlenecks = bottleneck_analysis.get("bottlenecks") or []
        impact = (bottleneck_analysis.get("impact") or "").strip()
        suggestions = (bottleneck_analysis.get("suggestions") or "").strip()

        bottleneck_block = (
            f"Nodes: {', '.join(bottlenecks) if bottlenecks else 'None'}\n"
            f"Impact: {impact or 'N/A'}\n"
            f"Suggestions: {suggestions or 'N/A'}"
        )
        parts.append("BOTTLENECK ANALYSIS\n" + bottleneck_block)

    return "\n\n".join(parts)
