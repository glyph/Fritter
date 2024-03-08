from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from json import dumps, loads
from pathlib import Path
from tempfile import mkdtemp
from typing import Any, Callable, Type
from unittest import TestCase
from zoneinfo import ZoneInfo

from datetype import DateTime, aware

from ..boundaries import (
    Cancellable,
    RecurrenceRule,
    ScheduledCall,
    ScheduledState,
    SomeScheduledCall,
    TimeDriver,
)
from ..drivers.datetimes import DateTimeDriver
from ..drivers.memory import MemoryDriver
from ..persistent.jsonable import (
    JSONableCallable,
    JSONableInstance,
    JSONableRepeatable,
    JSONableScheduler,
    JSONObject,
    JSONRegistry,
    LoadProcess,
    MissingPersistentCall,
    schedulerAtPath,
)
from ..repeat.rules.datetimes import EachYear, daily


@dataclass
class RegInfo:
    madeCalls: list[str]
    identityMap: dict[str, Any] = field(default_factory=dict)
    lookupLater: list[LaterStopper] = field(default_factory=list)


registry = JSONRegistry[RegInfo]()
emptyRegistry = JSONRegistry[RegInfo]()
PT = ZoneInfo(key="America/Los_Angeles")

globalCalls = []


@registry.function
def call1() -> None:
    globalCalls.append("hello")


@registry.function
def call2() -> None:
    globalCalls.append("goodbye")


@registry.repeatFunction
def repeatable(steps: int, scheduled: SomeScheduledCall) -> None:
    globalCalls.append(f"repeatable {steps}")


@dataclass
class InstanceWithMethods:
    value: str
    info: RegInfo
    callCount: int = 0
    stoppers: list[Cancellable] = field(default_factory=list)

    @classmethod
    def typeCodeForJSON(self) -> str:
        return "instanceWithMethods"

    @classmethod
    def fromJSON(
        cls, load: LoadProcess[RegInfo], json: JSONObject
    ) -> InstanceWithMethods:
        key = json["identity"]
        if key in load.bootstrap.identityMap:
            load.bootstrap.madeCalls.append(
                f"InstanceWithMethods.fromJSON: {json['value']} (cached)"
            )
            self: InstanceWithMethods = load.bootstrap.identityMap[key]
            return self
        load.bootstrap.madeCalls.append(
            f"InstanceWithMethods.fromJSON: {json['value']}"
        )
        new = cls(json["value"], load.bootstrap)
        load.bootstrap.identityMap[key] = new
        return new

    def toJSON(self, registry: JSONRegistry[RegInfo]) -> dict[str, object]:
        return {
            "value": self.value,
            "identity": id(self),
        }

    @registry.method
    def method1(self) -> None:
        self.info.madeCalls.append(f"{self.value}/method1")

    @registry.method
    def method2(self) -> None:
        self.info.madeCalls.append(f"{self.value}/method2")

    @registry.repeatMethod
    def repeatMethod(self, steps: int, scheduled: SomeScheduledCall) -> None:
        self.callCount += 1
        self.stoppers.append(scheduled)
        self.info.madeCalls.append(
            f"repeatMethod {steps} {self.value=} {self.callCount=}"
        )

    @registry.repeatMethod
    def repeatMethodDTZIL(
        self, steps: list[DateTime[ZoneInfo]], scheduled: SomeScheduledCall
    ) -> None:
        self.callCount += 1
        self.stoppers.append(scheduled)
        self.info.madeCalls.append(
            f"repeatMethod {steps} {self.value=} {self.callCount=}"
        )


Handle = ScheduledCall[DateTime[ZoneInfo], JSONableCallable[RegInfo], int]


@dataclass
class LaterStopper:
    handle: Handle

    @registry.method
    def stop(self) -> None:
        self.handle.cancel()

    @classmethod
    def typeCodeForJSON(self) -> str:
        return "later-stopper"

    def toJSON(self, registry: JSONRegistry[RegInfo]) -> dict[str, object]:
        return {
            "value": registry.saveScheduledCall(self.handle),
        }

    @classmethod
    def fromJSON(
        cls, load: LoadProcess[RegInfo], json: JSONObject
    ) -> LaterStopper:
        new = cls(load.loadScheduledCall(json["value"]))
        load.bootstrap.lookupLater.append(new)
        return new


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
            return registry.saveScheduledCall(it) if it is not None else it

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
        ckey = json["id"]
        if ckey in load.bootstrap.identityMap:
            result: Stoppable = load.bootstrap.identityMap[ckey]
            return result

        def get(
            name: str,
        ) -> Handle | None:
            it = json[name]
            assert it is not None
            loaded = load.loadScheduledCall(it)
            assert loaded.state is ScheduledState.pending
            return loaded

        self = cls(
            runcall=get("runcall"),
            stopcall=get("stopcall"),
            ran=json["ran"],
        )
        # leave it there for the test to pick up
        load.bootstrap.identityMap[ckey] = self
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


