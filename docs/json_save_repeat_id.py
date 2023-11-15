from datetime import timedelta
from json import dump

from datetype import DateTime
from fritter.drivers.datetime import DateTimeDriver, guessLocalZone
from fritter.drivers.memory import MemoryDriver
from fritter.repeat import EveryDelta

from json_identity import MyClass, registry

memoryDriver = MemoryDriver()
scheduler = registry.new(DateTimeDriver(memoryDriver))
dt = DateTime.now(guessLocalZone())
memoryDriver.advance(dt.timestamp())
myInstance = MyClass(3)
handle = scheduler.callAt(dt + timedelta(seconds=5), myInstance.later)
registry.repeatedly(
    scheduler, EveryDelta(timedelta(seconds=0.5)), myInstance.repeat
)


with open("saved-id-schedule.json", "w") as f:
    dump(registry.save(scheduler), f)
