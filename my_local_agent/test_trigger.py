import sys
import pickle
import sqlite3

conn = sqlite3.connect('sandbox/os_tasks.sqlite')
cursor = conn.cursor()
cursor.execute("SELECT id, job_state FROM apscheduler_jobs")
for row in cursor.fetchall():
    job_id = row[0]
    if job_id != 'daemon_guardiano':
        state = pickle.loads(row[1])
        print("NEXT RUN TIME:", state.get('next_run_time'))
        print("TRIGGER:", state.get('trigger'))
