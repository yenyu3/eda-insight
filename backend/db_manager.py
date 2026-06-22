import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

import config

DB_PATH = config.DB_PATH
TAIPEI_TZ = timezone(timedelta(hours=8))

# 這些欄位在 DB 中以 JSON 字串儲存，取出時要還原
JSON_FIELDS = {
    "parser_result",
    "workflow_plan",
    "sim_result",
    "synthesis_result",
    "dependency_graph",
    "risk_scores",
    "bottleneck_analysis",
}

RUN_ALLOWED_FIELDS = {
    "parser_result",
    "workflow_plan",
    "sim_result",
    "synthesis_result",
    "dependency_graph",
    "ai_summary",
    "risk_scores",
    "bottleneck_analysis",
    "design_content",
    "ppa_cell_count",
    "ppa_critical_path_ns",
    "ppa_slack_ns",
    "status",
}


def taipei_now() -> str:
    """回傳台北時區的 ISO timestamp，供資料庫持久化使用。"""
    return datetime.now(TAIPEI_TZ).replace(microsecond=0).isoformat()


def get_connection() -> sqlite3.Connection:
    """取得 SQLite 連線，啟用 WAL 以改善讀取並發能力。"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    """
    建立所有資料表（若不存在），並補齊舊版缺少的欄位。

    注意：
    - runs：存放 pipeline 執行紀錄
    - stage_logs：存放各 stage 的 log 與狀態
    """
    conn = get_connection()
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'pending',
                verilog_content TEXT,
                design_content TEXT,
                parser_result TEXT,
                workflow_plan TEXT,
                sim_result TEXT,
                synthesis_result TEXT,
                dependency_graph TEXT,
                ai_summary TEXT,
                risk_scores TEXT,
                bottleneck_analysis TEXT,
                ppa_cell_count INTEGER,
                ppa_critical_path_ns REAL,
                ppa_slack_ns REAL
            );

            CREATE TABLE IF NOT EXISTS stage_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                stage TEXT NOT NULL,
                status TEXT,
                log_output TEXT,
                duration_ms INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (run_id) REFERENCES runs(run_id)
            );
        """)

        # 舊資料庫向後相容：補齊可能缺少的欄位
        _ensure_column(conn, "runs", "risk_scores", "TEXT")
        _ensure_column(conn, "runs", "bottleneck_analysis", "TEXT")
        _ensure_column(conn, "runs", "design_content", "TEXT")
        _ensure_column(conn, "runs", "ppa_cell_count", "INTEGER")
        _ensure_column(conn, "runs", "ppa_critical_path_ns", "REAL")
        _ensure_column(conn, "runs", "ppa_slack_ns", "REAL")

    conn.close()


def _serialize_value(value: Any) -> Any:
    """dict / list 轉 JSON 字串，其餘原樣回傳。"""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def _deserialize_json_fields(row_dict: dict) -> dict:
    """將 DB 中以 JSON 字串儲存的欄位還原成 Python 物件。"""
    result = dict(row_dict)
    for field in JSON_FIELDS:
        if field in result and result[field]:
            try:
                result[field] = json.loads(result[field])
            except (json.JSONDecodeError, TypeError):
                pass
    return result


def _insert_run(
    run_id: str,
    filename: str,
    verilog_content: str,
    design_content: str | None = None,
) -> None:
    conn = get_connection()
    with conn:
        conn.execute(
            """
            INSERT INTO runs (
                run_id, filename, verilog_content, design_content, status, created_at
            )
            VALUES (?, ?, ?, ?, 'pending', ?)
            """,
            (run_id, filename, verilog_content, design_content, taipei_now()),
        )
    conn.close()


def create_run(run_id: str, filename: str, verilog_content: str) -> None:
    """建立新的 run 紀錄，初始狀態為 pending。"""
    _insert_run(run_id, filename, verilog_content, None)


def create_run_with_design(
    run_id: str,
    filename: str,
    verilog_content: str,
    design_content: str,
) -> None:
    """建立新的 run，並保存去除 testbench 後的 design source。"""
    _insert_run(run_id, filename, verilog_content, design_content)


def update_run_status(run_id: str, status: str) -> None:
    """更新指定 run 的整體狀態。"""
    conn = get_connection()
    with conn:
        conn.execute("UPDATE runs SET status = ? WHERE run_id = ?", (status, run_id))
    conn.close()


def update_run_field(run_id: str, field: str, value: Any) -> None:
    """
    更新 runs 表中單一欄位。

    注意：
    - 僅允許更新白名單中的欄位
    - dict / list 會自動序列化為 JSON 字串
    """
    if field not in RUN_ALLOWED_FIELDS:
        raise ValueError(f"欄位 '{field}' 不允許直接更新")

    serialized = _serialize_value(value)

    conn = get_connection()
    with conn:
        conn.execute(f"UPDATE runs SET {field} = ? WHERE run_id = ?", (serialized, run_id))
    conn.close()


