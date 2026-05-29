import sqlite3, json

conn = sqlite3.connect('eda_platform.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("SELECT run_id, filename, status, created_at FROM runs WHERE filename LIKE '%alu%' ORDER BY created_at DESC LIMIT 3")
rows = cur.fetchall()
for r in rows:
    print(f"run_id={r['run_id'][:8]}  file={r['filename']}  status={r['status']}  created={r['created_at']}")

run_id = rows[0]['run_id']
print(f"\n=== Checking {run_id[:8]} ===")

cur.execute("SELECT synthesis_result, sim_result FROM runs WHERE run_id=?", (run_id,))
row = cur.fetchone()
print("synthesis_result:", row['synthesis_result'])

sim = json.loads(row['sim_result']) if row['sim_result'] else {}
print("waveform signals:", sim.get('signals', []))
timeline = sim.get('timeline', {})
for sig in ['result[7:0]', 'carry_out', 'zero', 'a[7:0]', 'alu_out[8:0]']:
    if sig in timeline:
        print(f"  {sig} values: {timeline[sig]['values'][:12]}")

conn.close()
print("\nFull run_id:", run_id)
