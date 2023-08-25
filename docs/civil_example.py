
from typing import Callable

from datetime import datetime, timedelta
from datetype import DateTime, aware
from zoneinfo import ZoneInfo

from fritter.drivers.memory import MemoryDriver
from fritter.drivers.datetime import DateTimeDriver
from fritter.scheduler import Scheduler

TZ = ZoneInfo("US/Pacific")
memdriver = MemoryDriver()
dtdriver = DateTimeDriver(memdriver, TZ)
scheduler = Scheduler[DateTime[ZoneInfo], Callable[[], None]](dtdriver)

dt = datetime(2023, 5, 5, tzinfo=TZ)

memdriver.advance(dt.timestamp())

def hi() -> None:
    print("hi", scheduler.now().isoformat())

scheduler.callAt(aware(dt, ZoneInfo) + timedelta(days=2), hi)
memdriver.advance(2*(60 * 60 * 24))
