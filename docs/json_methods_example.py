from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from datetype import aware
from fritter.drivers.datetime import DateTimeDriver, guessLocalZone
from fritter.drivers.memory import MemoryDriver
from fritter.persistent.json import (
    JSONObject,
    JSONRegistry,
    LoadProcess,
)

registry = JSONRegistry[dict[str, str]]()


@dataclass
class MyClass:
    value: int

    @classmethod
    def typeCodeForJSON(cls) -> str:
        return ".".join([cls.__module__, cls.__name__])

    def toJSON(self, registry: JSONRegistry[object]) -> dict[str, object]:
        return {"value": self.value}

    @classmethod
    def fromJSON(
        cls, load: LoadProcess[dict[str, str]], json: JSONObject
    ) -> MyClass:
        return cls(json["value"])

    @registry.method
    def later(self) -> None:
        print("my value is", self.value)


memoryDriver = MemoryDriver()
scheduler = registry.new(DateTimeDriver(memoryDriver))
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

handle = scheduler.callAt(dt, MyClass(3).later)
myInstance = MyClass(3)
from json import dumps, loads

dump = dumps(registry.save(scheduler))
print(dump)
mem2 = MemoryDriver()
loaded = registry.load(mem2, loads(dump), {})
mem2.advance(dt.timestamp())
