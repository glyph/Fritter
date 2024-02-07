from datetime import datetime
from zoneinfo import ZoneInfo

from datetype import aware
from fritter.drivers.datetime import DateTimeDriver, guessLocalZone
from fritter.drivers.memory import MemoryDriver
from fritter.persistent.json import JSONableScheduler, JSONRegistry

ctxtype = dict[str, str]

registry = JSONRegistry[ctxtype]()


@registry.function
def call1() -> None:
    print("hello world")


memoryDriver = MemoryDriver()
scheduler = JSONableScheduler[ctxtype](DateTimeDriver(memoryDriver))
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
dump = registry.save(scheduler)
print(dump)
mem2 = MemoryDriver()
loaded = registry.load(mem2, dump, {})
mem2.advance(dt.timestamp())
