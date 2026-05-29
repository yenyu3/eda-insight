"""
db_manager.py — SQLite 資料庫管理模組

負責建立、讀取、更新 SQLite 資料表。
資料庫檔案位於 backend/eda_platform.db。
app 啟動時自動建表（CREATE TABLE IF NOT EXISTS）。
"""

import sqlite3
import json
import os
from datetime import datetime, timedelta, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "eda_platform.db")
TAIPEI_TZ = timezone(timedelta(hours=8))


def taipei_now() -> str:
    """Return an ISO timestamp in Taiwan local time for persisted records."""
    return datetime.now(TAIPEI_TZ).replace(microsecond=0).isoformat()


def get_connection() -> sqlite3.Connection:
    """取得 SQLite 連線，啟用 WAL 模式以支援並發讀取。"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    """建立所有資料表（若不存在）。app 啟動時呼叫一次。"""
    conn = get_connection()
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
                run_id TEXT,
                stage TEXT,
                status TEXT,
                log_output TEXT,
                duration_ms INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (run_id) REFERENCES runs(run_id)
            );
        """)
        _ensure_column(conn, "runs", "risk_scores", "TEXT")
        _ensure_column(conn, "runs", "bottleneck_analysis", "TEXT")
        _ensure_column(conn, "runs", "design_content", "TEXT")
    conn.close()


def create_run(run_id: str, filename: str, verilog_content: str) -> None:
    """在 runs 表中建立新的執行紀錄，初始狀態為 pending。"""
    conn = get_connection()
    with conn:
        conn.execute(
            "INSERT INTO runs (run_id, filename, verilog_content, status, created_at) VALUES (?, ?, ?, 'pending', ?)",
            (run_id, filename, verilog_content, taipei_now()),
        )
    conn.close()


def create_run_with_design(run_id: str, filename: str, verilog_content: str, design_content: str) -> None:
    """Create a run and persist the combined non-testbench design source."""
    conn = get_connection()
    with conn:
        conn.execute(
            "INSERT INTO runs (run_id, filename, verilog_content, design_content, status, created_at) VALUES (?, ?, ?, ?, 'pending', ?)",
            (run_id, filename, verilog_content, design_content, taipei_now()),
        )
    conn.close()


def update_run_status(run_id: str, status: str) -> None:
    """更新 runs 表中指定 run 的整體狀態。"""
    conn = get_connection()
    with conn:
        conn.execute("UPDATE runs SET status = ? WHERE run_id = ?", (status, run_id))
    conn.close()


def update_run_field(run_id: str, field: str, value) -> None:
    """更新 runs 表中單一欄位（用於儲存各 stage 的 JSON 結果）。"""
    allowed = {
        "parser_result", "workflow_plan", "sim_result", "synthesis_result",
        "dependency_graph", "ai_summary", "risk_scores", "bottleneck_analysis", "design_content", "ppa_cell_count",
        "ppa_critical_path_ns", "ppa_slack_ns", "status",
    }
    if field not in allowed:
        raise ValueError(f"欄位 '{field}' 不允許直接更新")
    serialized = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value
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
    result = dict(row)
    for field in ("parser_result", "workflow_plan", "sim_result", "synthesis_result", "dependency_graph", "risk_scores", "bottleneck_analysis"):
        if result.get(field):
            try:
                result[field] = json.loads(result[field])
            except (json.JSONDecodeError, TypeError):
                pass
    return result


def get_all_runs() -> list[dict]:
    """取得所有執行紀錄，依建立時間倒序排列，供 History 頁面使用。"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT run_id, filename, created_at, status, sim_result, parser_result, ppa_cell_count, ppa_critical_path_ns, ppa_slack_ns "
        "FROM runs ORDER BY created_at DESC"
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


def upsert_stage_log(run_id: str, stage: str, status: str, log_output: str, duration_ms: int | None = None) -> None:
    """寫入或更新 stage_logs 表中某個 stage 的執行狀態與 log。"""
    conn = get_connection()
    with conn:
        existing = conn.execute(
            "SELECT id FROM stage_logs WHERE run_id = ? AND stage = ?", (run_id, stage)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE stage_logs SET status = ?, log_output = ?, duration_ms = ? WHERE id = ?",
                (status, log_output, duration_ms, existing["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO stage_logs (run_id, stage, status, log_output, duration_ms, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, stage, status, log_output, duration_ms, taipei_now()),
            )
    conn.close()


def get_stage_logs(run_id: str) -> list[dict]:
    """取得指定 run 的所有 stage logs，依建立時間排序。"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT stage, status, log_output, duration_ms FROM stage_logs WHERE run_id = ? ORDER BY created_at",
        (run_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, decl: str) -> None:
    existing = {
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


def _loads_json(value: str | None):
    if not value:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None


def _sim_passed(sim_result: dict, status: str | None) -> bool | None:
    if not sim_result:
        return None
    if "error" in sim_result:
        return False
    if status in {"done", "error"}:
        return True
    return None
