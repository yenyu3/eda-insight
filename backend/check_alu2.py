import sqlite3, json, os

conn = sqlite3.connect('eda_platform.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

for run_id in ['63e7f1f2-2952-4c45-b813-695c869bfb8f', '8eaff8ad-3fc2-43fe-a0b2-1ed2ec123526']:
    short = run_id[:8]
    cur.execute("SELECT status, synthesis_result, sim_result FROM runs WHERE run_id=?", (run_id,))
    row = cur.fetchone()
    if not row: continue
    sim = json.loads(row['sim_result']) if row['sim_result'] else {}
    print(f"--- {short} status={row['status']} ---")
    print(f"  signals: {sim.get('signals', [])}")
    synth_path = fr'uploads\runs\{run_id}\synth.json'
    if os.path.exists(synth_path):
        from report_parser import parse_synthesis_json
        r = parse_synthesis_json(synth_path)
        print(f"  synth.json parse: cell={r['cell_count']} wire={r['wire_count']} ff={r['flip_flop_count']}")
    else:
        print(f"  synth.json: NOT FOUND")
    # Stage logs
    cur.execute("SELECT stage, status FROM stage_logs WHERE run_id=? ORDER BY id", (run_id,))
    for s in cur.fetchall():
        print(f"  [{s['stage']}] {s['status']}")
    print()

conn.close()
