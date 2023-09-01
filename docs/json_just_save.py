from json import dump
from zoneinfo import ZoneInfo

from datetype import DateTime
from datetime import timedelta
from fritter.drivers.datetime import DateTimeDriver
from fritter.drivers.memory import MemoryDriver
from fritter.persistent.json import JSONableScheduler

from json_instance import MyClass, registry

memoryDriver = MemoryDriver()
scheduler = JSONableScheduler(DateTimeDriver(memoryDriver))
dt = DateTime.now(ZoneInfo(key="America/Los_Angeles"))
handle = scheduler.callAt(dt + timedelta(seconds=5), MyClass(3).later)
myInstance = MyClass(3)


with open("saved-schedule.json", "w") as f:
    dump(registry.save(scheduler), f)
