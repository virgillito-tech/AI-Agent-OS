import sys
import logging
logging.basicConfig()
logging.getLogger('apscheduler').setLevel(logging.DEBUG)

from core.scheduler import scheduler
import time

# Some job stores need the scheduler to be started
scheduler.start()
time.sleep(1) # wait for start

jobs = scheduler.get_jobs()
print(f"FOUND {len(jobs)} JOBS")
for job in jobs:
    print("JOB ID:", job.id)
    print("ARGS:", job.args)
    testo = str(job.args[0]) if job.args and len(job.args) > 0 else ""
    print("TESTO:", testo)
    print("AI in testo?", "ai" in testo.lower())
    print("-" * 20)
scheduler.shutdown(wait=False)