def get_run(run_id: str) -> dict | None:
    """依 run_id 取得單筆執行紀錄，回傳 dict 或 None。"""
    conn = get_connection()
    row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    conn.close()

    if row is None:
        return None

    return _deserialize_json_fields(dict(row))


def get_all_runs() -> list[dict]:
    """取得所有執行紀錄，依建立時間倒序排列，供 History 頁面使用。"""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT run_id, filename, created_at, status,
               sim_result, parser_result,
               ppa_cell_count, ppa_critical_path_ns, ppa_slack_ns
        FROM runs
        ORDER BY created_at DESC, run_id DESC
        """
    ).fetchall()
    conn.close()

    runs = []
    for row in rows:
        run = dict(row)

        sim_result = _loads_json(run.pop("sim_result", None)) or {}
        parser_result = _loads_json(run.pop("parser_result", None)) or {}
        lint_issues = parser_result.get("lint_issues") or []

        run["cell_count"] = run.get("ppa_cell_count")
        run["warning_count"] = len(lint_issues)
        run["sim_passed"] = _sim_passed(sim_result, run.get("status"))
        runs.append(run)

    return runs


def upsert_stage_log(
    run_id: str,
    stage: str,
    status: str,
    log_output: str,
    duration_ms: int | None = None,
) -> None:
    """寫入或更新某個 stage 的執行狀態與 log。"""
    conn = get_connection()
    with conn:
        existing = conn.execute(
            "SELECT id FROM stage_logs WHERE run_id = ? AND stage = ?",
            (run_id, stage),
        ).fetchone()

        if existing:
            conn.execute(
                """
                UPDATE stage_logs
                SET status = ?, log_output = ?, duration_ms = ?
                WHERE id = ?
                """,
                (status, log_output, duration_ms, existing["id"]),
            )
        else:
            conn.execute(
                """
                INSERT INTO stage_logs (
                    run_id, stage, status, log_output, duration_ms, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (run_id, stage, status, log_output, duration_ms, taipei_now()),
            )
    conn.close()


def delete_run(run_id: str) -> bool:
    """刪除單筆 run 與其 stage logs；若有刪到資料則回傳 True。"""
    conn = get_connection()
    with conn:
        conn.execute("DELETE FROM stage_logs WHERE run_id = ?", (run_id,))
        cursor = conn.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))
    conn.close()
    return cursor.rowcount > 0


def get_stale_pending_run_ids(max_age_hours: int = 2) -> list[str]:
    """取得超過指定時間仍為 pending 的 run_id。"""
    cutoff = (datetime.now(TAIPEI_TZ) - timedelta(hours=max_age_hours)).replace(microsecond=0).isoformat()
    conn = get_connection()
    rows = conn.execute(
        "SELECT run_id FROM runs WHERE status = 'pending' AND created_at < ?",
        (cutoff,),
    ).fetchall()
    conn.close()
    return [r["run_id"] for r in rows]


def delete_runs(run_ids: list[str]) -> int:
    """批次刪除 runs 與其 stage logs，回傳刪除的 run 數量。"""
    if not run_ids:
        return 0

    placeholders = ",".join("?" * len(run_ids))
    conn = get_connection()
    with conn:
        conn.execute(f"DELETE FROM stage_logs WHERE run_id IN ({placeholders})", run_ids)
        cursor = conn.execute(f"DELETE FROM runs WHERE run_id IN ({placeholders})", run_ids)
    conn.close()
    return cursor.rowcount


def get_stage_logs(run_id: str) -> list[dict]:
    """取得指定 run 的所有 stage logs，依建立時間排序。"""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT stage, status, log_output, duration_ms
        FROM stage_logs
        WHERE run_id = ?
        ORDER BY created_at, id
        """,
        (run_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, decl: str) -> None:
    """若欄位不存在就補上，避免舊 DB 無法相容新版程式。"""
    existing = {
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


def _loads_json(value: str | None):
    """安全地將 JSON 字串轉回 Python 物件，失敗時回傳 None。"""
    if not value:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None


def _sim_passed(sim_result: dict, status: str | None) -> bool | None:
    """
    推測 simulation 是否成功。

    回傳：
    - True: 明確成功
    - False: 明確失敗
    - None: 狀態尚不明確
    """
    if not sim_result:
        return None

    if not isinstance(sim_result, dict):
        return None

    if "passed" in sim_result:
        return bool(sim_result.get("passed"))

    if "success" in sim_result:
        return bool(sim_result.get("success"))

    sim_status = str(sim_result.get("status") or "").lower()
    if sim_status == "warning":
        return False

    if sim_result.get("error"):
        return False

    if status == "done":
        return True
    if status == "error":
        return False

    return None
