from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from json import dumps, loads
from typing import Any, Type
from unittest import TestCase
from zoneinfo import ZoneInfo

from datetype import DateTime, aware

from ..boundaries import Cancellable, TimeDriver
from ..drivers.datetime import DateTimeDriver
from ..drivers.memory import MemoryDriver
from ..persistent.json import (
    JSONableCallable,
    JSONableInstance,
    JSONableScheduler,
    JSONObject,
    JSONRegistry,
    LoadProcess,
    MissingPersistentCall,
)
from ..repeat.rules.datetimes import daily
from ..scheduler import FutureCall


@dataclass
class RegInfo:
    calls: list[str]
    identityMap: dict[str, Any] = field(default_factory=dict)


registry = JSONRegistry[RegInfo]()
emptyRegistry = JSONRegistry[RegInfo]()
PT = ZoneInfo(key="America/Los_Angeles")

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
    stoppers: list[Cancellable] = field(default_factory=list)

    @classmethod
    def typeCodeForJSON(self) -> str:
        return "instanceWithMethods"

    @classmethod
    def fromJSON(
        cls, load: LoadProcess[RegInfo], json: JSONObject
    ) -> InstanceWithMethods:
        key = json["identity"]
        if key in load.context.identityMap:
            load.context.calls.append("InstanceWithMethods.fromJSON (cached)")
            self: InstanceWithMethods = load.context.identityMap[key]
            return self
        load.context.calls.append("InstanceWithMethods.fromJSON")
        new = cls(json["value"], load.context)
        load.context.identityMap[key] = new
        return new

    def toJSON(self, registry: JSONRegistry[RegInfo]) -> dict[str, object]:
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
        self.stoppers.append(stopper)
        self.info.calls.append(
            f"repeatMethod {steps} {self.value=} {self.calls=}"
        )


Handle = FutureCall[DateTime[ZoneInfo], JSONableCallable[RegInfo]]


@dataclass
class Stoppable:
    runcall: Handle | None = None
    stopcall: Handle | None = None
    ran: bool = False

    def scheduleme(self, scheduler: JSONableScheduler[RegInfo]) -> None:
        """
        Schedule 'runme' to run 2 seconds in the future, but 'stopme' to run 1
        second in the future.
        """
        now = scheduler.now()
        self.runcall = scheduler.callAt(now + timedelta(seconds=2), self.runme)
        self.stopcall = scheduler.callAt(
            now + timedelta(seconds=1), self.stopme
        )

    @classmethod
    def typeCodeForJSON(self) -> str:
        return "stoppable"

    def toJSON(self, registry: JSONRegistry[RegInfo]) -> dict[str, object]:
        def save(it: Handle | None) -> object:
            return registry.saveFutureCall(it) if it is not None else it

        return {
            "runcall": save(self.runcall),
            "stopcall": save(self.stopcall),
            "ran": self.ran,
            "id": id(self),
        }

    @classmethod
    def fromJSON(
        cls, load: LoadProcess[RegInfo], json: JSONObject
    ) -> Stoppable:
        if json["id"] in load.context.identityMap:
            result: Stoppable = load.context.identityMap[json["id"]]
            return result

        def get(
            name: str,
        ) -> Handle | None:
            it = json[name]
            return it if it is None else load.loadFutureCall(it)

        self = cls(
            runcall=get("runcall"), stopcall=get("stopcall"), ran=json["ran"]
        )
        # leave it there for the test to pick up
        load.context.identityMap[json["id"]] = self
        return self

    @registry.method
    def stopme(self) -> None:
        assert self.runcall is not None
        self.stopcall = None
        self.runcall.cancel()
        self.runcall = None

    @registry.method
    def runme(self) -> None:
        self.ran = True
        self.runcall = None


stp: Type[JSONableInstance[RegInfo]] = Stoppable


def jsonScheduler(driver: TimeDriver[float]) -> JSONableScheduler[RegInfo]:
    return registry.new(DateTimeDriver(driver))


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
            datetime(2023, 7, 21, 1, 1, 1, tzinfo=PT),
            ZoneInfo,
        )
        dt2 = aware(
            datetime(2023, 7, 22, 1, 1, 1, tzinfo=PT),
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

    def test_persistCancellers(self) -> None:
        """
        scheduled instance methods ought to be able to save handles to other
        instances and stuff
        """
        memoryDriver = MemoryDriver()
        scheduler = jsonScheduler(memoryDriver)
        dt = aware(datetime(2023, 7, 21, 1, 1, 1, tzinfo=PT), ZoneInfo)
        memoryDriver.advance(dt.timestamp() + 1)
        s = Stoppable()
        s.scheduleme(scheduler)
        jsonobj = dumps(registry.save(scheduler))
        saved = loads(jsonobj)
        memory2 = MemoryDriver()
        ri = RegInfo([])
        registry.load(memory2, saved, ri)
        [(name, loadedStoppable)] = ri.identityMap.items()
        assert isinstance(loadedStoppable, Stoppable)
        memory2.advance(dt.timestamp() + 3.0)

    def test_noSuchCallID(self) -> None:
        mem = MemoryDriver()
        with self.assertRaises(MissingPersistentCall) as raised:
            registry.load(
                mem,
                {
                    "scheduledCalls": [
                        {
                            "when": "2023-07-21T08:01:03",
                            "tz": "Etc/UTC",
                            "what": {
                                "type": "stoppable.stopme",
                                "data": {
                                    "runcall": {"id": 7},
                                    "stopcall": {"id": 2},
                                    "ran": False,
                                    "id": 4411099664,
                                },
                            },
                            "called": False,
                            "canceled": False,
                            "id": 2,
                        }
                    ],
                    "counter": "2",
                },
                RegInfo([]),
            )
        self.assertEqual(raised.exception.args[0], 7)

    def test_idling(self) -> None:
        memoryDriver = MemoryDriver()
        scheduler = jsonScheduler(memoryDriver)
        dt = aware(
            datetime(2023, 7, 21, 1, 1, 1, tzinfo=PT),
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
            datetime(2023, 7, 21, 1, 1, 1, tzinfo=PT),
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
            datetime(2023, 7, 21, 1, 1, 1, tzinfo=PT),
            ZoneInfo,
        )
        memoryDriver = MemoryDriver()
        memoryDriver.advance(dt.timestamp())
        scheduler = jsonScheduler(memoryDriver)
        info = RegInfo([])
        inst = InstanceWithMethods("sample", info)
        method = inst.repeatMethod
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
