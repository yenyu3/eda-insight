import os
import time

import db_manager
from eda_tools.verilog_parser import parse_verilog
from eda_tools.flowchart_extractor import extract_flowchart


def run_parse_stage(
    run_id: str,
    verilog_content: str,
    run_dir: str | None = None,
) -> dict:
    """
    執行 verilog_parse stage。

    行為說明：
    - 先以 verilog_content 作為預設輸入
    - 若 run_dir 存在，則合併目錄內所有 .v 檔案後再解析
    - 解析結果會寫回 runs.parser_result
    - stage 狀態會寫入 stage_logs
    """
    t0 = time.time()
    db_manager.upsert_stage_log(run_id, "verilog_parse", "running", "")

    combined = verilog_content

    # 有 run_dir 時合併目錄內所有 .v 檔解析
    if run_dir and os.path.isdir(run_dir):
        parts = []
        for fname in sorted(os.listdir(run_dir)):
            if fname.endswith(".v"):
                with open(
                    os.path.join(run_dir, fname),
                    "r",
                    encoding="utf-8",
                    errors="replace",
                ) as f:
                    parts.append(f.read())

        if parts:
            combined = "\n".join(parts)

    result = parse_verilog(combined)
    duration = int((time.time() - t0) * 1000)

    db_manager.update_run_field(run_id, "parser_result", result)

    modules = result.get("modules", [])
    db_manager.upsert_stage_log(
        run_id,
        "verilog_parse",
        "done",
        f"解析完成，找到 {len(modules)} 個 module",
        duration,
    )
    return result


def get_flowchart(verilog_content: str) -> dict:
    """
    從 Verilog 原始碼萃取 always block flowchart 與 assign 關係圖。

    注意：
    - 這是一個獨立 helper，不是 parse stage 的必要流程
    - 呼叫端可依需求決定是否展示 flowchart
    """
    return extract_flowchart(verilog_content)
