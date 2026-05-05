import asyncio
from core.scheduler import scheduler

jobs = scheduler.get_jobs()
for job in jobs:
    print("JOB ID:", job.id)
    print("ARGS:", job.args)
    if job.args:
        print("ARGS[0] (testo_task):", job.args[0])
    print("-" * 20)
