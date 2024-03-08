from datetime import timedelta
from json import dump

from datetype import DateTime
from fritter.drivers.datetimes import DateTimeDriver, guessLocalZone
from fritter.drivers.memory import MemoryDriver
from fritter.repeat.rules.datetimes import EveryDelta

from json_instance import MyClass, registry

memoryDriver = MemoryDriver()
scheduler, saver = registry.createScheduler(DateTimeDriver(memoryDriver))
dt = DateTime.now(guessLocalZone())
memoryDriver.advance(dt.timestamp())
handle = scheduler.callAt(dt + timedelta(seconds=5), MyClass(3).later)
myInstance = MyClass(3)
registry.repeatedly(
    scheduler, EveryDelta(timedelta(seconds=0.5)), myInstance.repeat
)


with open("saved-schedule.json", "w") as f:
    dump(saver(), f)