def jsonScheduler(
    driver: TimeDriver[float],
) -> tuple[JSONableScheduler[RegInfo], Callable[[], JSONObject]]:
    return registry.createScheduler(DateTimeDriver(driver))


class PersistentSchedulerTests(TestCase):
    def tearDown(self) -> None:
        del globalCalls[:]

    def test_scheduleRunSaveRun(self) -> None:
        """
        Test scheduling module-level functions and instance methods.
        """
        memoryDriver = MemoryDriver()
        scheduler, saver = jsonScheduler(memoryDriver)
        dt = aware(
            datetime(2023, 7, 21, 1, 1, 1, tzinfo=PT),
            ZoneInfo,
        )
        dt2 = aware(
            datetime(2023, 7, 22, 1, 1, 1, tzinfo=PT),
            ZoneInfo,
        )
        ri0 = RegInfo([])
        iwm = InstanceWithMethods("test_scheduleRunSaveRun-value", ri0)
        scheduler.callAt(dt, call1)
        scheduler.callAt(dt, iwm.method1)
        scheduler.callAt(dt2, call2)
        scheduler.callAt(dt2, iwm.method2)
        memoryDriver.advance(dt.timestamp() + 1)
        self.assertEqual(globalCalls, ["hello"])
        del globalCalls[:]
        saved = saver()
        memory2 = MemoryDriver()
        ri = RegInfo([])
        registry.loadScheduler(DateTimeDriver(memory2), saved, ri)
        memory2.advance(dt2.timestamp() + 1)
        self.assertEqual(globalCalls, ["goodbye"])
        self.assertEqual(
            ri0.madeCalls, ["test_scheduleRunSaveRun-value/method1"]
        )
        self.assertEqual(
            ri.madeCalls,
            [
                "InstanceWithMethods.fromJSON: test_scheduleRunSaveRun-value",
                "test_scheduleRunSaveRun-value/method2",
            ],
        )

    def test_persistCancellers(self) -> None:
        """
        scheduled instance methods ought to be able to save handles to other
        instances and stuff
        """
        memoryDriver = MemoryDriver()
        scheduler, saver = jsonScheduler(memoryDriver)
        dt = aware(datetime(2023, 7, 21, 1, 1, 1, tzinfo=PT), ZoneInfo)
        memoryDriver.advance(dt.timestamp() + 1)
        s = Stoppable()
        self.assertEqual(s.ran, False)
        s.runme()
        self.assertEqual(s.ran, True)

        s = Stoppable()
        s.scheduleme(scheduler)
        assert s.runcall is not None
        assert s.stopcall is not None
        s2 = LaterStopper(s.runcall)
        s3 = LaterStopper(s.stopcall)
        s4 = LaterStopper(s.runcall)
        s5 = LaterStopper(s.stopcall)
        scheduler.callAt(
            aware(datetime(2029, 1, 1, tzinfo=PT), ZoneInfo), s2.stop
        )
        scheduler.callAt(
            aware(datetime(2029, 1, 2, tzinfo=PT), ZoneInfo), s3.stop
        )
        scheduler.callAt(
            aware(datetime(2029, 1, 3, tzinfo=PT), ZoneInfo), s4.stop
        )
        last = scheduler.callAt(
            aware(datetime(2029, 1, 4, tzinfo=PT), ZoneInfo), s5.stop
        )
        scheduler.callAt(
            aware(datetime(2029, 1, 5, tzinfo=PT), ZoneInfo),
            LaterStopper(last).stop,
        )
        jsonobj = dumps(saver())
        saved = loads(jsonobj)
        memory2 = MemoryDriver()
        ri = RegInfo([])
        registry.loadScheduler(DateTimeDriver(memory2), saved, ri)
        [run1, stop1, run2, stop2, loadedLast] = ri.lookupLater
        self.assertEqual(run1.handle.state, ScheduledState.pending)
        [(name, loadedStoppable)] = ri.identityMap.items()
        assert isinstance(loadedStoppable, Stoppable)
        self.assertEqual(loadedStoppable.ran, False)
        rc = loadedStoppable.runcall
        sc = loadedStoppable.stopcall
        assert rc is not None
        assert sc is not None
        self.assertEqual(rc.state, ScheduledState.pending)
        self.assertEqual(
            rc.when,
            datetime(2023, 7, 21, 8, 1, 4, tzinfo=ZoneInfo(key="Etc/UTC")),
        )
        self.assertIsNot(rc.what, None)
        self.assertEqual(rc.id, 0)
        memory2.advance(dt.timestamp() + 4.0)
        self.assertEqual(loadedStoppable.ran, False)
        self.assertIs(loadedStoppable.runcall, None)
        self.assertEqual(rc.state, ScheduledState.cancelled)
        self.assertEqual(loadedLast.handle.state, ScheduledState.pending)
        loadedLast.stop()
        self.assertEqual(loadedLast.handle.state, ScheduledState.cancelled)

        # These are loaded reentrantly and cannot be identical, but they map
        # their IDs and are the same
        self.assertEqual(rc.id, run1.handle.id)
        self.assertEqual(sc.id, stop1.handle.id)

        # all references not loaded reentrantly are exactly identical
        self.assertIs(run1.handle, run2.handle)
        self.assertEqual(run1.handle.state, ScheduledState.cancelled)
        self.assertIs(stop1.handle, stop2.handle)

    def test_schedulerAtPath(self) -> None:
        ri0 = RegInfo([])
        iwm = InstanceWithMethods("A", ri0)
        mem = MemoryDriver()
        p = Path(mkdtemp()) / "scheduler.json"
        ts = datetime(2024, 2, 1, tzinfo=ZoneInfo("Etc/UTC")).timestamp()
        mem.advance(ts)
        aw = aware(datetime(2024, 2, 2, tzinfo=ZoneInfo("Etc/UTC")), ZoneInfo)
        with schedulerAtPath(registry, DateTimeDriver(mem), p, ri0) as sched1:
            sched1.callAt(aw, iwm.method1)
        ri1 = RegInfo([])
        mem2 = MemoryDriver()
        with schedulerAtPath(registry, DateTimeDriver(mem2), p, ri1):
            mem2.advance()
        self.assertEqual(
            ri1.madeCalls, ["InstanceWithMethods.fromJSON: A", "A/method1"]
        )

    def test_noSuchCallID(self) -> None:
        mem = MemoryDriver()
        with self.assertRaises(MissingPersistentCall) as raised:
            registry.loadScheduler(
                DateTimeDriver(mem),
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
        scheduler, saver = jsonScheduler(memoryDriver)
        dt = aware(
            datetime(2023, 7, 21, 1, 1, 1, tzinfo=PT),
            ZoneInfo,
        )
        handle = scheduler.callAt(dt, call1)
        self.assertEqual(memoryDriver.isScheduled(), True)
        handle.cancel()
        self.assertEqual(memoryDriver.isScheduled(), False)
        memoryDriver.advance(dt.timestamp() + 1)
        self.assertEqual(globalCalls, [])

    def test_emptyScheduler(self) -> None:
        memory = MemoryDriver()
        registry.loadScheduler(
            DateTimeDriver(memory), {"scheduledCalls": []}, RegInfo([])
        )
        self.assertEqual(memory.isScheduled(), False)

    def test_repeatable(self) -> None:
        dt = aware(
            datetime(2023, 7, 21, 1, 1, 1, tzinfo=PT),
            ZoneInfo,
        )
        memoryDriver = MemoryDriver()
        memoryDriver.advance(dt.timestamp())
        scheduler, saver = jsonScheduler(memoryDriver)
        registry.repeatedly(scheduler, daily, repeatable, dt)
        self.assertEqual(globalCalls, ["repeatable 1"])
        del globalCalls[:]

        def days(n: int) -> float:
            return 60 * 60 * 24 * n

        memoryDriver.advance(days(3))
        self.assertEqual(globalCalls, ["repeatable 3"])
        del globalCalls[:]

        newInfo = RegInfo([])
        mem2 = MemoryDriver()
        mem2.advance(dt.timestamp())
        mem2.advance(days(7))
        self.assertEqual(mem2.isScheduled(), False)
        registry.loadScheduler(
            DateTimeDriver(mem2), loads(dumps(saver())), newInfo
        )
        self.assertEqual(mem2.isScheduled(), True)
        amount = mem2.advance()
        assert amount is not None
        self.assertLess(amount, 0.0001)
        self.assertEqual(globalCalls, ["repeatable 4"])

    def test_repeatEachYear(self) -> None:
        memoryDriver = MemoryDriver()
        dt = aware(
            datetime(2023, 7, 21, 1, 1, 1, tzinfo=PT),
            ZoneInfo,
        )
        scheduler: JSONableScheduler[RegInfo]
        scheduler, saver = jsonScheduler(memoryDriver)
        ri = RegInfo([])
        iwm = InstanceWithMethods("test_repeatEachYear", ri)
        rrule: RecurrenceRule[DateTime[ZoneInfo], list[DateTime[ZoneInfo]]] = (
            EachYear(2)
        )
        repeatMethod: JSONableRepeatable[RegInfo, list[DateTime[ZoneInfo]]] = (
            iwm.repeatMethodDTZIL
        )
        registry.repeatedly(scheduler, rrule, repeatMethod, dt)
        newInfo = RegInfo([])
        mem2 = MemoryDriver()
        mem2.advance(dt.timestamp())
        registry.loadScheduler(
            DateTimeDriver(mem2), loads(dumps(saver())), newInfo
        )
        mem2.advance(timedelta(days=365 * 4).total_seconds())
        LA = "zoneinfo.ZoneInfo(key='America/Los_Angeles')"
        expectedCalls = [
            "InstanceWithMethods.fromJSON: test_repeatEachYear",
            "repeatMethod ["
            f"datetime.datetime(2023, 7, 21, 1, 1, 1, tzinfo={LA}), "
            f"datetime.datetime(2025, 7, 21, 1, 1, 1, tzinfo={LA})"
            "] self.value='test_repeatEachYear' self.callCount=1",
        ]
        self.assertEqual(newInfo.madeCalls, expectedCalls)

    def test_repeatLoadError(self) -> None:
        dt = aware(
            datetime(2023, 7, 21, 1, 1, 1, tzinfo=PT),
            ZoneInfo,
        )
        memoryDriver = MemoryDriver()
        memoryDriver.advance(dt.timestamp())
        oneCall = {
            "when": "2023-07-22T08:01:01",
            "tz": "Etc/UTC",
            "what": {
                "type": "fritter:repetition.repeat",
                "data": {
                    "ts": "2023-07-22T08:01:01",
                    "tz": "Etc/UTC",
                    "rule": {
                        "type": "incorrect rule type",
                        "data": {"delta": (1, 0, 0)},
                    },
                    "callable": {
                        "type": "instanceWithMethods.repeatMethod",
                        "data": {
                            "value": "sample",
                            "identity": 4335201296,
                        },
                    },
                },
            },
            "called": False,
            "cancelled": False,
            "id": 1,
        }
        with self.assertRaises(KeyError) as ke:
            registry.loadScheduler(
                DateTimeDriver(memoryDriver),
                {
                    "scheduledCalls": [oneCall],
                    "counter": "1",
                },
                RegInfo([]),
            )
        self.assertEqual(
            str(ke.exception),
            repr("cannot interpret rule type code 'incorrect rule type'"),
        )

    def test_repeatableMethod(self) -> None:
        dt = aware(
            datetime(2023, 7, 21, 1, 1, 1, tzinfo=PT),
            ZoneInfo,
        )
        memoryDriver = MemoryDriver()
        memoryDriver.advance(dt.timestamp())
        scheduler, saver = jsonScheduler(memoryDriver)
        info = RegInfo([])
        inst = InstanceWithMethods("sample", info)
        method = inst.repeatMethod
        shared = InstanceWithMethods("shared", info)
        registry.repeatedly(scheduler, daily, method)
        registry.repeatedly(scheduler, daily, shared.repeatMethod)
        registry.repeatedly(scheduler, daily, shared.repeatMethod)
        self.assertEqual(
            info.madeCalls,
            [
                "repeatMethod 1 self.value='sample' self.callCount=1",
                "repeatMethod 1 self.value='shared' self.callCount=1",
                "repeatMethod 1 self.value='shared' self.callCount=2",
            ],
        )
        del info.madeCalls[:]

        def days(n: int) -> float:
            return 60 * 60 * 24 * n

        memoryDriver.advance(days(3))
        expected = [
            "repeatMethod 3 self.value='sample' self.callCount=2",
            "repeatMethod 3 self.value='shared' self.callCount=3",
            "repeatMethod 3 self.value='shared' self.callCount=4",
        ]

        self.assertEqual(info.madeCalls, expected)

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
        persistent = dumps(saver())
        loadedScheduler, saver2 = registry.loadScheduler(
            DateTimeDriver(mem2), loads(persistent), newInfo
        )
        repersistent = dumps(saver2())
        registry.loadScheduler(
            DateTimeDriver(mem3), loads(repersistent), newNewInfo
        )
        loaded = loads(persistent)
        with self.assertRaises(KeyError):
            # TODO: allow for better error handling that doesn't just blow up
            # on the type code lookup failure
            emptyRegistry.loadScheduler(
                DateTimeDriver(MemoryDriver()), loaded, newInfo
            )
        self.assertEqual(mem2.isScheduled(), True)
        mem2.advance()
        expectedCalls = [
            "InstanceWithMethods.fromJSON: sample",
            "InstanceWithMethods.fromJSON: shared",
            "InstanceWithMethods.fromJSON: shared (cached)",
            "repeatMethod 4 self.value='sample' self.callCount=1",
            "repeatMethod 4 self.value='shared' self.callCount=1",
            "repeatMethod 4 self.value='shared' self.callCount=2",
        ]
        self.assertEqual(newInfo.madeCalls, expectedCalls)
        self.assertEqual(mem3.isScheduled(), True)
        mem3.advance()
        self.assertEqual(newNewInfo.madeCalls, expectedCalls)

        # round trip:
