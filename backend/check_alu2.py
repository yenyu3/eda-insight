import json
import os
import sqlite3
from pathlib import Path

from report_parser import parse_synthesis_json

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "eda_platform.db"

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

for run_id in ['63e7f1f2-2952-4c45-b813-695c869bfb8f', '8eaff8ad-3fc2-43fe-a0b2-1ed2ec123526']:
    short = run_id[:8]
    cur.execute("SELECT status, synthesis_result, sim_result FROM runs WHERE run_id=?", (run_id,))
    row = cur.fetchone()
    if not row:
        continue
    sim = json.loads(row['sim_result']) if row['sim_result'] else {}
    print(f"--- {short} status={row['status']} ---")
    print(f"  signals: {sim.get('signals', [])}")
    synth_path = BASE_DIR / 'uploads' / 'runs' / run_id / 'synth.json'
    if os.path.exists(synth_path):
        r = parse_synthesis_json(str(synth_path))
        print(f"  synth.json parse: cell={r['cell_count']} wire={r['wire_count']} ff={r['flip_flop_count']}")
    else:
        print("  synth.json: NOT FOUND")
    cur.execute("SELECT stage, status FROM stage_logs WHERE run_id=? ORDER BY id", (run_id,))
    for s in cur.fetchall():
        print(f"  [{s['stage']}] {s['status']}")
    print()

conn.close()
