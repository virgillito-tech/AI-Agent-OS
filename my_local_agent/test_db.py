import sqlite3
import pickle

conn = sqlite3.connect('sandbox/os_tasks.sqlite')
cursor = conn.cursor()
cursor.execute("SELECT id, job_state FROM apscheduler_jobs")
for row in cursor.fetchall():
    job_id = row[0]
    state = pickle.loads(row[1])
    args = state.get('args', [])
    print(f"JOB: {job_id}")
    print(f"ARGS: {args}")
