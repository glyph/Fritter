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


class JSONable(Protocol):
    def typeCodeForJSON(self) -> str:
        """
        Type-code to be looked up later.
        """

    def asJSON(self) -> JSONObject:
        """
        Convert this callable to a JSON-serializable dictionary.
        """


T = TypeVar("T")
LoadContext = TypeVar("LoadContext", contravariant=True)


class JSONableInstance(JSONable, Protocol[LoadContext]):
    @classmethod
    def typeCodeForJSON(cls) -> str:
        ...

    @classmethod
    def fromJSON(
        cls: Type[T], loadContext: LoadContext, json: JSONObject
    ) -> T:
        ...


class JSONableCallable(JSONable, Protocol):
    """
    Protocol definition of a serializable callable usable with
    L{JSONSerializer}.
    """

    def __call__(self) -> None:
        """
        Do the work of the callable.
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
        LoadContext,
        PersistableScheduler[JSONableCallable, dict[str, object]],
        dict[str, object],
    ],
    JSONableCallable,
]

TypeCodeLookup = Mapping[str, JSONDeserializer[LoadContext]]


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
    typeCodeLookup: TypeCodeLookup[LoadContext],
    loadContext: LoadContext,
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
        what = typeCodeLookup[typeCode](
            loadContext, new, callJSON["what"]["data"]
        )
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


JSONScheduler = PersistableScheduler[JSONableCallable, dict[str, object]]
JSONObject = dict[str, Any]


JI = TypeVar("JI", bound=JSONableInstance[object])


@dataclass
class JSONableBoundMethod(Generic[JI]):
    descriptor: JSONableMethodDescriptor[JI, Any]
    instance: JI

    def __call__(self) -> None:
        self.descriptor.func(self.instance)

    def asJSON(self) -> dict[str, object]:
        return self.instance.asJSON()

    def typeCodeForJSON(self) -> str:
        return (
            f"{self.instance.typeCodeForJSON()}."
            f"{self.descriptor.func.__name__}"
        )


__JC: Type[JSONableCallable] = JSONableBoundMethod


@dataclass
class JSONableMethodDescriptor(Generic[JI, LoadContext]):
    registry: JSONRegistry[LoadContext]
    func: Callable[[JI], None]

    def __set_name__(self, cls: Type[JI], name: str) -> None:
        self.registry.registerMethodWithType(cls, self.func.__name__)

    def __get__(
        self, instance: JI, owner: object = None
    ) -> JSONableBoundMethod[JI]:
        return JSONableBoundMethod(self, instance)


@dataclass
class LoaderMap(TypeCodeLookup[LoadContext]):
    registry: dict[str, JSONableCallable]
    instanceRegistry: dict[str, Type[JSONableInstance[LoadContext]]]

    def __getitem__(self, key: str) -> JSONDeserializer[LoadContext]:
        def loader(
            ctx: LoadContext, sched: JSONScheduler, json: JSONObject
        ) -> JSONableCallable:
            if key in self.registry:
                return self.registry[key]
            else:
                typeCode, methodName = key.rsplit(".", 1)
                result: JSONableCallable = getattr(
                    self.instanceRegistry[typeCode].fromJSON(ctx, json),
                    methodName,
                )
                return result

        return loader

    def __iter__(self) -> Iterator[str]:
        return iter(self.registry.keys())

    def __len__(self) -> int:
        return len(self.registry)


SomeContext = TypeVar(
    "SomeContext",
    bound=JSONableInstance[Any],
    # See comment in JSONRegistry.asMethod about this bound
)


@dataclass
class JSONRegistry(Generic[LoadContext]):
    registry: dict[str, JSONableCallable] = field(default_factory=dict)
    instanceRegistry: dict[str, Type[JSONableInstance[LoadContext]]] = field(
        default_factory=dict
    )

    @property
    def loaders(self) -> TypeCodeLookup[LoadContext]:
        return LoaderMap(self.registry, self.instanceRegistry)

    def byName(self, cb: Callable[[], None]) -> JSONableCallable:
        func = SerializableFunction(cb, cb.__name__)
        self.registry[func.typeCodeForJSON()] = func
        return func

    def asMethod(
        self, method: Callable[[SomeContext], None]
    ) -> JSONableMethodDescriptor[SomeContext, LoadContext]:

        wrapped = JSONableMethodDescriptor[SomeContext, LoadContext](
            self, method
        )

        # I want to stipulate that the method I am taking here must have a
        # 'self' parameter whose type is *at least* as strict as
        # JSONableInstance[LoadContext] but may be stricter than that.
        # However, this would require higher-kinded typevars, in order to make
        # SomeContext bounded by JSONableInstance[LoadContext] rather than
        # JSONableInstance[Any]: https://github.com/python/typing/issues/548

        return wrapped

    def registerMethodWithType(
        self, cls: Type[JSONableInstance[LoadContext]], name: str
    ) -> None:
        # TODO: honor 'name', keep a record of which ones are allowed for this
        # type
        self.instanceRegistry[cls.typeCodeForJSON()] = cls
