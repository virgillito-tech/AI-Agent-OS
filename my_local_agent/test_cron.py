from apscheduler.triggers.cron import CronTrigger
from datetime import datetime

t1 = CronTrigger(day='last sun')
print("last sun:", t1.get_next_fire_time(None, datetime(2026, 5, 1)))

t2 = CronTrigger(hour='9', minute='0', day_of_week='mon')
print("every mon at 9:", t2.get_next_fire_time(None, datetime(2026, 5, 1)))
