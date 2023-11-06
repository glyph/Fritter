from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from unittest import TestCase
from zoneinfo import ZoneInfo
from json import dumps, loads

from datetype import aware

from ..boundaries import TimeDriver, Cancellable
from ..drivers.datetime import DateTimeDriver
from ..drivers.memory import MemoryDriver
from ..persistent.json import JSONableScheduler, JSONObject, JSONRegistry
from ..repeat import daily
from ..scheduler import Scheduler


@dataclass
class RegInfo:
    calls: list[str]
    identityMap: dict[str, Any] = field(default_factory=dict)


registry = JSONRegistry[RegInfo]()
emptyRegistry = JSONRegistry[RegInfo]()
arbitraryZone = ZoneInfo(key="America/Los_Angeles")

calls = []


@registry.function
def call1() -> None:
    calls.append("hello")


@registry.function
def call2() -> None:
    calls.append("goodbye")


@registry.repeatFunction
def repeatable(steps: int, stopper: Cancellable) -> None:
    calls.append(f"repeatable {steps}")


@dataclass
class InstanceWithMethods:
    value: str
    info: RegInfo
    calls: int = 0

    @classmethod
    def typeCodeForJSON(self) -> str:
        return "instanceWithMethods"

    @classmethod
    def fromJSON(
        cls,
        registry: JSONRegistry[RegInfo],
        scheduler: JSONableScheduler,
        loadContext: RegInfo,
        json: JSONObject,
    ) -> InstanceWithMethods:
        key = json["identity"]
        if key in loadContext.identityMap:
            loadContext.calls.append("InstanceWithMethods.fromJSON (cached)")
            self: InstanceWithMethods = loadContext.identityMap[key]
            return self
        loadContext.calls.append("InstanceWithMethods.fromJSON")
        new = cls(json["value"], loadContext)
        loadContext.identityMap[key] = new
        return new

    def asJSON(self) -> dict[str, object]:
        return {
            "value": self.value,
            "identity": id(self),
        }

    @registry.method
    def method1(self) -> None:
        self.info.calls.append(f"{self.value}/method1")

    @registry.method
    def method2(self) -> None:
        self.info.calls.append(f"{self.value}/method2")

    @registry.repeatMethod
    def repeatMethod(self, steps: int, stopper: Cancellable) -> None:
        self.calls += 1
        self.info.calls.append(
            f"repeatMethod {steps} {self.value=} {self.calls=}"
        )


def jsonScheduler(driver: TimeDriver[float]) -> JSONableScheduler:
    return Scheduler(DateTimeDriver(driver))


