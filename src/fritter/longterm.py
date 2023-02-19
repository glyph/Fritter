"""
Schedule things in terms of datetimes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Callable, Generic, Mapping, Protocol, Type, TypeVar
from zoneinfo import ZoneInfo

from datetype import DateTime, fromisoformat

from .boundaries import TimeDriver
from fritter.boundaries import RepeatingWork
from fritter.priority_queue import HeapPriorityQueue
from fritter.scheduler import FutureCall, Scheduler


@dataclass
class DateTimeDriver:
    """
    Driver based on aware datetimes.
    """

    _driver: TimeDriver[float]

    def unschedule(self) -> None:
        """
        Unschedule from underlying driver.
        """
        self._driver.unschedule()

    def reschedule(
        self, newTime: DateTime[ZoneInfo], work: Callable[[], None]
    ) -> None:
        """
        Re-schedule to a new time.
        """
        self._driver.reschedule(newTime.timestamp(), work)

    def currentTimestamp(self) -> DateTime[ZoneInfo]:
        return DateTime.now(ZoneInfo("Etc/UTC"))


_: Type[TimeDriver[DateTime[ZoneInfo]]] = DateTimeDriver


PersistentCallable = TypeVar("PersistentCallable", bound=Callable[[], None])
FullSerialization = TypeVar("FullSerialization", covariant=True)


class Serializer(Protocol[PersistentCallable, FullSerialization]):
    """
    An object that can serialize some FutureCalls into something.
    """

    def add(
        self, item: FutureCall[DateTime[ZoneInfo], PersistentCallable]
    ) -> None:
        """
        Add a FutureCall to the set to be serialized.
        """

    def finish(self) -> FullSerialization:
        """
        Complete the serialization.
        """


@dataclass
class PersistableScheduler(Generic[PersistentCallable, FullSerialization]):
    """
    A scheduler whomst may persist.
    """

    _runtimeDriver: TimeDriver[float]
    _serializerFactory: Callable[
        [], Serializer[PersistentCallable, FullSerialization]
    ]

    _scheduler: Scheduler[DateTime[ZoneInfo], PersistentCallable] | None = None
    _calls: list[FutureCall[DateTime[ZoneInfo], PersistentCallable]] = field(
        default_factory=list
    )

    @property
    def scheduler(self) -> Scheduler[DateTime[ZoneInfo], PersistentCallable]:
        """
        Create the scheduler if we need one.
        """
        if self._scheduler is None:
            self._scheduler = Scheduler(
                HeapPriorityQueue(self._calls),
                DateTimeDriver(self._runtimeDriver),
            )
        return self._scheduler

    def save(self) -> FullSerialization:
        """
        serialize everything
        """
        serializer = self._serializerFactory()
        for item in self._calls:
            serializer.add(item)
        return serializer.finish()


class JSONableCallable(Protocol):
    """
    It's callable! It's JSONable!
    """

    def __call__(self) -> None:
        """
        Do the work of the callable.
        """

    def typeCodeForJSON(self) -> str:
        """
        Type-code to be looked up later.
        """

    def asJSON(self) -> dict[str, object]:
        """
        Serialize this callable to JSON.
        """


@dataclass
class JSONSerializer:
    """
    JSON Serializer.
    """

    _calls: list[dict[str, object]]

    def add(
        self, item: FutureCall[DateTime[ZoneInfo], JSONableCallable]
    ) -> None:
        self._calls.append(
            {
                "when": item.when.replace(tzinfo=None).isoformat(),
                "tz": item.when.tzinfo.key,
                "what": {
                    "type": item.what.typeCodeForJSON(),
                    "data": item.what.asJSON(),
                },
                "called": item.called,
                "canceled": item.canceled,
            }
        )

    def finish(self) -> dict[str, object]:
        """
        Collect all the calls and save them.
        """
        return {"scheduledCalls": self._calls}


def jsonScheduler(
    runtimeDriver: TimeDriver[float],
) -> PersistableScheduler[JSONableCallable, dict[str, object]]:
    """
    Create a new persistable scheduler.
    """
    return PersistableScheduler(runtimeDriver, lambda: JSONSerializer([]))


RuleFunction = Callable[
    [DateTime[ZoneInfo], DateTime[ZoneInfo]],
    tuple[int, DateTime[ZoneInfo]],
]


@dataclass
class Recurring(Generic[PersistentCallable, FullSerialization]):
    """ """

    desiredTime: DateTime[ZoneInfo]
    rule: RuleFunction
    callback: RepeatingWork
    convert: Callable[
        [Recurring[PersistentCallable, FullSerialization]],
        PersistentCallable,
    ]
    scheduler: PersistableScheduler[PersistentCallable, FullSerialization]

    def recur(self) -> None:
        callIncrement, self.desiredTime = self.rule(
            self.desiredTime,
            self.scheduler.scheduler.currentTimestamp(),
        )
        self.callback(callIncrement)
        self.scheduler.scheduler.callAtTimestamp(
            self.desiredTime,
            self.convert(self),
        )


def daily(
    desiredTime: DateTime[ZoneInfo],
    currentTime: DateTime[ZoneInfo],
) -> tuple[int, DateTime[ZoneInfo]]:
    return 1, desiredTime + timedelta(days=1)

def dailyWithSkips(
    desiredTime: DateTime[ZoneInfo],
    currentTime: DateTime[ZoneInfo],
) -> tuple[int, DateTime[ZoneInfo]]:
    days = 0
    nextDesired = desiredTime
    while nextDesired < currentTime:
        days += 1
        nextDesired += timedelta(days=1)
    return days, nextDesired

__: RuleFunction

__ = daily
__ = dailyWithSkips


def schedulerFromJSON(
    runtimeDriver: TimeDriver[float],
    serializedJSON: dict[str, Any],
    codeLookup: Mapping[
        str,
        Callable[
            [
                PersistableScheduler[JSONableCallable, dict[str, object]],
                dict[str, object],
            ],
            JSONableCallable,
        ],
    ],
) -> PersistableScheduler[JSONableCallable, dict[str, object]]:
    """
    Load some JSON.
    """
    calls: list[FutureCall[DateTime[ZoneInfo], JSONableCallable]] = []
    loadedID = 0
    new = PersistableScheduler(
        runtimeDriver, lambda: JSONSerializer([]), _calls=calls
    )
    for callJSON in serializedJSON["scheduledCalls"]:
        loadedID -= 1
        call = FutureCall(
            when=fromisoformat(callJSON["what"]["when"]).replace(
                tzinfo=ZoneInfo(callJSON["tz"])
            ),
            what=codeLookup[callJSON["what"]["type"]](
                new,
                callJSON["what"]["data"],
            ),
            id=loadedID,
            called=callJSON["called"],
            canceled=callJSON["canceled"],
        )
        calls.append(call)
    return new
