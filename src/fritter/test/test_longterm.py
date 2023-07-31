from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from unittest import TestCase
from zoneinfo import ZoneInfo

from datetype import aware
from fritter.longterm import (
    JSONObject,
    JSONRegistry,
    jsonScheduler,
    schedulerFromJSON,
)
from fritter.memory_driver import MemoryDriver


@dataclass
class RegInfo:
    calls: list[str]


registry = JSONRegistry[RegInfo]()

calls = []


@registry.byName
def call1() -> None:
    calls.append("hello")


@registry.byName
def call2() -> None:
    calls.append("goodbye")


@dataclass
class InstanceWithMethods:
    value: str
    info: RegInfo

    @classmethod
    def typeCodeForJSON(self) -> str:
        return "instanceWithMethods"

    @classmethod
    def fromJSON(cls, ctx: RegInfo, json: JSONObject) -> InstanceWithMethods:
        ctx.calls.append("InstanceWithMethods.fromJSON")
        return cls(json["value"], ctx)

    def asJSON(self) -> dict[str, object]:
        return {"value": self.value}

    @registry.asMethod
    def method1(self) -> None:
        self.info.calls.append(f"{self.value}/method1")

    @registry.asMethod
    def method2(self) -> None:
        self.info.calls.append(f"{self.value}/method2")


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
        schedulerFromJSON(memory2, saved, registry.loaders, ri)
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

    def test_loaderMapMethods(self) -> None:
        """
        LoaderMap can act like a mapping, even though it's rarely used as one.
        """
        # TODO: Mapping requires we implement these methods, but are these
        # event he right ones?  we don't enumerate the instance registry, and
        # in order to do it we'd need to more explicitly remember which
        # specific methods are registered.
        self.assertEqual(len(registry.loaders), 2)
        self.assertEqual(list(registry.loaders), ["call1", "call2"])
