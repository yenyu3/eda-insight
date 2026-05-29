import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "eda_platform.db"

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("SELECT run_id, filename, status, created_at FROM runs WHERE filename LIKE '%adder%' ORDER BY created_at DESC LIMIT 5")
rows = cur.fetchall()
for r in rows:
    print(f"run_id={r['run_id'][:8]}  file={r['filename']}  status={r['status']}  created={r['created_at']}")

print()
if rows:
    run_id = rows[0]['run_id']
    cur.execute("SELECT stage, status, log_output FROM stage_logs WHERE run_id=? ORDER BY id", (run_id,))
    for s in cur.fetchall():
        print(f"  [{s['stage']}] {s['status']}")
        if s['log_output']:
            print(f"    log: {s['log_output'][:200]}")

    cur.execute("SELECT synthesis_result FROM runs WHERE run_id=?", (run_id,))
    row = cur.fetchone()
    print()
    print('synthesis_result:', row['synthesis_result'])

conn.close()
