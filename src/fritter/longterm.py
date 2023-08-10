"""
Schedule things in terms of datetimes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Generic, Protocol, Type, TypeVar
from zoneinfo import ZoneInfo

from datetype import DateTime


from .boundaries import TimeDriver
from .priority_queue import HeapPriorityQueue
from .scheduler import FutureCall, Scheduler

PersistentCallable = TypeVar("PersistentCallable", bound=Callable[[], None])
FullSerialization = TypeVar("FullSerialization", covariant=True)


@dataclass(frozen=True)
class DateTimeDriver:
    """
    Driver based on aware datetimes.
    """

    driver: TimeDriver[float]
    zone: ZoneInfo = ZoneInfo("Etc/UTC")

    def unschedule(self) -> None:
        """
        Unschedule from underlying driver.
        """
        self.driver.unschedule()

    def reschedule(
        self, newTime: DateTime[ZoneInfo], work: Callable[[], None]
    ) -> None:
        """
        Re-schedule to a new time.
        """
        self.driver.reschedule(newTime.timestamp(), work)

    def now(self) -> DateTime[ZoneInfo]:
        timestamp = self.driver.now()
        return DateTime.fromtimestamp(timestamp, self.zone)


_DriverTypeCheck: Type[TimeDriver[DateTime[ZoneInfo]]] = DateTimeDriver


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
