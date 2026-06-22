"""
services/lint_service.py — Lint 結果記錄 Service

Lint 由 verilog_parser 在靜態分析時一併執行；
此 service 負責將結果寫入 stage_logs。
"""

import db_manager


def run_lint_stage(run_id: str, parser_result: dict) -> None:
    """
    記錄 lint stage 結果（lint 由 parser_service 執行，此處僅更新 stage log）。

    Args:
        run_id: 執行唯一識別碼
        parser_result: parser_service.run_parse_stage() 回傳的 dict
    """
    issues = parser_result.get("lint_issues", [])
    msg = f"Lint 完成，發現 {len(issues)} 個問題" if issues else "Lint 通過，無問題"
    db_manager.upsert_stage_log(run_id, "lint", "done", msg, 0)
