from datetime import datetime, timedelta
from datetype import DateTime, aware
from zoneinfo import ZoneInfo

from fritter.boundaries import TimeDriver, CivilScheduler
from fritter.drivers.memory import MemoryDriver
from fritter.drivers.datetimes import DateTimeDriver
from fritter.scheduler import schedulerFromDriver

# set up memory driver
advancer = MemoryDriver()
base: TimeDriver[float] = advancer
# set up datetime driver
TZ = ZoneInfo("US/Pacific")
dtdriver: TimeDriver[DateTime[ZoneInfo]] = DateTimeDriver(base, TZ)
# set up scheduler
scheduler: CivilScheduler = schedulerFromDriver(dtdriver)
# create datetime
dt = datetime(2023, 5, 5, tzinfo=TZ)
# advance to the timestamp
advancer.advance(dt.timestamp() - advancer.now())
# done advancing


# define some work
def hi() -> None:
    print("hi", scheduler.now().isoformat())


# schedule the work for 2 days in the future
scheduler.callAt(aware(dt, ZoneInfo) + timedelta(days=2), hi)
advancer.advance(2 * (60 * 60 * 24))
