import db_manager


def run_lint_stage(run_id: str, parser_result: dict) -> None:
    """
    記錄 lint stage 結果。

    說明：
    - lint_issues 由 parser_result 提供
    - 本 stage 不重新執行 lint 規則
    - 只負責將 lint 結果寫入 stage log，供前端與 AI 報告使用
    """
    issues = parser_result.get("lint_issues", [])
    if issues:
        msg = f"Lint 完成，發現 {len(issues)} 個問題"
    else:
        msg = "Lint 通過，無問題"

    db_manager.upsert_stage_log(run_id, "lint", "done", msg, 0)
