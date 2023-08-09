from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from unittest import TestCase
from zoneinfo import ZoneInfo

from datetype import aware

from ..jsonterm import (
    JSONableCallable,
    JSONObject,
    JSONRegistry,
    jsonScheduler,
)
from ..longterm import PersistableScheduler, daily
from ..memory_driver import MemoryDriver


@dataclass
class RegInfo:
    calls: list[str]
    identityMap: dict[str, Any] = field(default_factory=dict)


registry = JSONRegistry[RegInfo]()
emptyRegistry = JSONRegistry[RegInfo]()

calls = []


@registry.byName
def call1() -> None:
    calls.append("hello")


@registry.byName
def call2() -> None:
    calls.append("goodbye")


@registry.recurringFunction
def repeating(steps: int) -> None:
    calls.append(f"repeating {steps}")


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
        scheduler: PersistableScheduler[JSONableCallable, JSONObject],
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

    @registry.asMethod
    def method1(self) -> None:
        self.info.calls.append(f"{self.value}/method1")

    @registry.asMethod
    def method2(self) -> None:
        self.info.calls.append(f"{self.value}/method2")

    @registry.recurringMethod
    def recurrence(self, steps: int) -> None:
        self.calls += 1
        self.info.calls.append(
            f"recurrence {steps} {self.value=} {self.calls=}"
        )


class PersistentSchedulerTests(TestCase):
    def tearDown(self) -> None:
        del calls[:]

    def test_scheduleRunSaveRun(self) -> None:
        """
        Test scheduling module-level functions and instance methods.
        """
        memoryDriver = MemoryDriver()
        persistentScheduler = jsonScheduler(memoryDriver)
        dt = aware(
            datetime(
                2023,
                7,
                21,
                1,
                1,
                1,
                tzinfo=ZoneInfo(key="America/Los_Angeles"),
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
                tzinfo=ZoneInfo(key="America/Los_Angeles"),
            ),
            ZoneInfo,
        )
        ri0 = RegInfo([])
        iwm = InstanceWithMethods("test_scheduleRunSaveRun value", ri0)
        persistentScheduler.scheduler.callAtTimestamp(dt, call1)
        persistentScheduler.scheduler.callAtTimestamp(dt, iwm.method1)
        persistentScheduler.scheduler.callAtTimestamp(dt2, call2)
        persistentScheduler.scheduler.callAtTimestamp(dt2, iwm.method2)
        memoryDriver.advance(dt.timestamp() + 1)
        self.assertEqual(calls, ["hello"])
        del calls[:]
        saved = persistentScheduler.save()
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
        persistentScheduler = jsonScheduler(memoryDriver)
        dt = aware(
            datetime(
                2023,
                7,
                21,
                1,
                1,
                1,
                tzinfo=ZoneInfo(key="America/Los_Angeles"),
            ),
            ZoneInfo,
        )
        handle = persistentScheduler.scheduler.callAtTimestamp(dt, call1)
        self.assertEqual(memoryDriver.isScheduled(), True)
        handle.cancel()
        self.assertEqual(memoryDriver.isScheduled(), False)
        memoryDriver.advance(dt.timestamp() + 1)
        self.assertEqual(calls, [])

    def test_emptyScheduler(self) -> None:
        memory = MemoryDriver()
        registry.load(memory, {"scheduledCalls": []}, RegInfo([]))
        self.assertEqual(memory.isScheduled(), False)

    def test_recurring(self) -> None:
        dt = aware(
            datetime(
                2023,
                7,
                21,
                1,
                1,
                1,
                tzinfo=ZoneInfo(key="America/Los_Angeles"),
            ),
            ZoneInfo,
        )
        memoryDriver = MemoryDriver()
        memoryDriver.advance(dt.timestamp())
        persistentScheduler = jsonScheduler(memoryDriver)
        registry.recurring(dt, daily, repeating, persistentScheduler).recur()
        self.assertEqual(calls, ["repeating 1"])
        del calls[:]

        def days(n: int) -> float:
            return 60 * 60 * 24 * n

        memoryDriver.advance(days(3))
        self.assertEqual(calls, ["repeating 3"])
        del calls[:]
        from json import dumps, loads

        newInfo = RegInfo([])
        mem2 = MemoryDriver()
        mem2.advance(dt.timestamp())
        mem2.advance(days(7))
        self.assertEqual(mem2.isScheduled(), False)
        registry.load(mem2, loads(dumps(persistentScheduler.save())), newInfo)
        self.assertEqual(mem2.isScheduled(), True)
        amount = mem2.advance()
        self.assertEqual(amount, 0.0)
        self.assertEqual(calls, ["repeating 4"])

    def test_recurringMethod(self) -> None:
        dt = aware(
            datetime(
                2023,
                7,
                21,
                1,
                1,
                1,
                tzinfo=ZoneInfo(key="America/Los_Angeles"),
            ),
            ZoneInfo,
        )
        memoryDriver = MemoryDriver()
        memoryDriver.advance(dt.timestamp())
        persistentScheduler = jsonScheduler(memoryDriver)
        info = RegInfo([])
        method = InstanceWithMethods("sample", info).recurrence
        shared = InstanceWithMethods("shared", info)
        registry.recurring(dt, daily, method, persistentScheduler).recur()
        registry.recurring(
            dt, daily, shared.recurrence, persistentScheduler
        ).recur()
        registry.recurring(
            dt, daily, shared.recurrence, persistentScheduler
        ).recur()
        self.assertEqual(
            info.calls,
            [
                "recurrence 1 self.value='sample' self.calls=1",
                "recurrence 1 self.value='shared' self.calls=1",
                "recurrence 1 self.value='shared' self.calls=2",
            ],
        )
        del info.calls[:]

        def days(n: int) -> float:
            return 60 * 60 * 24 * n

        memoryDriver.advance(days(3))
        self.assertEqual(
            info.calls,
            [
                "recurrence 3 self.value='sample' self.calls=2",
                "recurrence 3 self.value='shared' self.calls=3",
                "recurrence 3 self.value='shared' self.calls=4",
            ],
        )
        from json import dumps, loads

        newInfo = RegInfo([])
        mem2 = MemoryDriver()
        mem2.advance(dt.timestamp())
        mem2.advance(days(7))
        self.assertEqual(mem2.isScheduled(), False)
        persistent = dumps(persistentScheduler.save())
        registry.load(mem2, loads(persistent), newInfo)
        loaded = loads(persistent)
        with self.assertRaises(KeyError):
            # TODO: allow for better error handling that doesn't just blow up
            emptyRegistry.load(MemoryDriver(), loaded, newInfo)
        self.assertEqual(mem2.isScheduled(), True)
        amount = mem2.advance()
        self.assertEqual(amount, 0.0)
        self.assertEqual(
            newInfo.calls,
            [
                "InstanceWithMethods.fromJSON",
                "InstanceWithMethods.fromJSON",
                "InstanceWithMethods.fromJSON (cached)",
                "recurrence 4 self.value='sample' self.calls=1",
                "recurrence 4 self.value='shared' self.calls=1",
                "recurrence 4 self.value='shared' self.calls=2",
            ],
        )
