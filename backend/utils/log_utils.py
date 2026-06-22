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
    """組裝 AI 決策摘要，避免重複 RiskPanel / Bottleneck 區塊的詳細內容。"""
    summary = (log_insight or {}).get("summary") or "Log analysis completed."
    warnings = (log_insight or {}).get("warnings") or []
    log_limitations = (log_insight or {}).get("limitations") or []
    risk_summary = (risk_scores or {}).get("summary") or ""
    evidence = (risk_scores or {}).get("evidence") or []
    next_actions = (risk_scores or {}).get("next_actions") or []
    risk_limitations = (risk_scores or {}).get("limitations") or []
    confidence = (risk_scores or {}).get("confidence")
    bottleneck_limitations = (bottleneck_analysis or {}).get("limitations") or []

    conclusion_lines = [summary.strip()]
    if risk_summary and risk_summary.strip() and risk_summary.strip() != summary.strip():
        conclusion_lines.append(risk_summary.strip())

    parts = ["結論", "\n".join(conclusion_lines)]

    key_evidence = []
    key_evidence.extend(str(item) for item in evidence[:3] if item)

    if warnings:
        key_evidence.extend(f"工具 warning/error: {w}" for w in warnings[:2])

    if bottleneck_analysis:
        bottlenecks = bottleneck_analysis.get("bottlenecks") or []
        if bottlenecks:
            key_evidence.append(f"Dependency graph 顯示 {', '.join(bottlenecks[:3])} 可能是結構性匯流點。")

    if key_evidence:
        evidence_block = "\n".join(f"- {item}" for item in key_evidence[:5])
        parts.append("關鍵依據\n" + evidence_block)

    if next_actions:
        action_block = "\n".join(f"- {item}" for item in next_actions[:3] if item)
        if action_block:
            parts.append("建議動作\n" + action_block)

    limitations = [str(item) for item in [*log_limitations, *risk_limitations, *bottleneck_limitations] if item]
    if limitations:
        limitation_block = "\n".join(f"- {item}" for item in limitations[:4])
        parts.append("資料限制\n" + limitation_block)

    if confidence:
        parts.append(f"信心程度\n{confidence}")

    return "\n\n".join(parts)