class PersistentSchedulerTests(TestCase):
    def tearDown(self) -> None:
        del calls[:]

    def test_scheduleRunSaveRun(self) -> None:
        """
        Test scheduling module-level functions and instance methods.
        """
        memoryDriver = MemoryDriver()
        scheduler = jsonScheduler(memoryDriver)
        dt = aware(
            datetime(
                2023,
                7,
                21,
                1,
                1,
                1,
                tzinfo=arbitraryZone,
            ),
            ZoneInfo,
        )
        dt2 = aware(
            datetime(
                2023,
                7,
                22,
                1,
                1,
                1,
                tzinfo=arbitraryZone,
            ),
            ZoneInfo,
        )
        ri0 = RegInfo([])
        iwm = InstanceWithMethods("test_scheduleRunSaveRun value", ri0)
        scheduler.callAt(dt, call1)
        scheduler.callAt(dt, iwm.method1)
        scheduler.callAt(dt2, call2)
        scheduler.callAt(dt2, iwm.method2)
        memoryDriver.advance(dt.timestamp() + 1)
        self.assertEqual(calls, ["hello"])
        del calls[:]
        saved = registry.save(scheduler)
        memory2 = MemoryDriver()
        ri = RegInfo([])
        registry.load(memory2, saved, ri)
        memory2.advance(dt2.timestamp() + 1)
        self.assertEqual(calls, ["goodbye"])
        self.assertEqual(ri0.calls, ["test_scheduleRunSaveRun value/method1"])
        self.assertEqual(
            ri.calls,
            [
                "InstanceWithMethods.fromJSON",
                "test_scheduleRunSaveRun value/method2",
            ],
        )

    def test_idling(self) -> None:
        memoryDriver = MemoryDriver()
        scheduler = jsonScheduler(memoryDriver)
        dt = aware(
            datetime(
                2023,
                7,
                21,
                1,
                1,
                1,
                tzinfo=arbitraryZone,
            ),
            ZoneInfo,
        )
        handle = scheduler.callAt(dt, call1)
        self.assertEqual(memoryDriver.isScheduled(), True)
        handle.cancel()
        self.assertEqual(memoryDriver.isScheduled(), False)
        memoryDriver.advance(dt.timestamp() + 1)
        self.assertEqual(calls, [])

    def test_emptyScheduler(self) -> None:
        memory = MemoryDriver()
        registry.load(memory, {"scheduledCalls": []}, RegInfo([]))
        self.assertEqual(memory.isScheduled(), False)

    def test_repeatable(self) -> None:
        dt = aware(
            datetime(
                2023,
                7,
                21,
                1,
                1,
                1,
                tzinfo=arbitraryZone,
            ),
            ZoneInfo,
        )
        memoryDriver = MemoryDriver()
        memoryDriver.advance(dt.timestamp())
        scheduler = jsonScheduler(memoryDriver)
        registry.repeatedly(scheduler, daily, repeatable, dt)
        self.assertEqual(calls, ["repeatable 1"])
        del calls[:]

        def days(n: int) -> float:
            return 60 * 60 * 24 * n

        memoryDriver.advance(days(3))
        self.assertEqual(calls, ["repeatable 3"])
        del calls[:]

        newInfo = RegInfo([])
        mem2 = MemoryDriver()
        mem2.advance(dt.timestamp())
        mem2.advance(days(7))
        self.assertEqual(mem2.isScheduled(), False)
        registry.load(mem2, loads(dumps(registry.save(scheduler))), newInfo)
        self.assertEqual(mem2.isScheduled(), True)
        amount = mem2.advance()
        assert amount is not None
        self.assertLess(amount, 0.0001)
        self.assertEqual(calls, ["repeatable 4"])

    def test_repeatableMethod(self) -> None:
        dt = aware(
            datetime(
                2023,
                7,
                21,
                1,
                1,
                1,
                tzinfo=arbitraryZone,
            ),
            ZoneInfo,
        )
        memoryDriver = MemoryDriver()
        memoryDriver.advance(dt.timestamp())
        scheduler = jsonScheduler(memoryDriver)
        info = RegInfo([])
        method = InstanceWithMethods("sample", info).repeatMethod
        shared = InstanceWithMethods("shared", info)
        registry.repeatedly(scheduler, daily, method)
        registry.repeatedly(scheduler, daily, shared.repeatMethod)
        registry.repeatedly(scheduler, daily, shared.repeatMethod)
        self.assertEqual(
            info.calls,
            [
                "repeatMethod 1 self.value='sample' self.calls=1",
                "repeatMethod 1 self.value='shared' self.calls=1",
                "repeatMethod 1 self.value='shared' self.calls=2",
            ],
        )
        del info.calls[:]

        def days(n: int) -> float:
            return 60 * 60 * 24 * n

        memoryDriver.advance(days(3))
        self.assertEqual(
            info.calls,
            [
                "repeatMethod 3 self.value='sample' self.calls=2",
                "repeatMethod 3 self.value='shared' self.calls=3",
                "repeatMethod 3 self.value='shared' self.calls=4",
            ],
        )

        newInfo = RegInfo([])
        newNewInfo = RegInfo([])

        def atTimeDriver() -> MemoryDriver:
            x = MemoryDriver()
            x.advance(dt.timestamp())
            x.advance(days(7))
            return x

        mem2 = atTimeDriver()
        mem3 = atTimeDriver()

        self.assertEqual(mem2.isScheduled(), False)
        persistent = dumps(registry.save(scheduler))
        loadedScheduler = registry.load(mem2, loads(persistent), newInfo)
        repersistent = dumps(registry.save(loadedScheduler))
        registry.load(mem3, loads(repersistent), newNewInfo)
        loaded = loads(persistent)
        with self.assertRaises(KeyError):
            # TODO: allow for better error handling that doesn't just blow up
            # on the type code lookup failure
            emptyRegistry.load(MemoryDriver(), loaded, newInfo)
        self.assertEqual(mem2.isScheduled(), True)
        mem2.advance()
        expectedCalls = [
            "InstanceWithMethods.fromJSON",
            "InstanceWithMethods.fromJSON",
            "InstanceWithMethods.fromJSON (cached)",
            "repeatMethod 4 self.value='sample' self.calls=1",
            "repeatMethod 4 self.value='shared' self.calls=1",
            "repeatMethod 4 self.value='shared' self.calls=2",
        ]
        self.assertEqual(newInfo.calls, expectedCalls)
        self.assertEqual(mem3.isScheduled(), True)
        mem3.advance()
        self.assertEqual(newNewInfo.calls, expectedCalls)

        # round trip:
