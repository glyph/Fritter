from datetime import datetime
from zoneinfo import ZoneInfo

from datetype import aware
from fritter.drivers.datetimes import DateTimeDriver, guessLocalZone
from fritter.drivers.memory import MemoryDriver
from fritter.persistent.jsonable import JSONableScheduler, JSONRegistry

ctxtype = dict[str, str]

registry = JSONRegistry[ctxtype]()


@registry.function
def call1() -> None:
    print("hello world")


memoryDriver = MemoryDriver()
scheduler: JSONableScheduler[ctxtype]
scheduler, saver = registry.new(DateTimeDriver(memoryDriver))

dt = aware(
    datetime(
        2023,
        7,
        21,
        1,
        1,
        1,
        tzinfo=guessLocalZone(),
    ),
    ZoneInfo,
)
handle = scheduler.callAt(dt, call1)
dump = saver()
print(dump)
mem2 = MemoryDriver()
loaded = registry.load(mem2, dump, {})
mem2.advance(dt.timestamp())
