"""utils/log_utils.py — Stage log 格式化與 AI 摘要組裝工具。"""

import subprocess


def format_stage_logs_for_ai(logs: list[dict]) -> str:
    """將所有 stage logs 合併為 AI 可讀的純文字。"""
    lines = []
    for log in logs:
        stage = log.get("stage", "unknown")
        status = log.get("status", "unknown")
        output = (log.get("log_output") or "").strip()
        if output:
            lines.append(f"[{stage}:{status}]\n{output}")
        else:
            lines.append(f"[{stage}:{status}]")
    return "\n\n".join(lines)


def format_tool_error(result: subprocess.CompletedProcess) -> str:
    """擷取 EDA 工具 stderr/stdout 作為錯誤摘要（避免 DB 爆量）。"""
    parts = []
    if result.stderr:
        parts.append(result.stderr.strip())
    if result.stdout:
        parts.append(result.stdout.strip())
    return "\n\n".join(parts).strip() or f"Tool exited with code {result.returncode}"


def format_ai_summary(
    log_insight: dict,
    risk_scores: dict,
    bottleneck_analysis: dict | None = None,
) -> str:
    """將 log_insight / risk_scores / bottleneck_analysis 組裝成可供前端展示的純文字摘要。"""
    summary = (log_insight or {}).get("summary") or "Log analysis completed."
    warnings = (log_insight or {}).get("warnings") or []
    events = (log_insight or {}).get("events") or []
    parts = ["AI LOG INTERPRETATION", summary]

    if warnings:
        parts.append("WARNINGS\n" + "\n".join(f"- {w}" for w in warnings[:5]))
    if events:
        parts.append("EVENTS\n" + "\n".join(f"- {e}" for e in events[:5]))
    if risk_scores:
        parts.append(
            "RISK SCORES\n"
            f"Timing: {risk_scores.get('timing_risk', 'N/A')}\n"
            f"Area: {risk_scores.get('area_risk', 'N/A')}\n"
            f"Function: {risk_scores.get('function_risk', 'N/A')}\n"
            f"{risk_scores.get('summary', '')}".strip()
        )
    if bottleneck_analysis:
        bottlenecks = bottleneck_analysis.get("bottlenecks") or []
        impact = bottleneck_analysis.get("impact") or ""
        suggestions = bottleneck_analysis.get("suggestions") or ""
        parts.append(
            "BOTTLENECK ANALYSIS\n"
            f"Nodes: {', '.join(bottlenecks) if bottlenecks else 'None'}\n"
            f"Impact: {impact}\n"
            f"Suggestions: {suggestions}".strip()
        )
    return "\n\n".join(parts)
