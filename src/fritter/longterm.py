"""
Schedule things in terms of datetimes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import (
    Any,
    Callable,
    Generic,
    Iterator,
    Mapping,
    Protocol,
    Type,
    TypeVar,
)
from zoneinfo import ZoneInfo

from datetype import DateTime, fromisoformat

from fritter.boundaries import RepeatingWork
from fritter.priority_queue import HeapPriorityQueue
from fritter.scheduler import FutureCall, Scheduler

from .boundaries import TimeDriver


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
        return DateTime.fromtimestamp(
            self._driver.currentTimestamp(), ZoneInfo("Etc/UTC")
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
    A L{persistentScheduler}C{[X, Y]} can produce a L{Scheduler} restricted to
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
                HeapPriorityQueue(self._calls),
                # TODO: I don't think that Scheduler properly respects being
                # initialized with a non-empty queue
                DateTimeDriver(self._runtimeDriver),
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


class JSONableCallable(Protocol):
    """
    Protocol definition of a serializable callable usable with
    L{JSONSerializer}.
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
        Convert this callable to a JSON-serializable dictionary.
        """


@dataclass
class JSONSerializer:
    """
    Implementation of L{Serializer} protocol in terms of L{JSONableCallable}s.
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
        Collect all the calls and save them into a JSON object.
        """
        return {"scheduledCalls": self._calls}


RuleFunction = Callable[
    [DateTime[ZoneInfo], DateTime[ZoneInfo]],
    tuple[int, DateTime[ZoneInfo]],
]


@dataclass
class Recurring(Generic[PersistentCallable, FullSerialization]):
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

JSONDeserializer = Callable[
    [
        PersistableScheduler[JSONableCallable, dict[str, object]],
        dict[str, object],
    ],
    JSONableCallable,
]

TypeCodeLookup = Mapping[str, JSONDeserializer]


def jsonScheduler(
    runtimeDriver: TimeDriver[float],
) -> PersistableScheduler[JSONableCallable, dict[str, object]]:
    """
    Create a new L{PersistableScheduler} using a given L{TimeDriver} that can
    schedule C{float}s.
    """
    return PersistableScheduler(runtimeDriver, lambda: JSONSerializer([]))


def schedulerFromJSON(
    runtimeDriver: TimeDriver[float],
    serializedJSON: dict[str, Any],
    typeCodeLookup: TypeCodeLookup,
) -> PersistableScheduler[JSONableCallable, dict[str, object]]:
    """
    Load a JSON object in the format serialized from L{JSONSerializer.finalize}
    and a runtime L{TimeDriver}C{[float]}, returning a L{PersistableScheduler}.
    """
    loadedID = 0
    new = PersistableScheduler(
        runtimeDriver,
        lambda: JSONSerializer([]),
    )
    for callJSON in serializedJSON["scheduledCalls"]:
        loadedID -= 1
        when = fromisoformat(callJSON["when"]).replace(
            tzinfo=ZoneInfo(callJSON["tz"])
        )
        typeCode = callJSON["what"]["type"]
        what = typeCodeLookup[typeCode](new, callJSON["what"]["data"])
        new.scheduler.callAtTimestamp(when, what)
    return new


@dataclass
class SerializableFunction:
    original: Callable[[], None]
    typeCode: str

    def __call__(self) -> None:
        self.original()

    def typeCodeForJSON(self) -> str:
        return self.typeCode

    def asJSON(self) -> dict[str, object]:
        return {}


@dataclass
class LoaderMap(TypeCodeLookup):
    registry: dict[str, JSONableCallable]

    def __getitem__(
        self, key: str
    ) -> Callable[
        [
            PersistableScheduler[JSONableCallable, dict[str, object]],
            dict[str, object],
        ],
        JSONableCallable,
    ]:
        def loader(
            scheduler: PersistableScheduler[
                JSONableCallable, dict[str, object]
            ],
            json: dict[str, object],
        ) -> JSONableCallable:
            return self.registry[key]

        return loader

    def __iter__(self) -> Iterator[str]:
        if False:
            yield

    def __len__(self) -> int:
        return 0


@dataclass
class JSONRegistry:
    registry: dict[str, JSONableCallable] = field(default_factory=dict)

    @property
    def loaders(self) -> TypeCodeLookup:
        return LoaderMap(self.registry)

    def byName(self, cb: Callable[[], None]) -> JSONableCallable:
        func = SerializableFunction(cb, cb.__name__)
        self.registry[cb.__name__] = func
        return func
