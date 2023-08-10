"""
Schedule things in terms of datetimes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Callable, Generic, Protocol, Type, TypeVar
from zoneinfo import ZoneInfo

from datetype import DateTime

from fritter.scheduler import WhenT

from .boundaries import RepeatingWork, TimeDriver
from .priority_queue import HeapPriorityQueue
from .scheduler import FutureCall, Scheduler


@dataclass
class DateTimeDriver:
    """
    Driver based on aware datetimes.
    """

    _driver: TimeDriver[float]
    _localTimezone: ZoneInfo = ZoneInfo("Etc/UTC")

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
        return DateTime.fromtimestamp(
            self._driver.currentTimestamp(), self._localTimezone
        )


_: Type[TimeDriver[DateTime[ZoneInfo]]] = DateTimeDriver


PersistentCallable = TypeVar("PersistentCallable", bound=Callable[[], None])
FullSerialization = TypeVar("FullSerialization", covariant=True)


class Serializer(Protocol[PersistentCallable, FullSerialization]):
    """
    A L{Serializer}C{[X, Y]} can serialize a collection of C{X} - which must be
    at least a 0-argument callable returning None - into a C{Y}.
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
    A L{PersistentScheduler}C{[X, Y]} can produce a L{Scheduler} restricted to
    scheduling callables of type C{X}, which can be serialized to C{Y} by its
    C{save} method.  You must provide a L{TimeDriver}C{[float]} and a callable
    that returns a L{Serializer}C{[X, Y]} to construct one.
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
        Create the scheduler.
        """
        if self._scheduler is None:
            self._scheduler = Scheduler(
                DateTimeDriver(self._runtimeDriver),
                # TODO: Scheduler cannot be initialized with a non-empty queue,
                # so this interface is risky
                HeapPriorityQueue(self._calls),
            )
        return self._scheduler

    def save(self) -> FullSerialization:
        """
        Serialize all the calls scheduled against C{self.scheduler} and return
        the C{FullSerialization} type provided by the serializer.
        """
        serializer = self._serializerFactory()
        for item in self._calls:
            serializer.add(item)
        return serializer.finish()


RuleFunction = Callable[[WhenT, WhenT], tuple[int, WhenT]]


BaseCallable = TypeVar(
    "BaseCallable", bound=Callable[[], None]
)
RecurringCallable = TypeVar(
    "RecurringCallable", bound=RepeatingWork
)

RepeatingWhatT = TypeVar("RepeatingWhatT", bound=RepeatingWork)

@dataclass
class Recurring(
    Generic[
        WhenT, BaseCallable, RecurringCallable, FullSerialization
    ]
):
    initialTime: WhenT
    rule: RuleFunction[WhenT]
    callable: RecurringCallable
    convert: Callable[
        [
            Recurring[
                WhenT,
                BaseCallable,
                RecurringCallable,
                FullSerialization,
            ]
        ],
        BaseCallable,
    ]
    scheduler: Scheduler[WhenT, BaseCallable]

    def recur(self) -> None:
        now = self.scheduler.currentTimestamp()
        callIncrement, self.initialTime = self.rule(self.initialTime, now)
        self.callable(callIncrement)
        self.scheduler.callAtTimestamp(self.initialTime, self.convert(self))


def daily(
    initialTime: DateTime[ZoneInfo], currentTime: DateTime[ZoneInfo]
) -> tuple[int, DateTime[ZoneInfo]]:
    days = 0
    nextDesired = initialTime
    while nextDesired <= currentTime:
        days += 1
        nextDesired += timedelta(days=1)
    return days, nextDesired


__: RuleFunction[DateTime[ZoneInfo]]

__ = daily
# __ = dailyWithSkips
