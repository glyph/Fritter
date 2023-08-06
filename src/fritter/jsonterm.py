# -*- test-case-name: fritter.test.test_longterm -*-
from __future__ import annotations

from dataclasses import dataclass, field
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

from .boundaries import RepeatingWork, TimeDriver
from .longterm import (
    PersistableScheduler,
    Recurring,
    RuleFunction,
    daily,
    dailyWithSkips,
)
from .scheduler import FutureCall

T = TypeVar("T")
LoadContext = TypeVar("LoadContext", contravariant=True)
LoadContextInv = TypeVar("LoadContextInv")
JSONObject = dict[str, Any]


class JSONable(Protocol):
    def typeCodeForJSON(self) -> str:
        """
        Type-code to be looked up later.
        """

    def asJSON(self) -> JSONObject:
        """
        Convert this callable to a JSON-serializable dictionary.
        """


class JSONableCallable(JSONable, Protocol):
    """
    Protocol definition of a serializable callable usable with
    L{JSONSerializer}.
    """

    def __call__(self) -> None:
        """
        Do the work of the callable.
        """


JSONDeserializer = Callable[
    [
        LoadContext,
        PersistableScheduler[JSONableCallable, JSONObject],
        JSONObject,
    ],
    JSONableCallable,
]
TypeCodeLookup = Mapping[str, JSONDeserializer[LoadContext]]
JSONScheduler = PersistableScheduler[JSONableCallable, JSONObject]


class JSONableInstance(JSONable, Protocol[LoadContextInv]):
    @classmethod
    def typeCodeForJSON(cls) -> str:
        ...

    @classmethod
    def fromJSON(
        cls: Type[JSONableSelfCo],
        registry: JSONRegistry[LoadContextInv],
        scheduler: PersistableScheduler[JSONableCallable, JSONObject],
        loadContext: LoadContextInv,
        json: JSONObject,
    ) -> JSONableSelfCo:
        ...


JSONableSelf = TypeVar(
    "JSONableSelf",
    bound=JSONableInstance[Any],
    # See comment in JSONRegistry.asMethod about this bound
)

JSONableSelfCo = TypeVar(
    "JSONableSelfCo", bound=JSONableInstance[Any], covariant=True
)


class JSONableLoader(Protocol[LoadContextInv, JSONableSelfCo]):
    def fromJSON(
        self,
        registry: JSONRegistry[LoadContextInv],
        scheduler: PersistableScheduler[JSONableCallable, JSONObject],
        loadContext: LoadContextInv,
        json: JSONObject,
    ) -> JSONableSelfCo:
        ...


@dataclass
class JSONSerializer:
    """
    Implementation of L{Serializer} protocol in terms of L{JSONableCallable}s.
    """

    _calls: list[JSONObject]

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

    def finish(self) -> JSONObject:
        """
        Collect all the calls and save them into a JSON object.
        """
        return {"scheduledCalls": self._calls}


def jsonScheduler(
    runtimeDriver: TimeDriver[float],
) -> PersistableScheduler[JSONableCallable, JSONObject]:
    """
    Create a new L{PersistableScheduler} using a given L{TimeDriver} that can
    schedule C{float}s.
    """
    return PersistableScheduler(runtimeDriver, lambda: JSONSerializer([]))


def schedulerFromJSON(
    runtimeDriver: TimeDriver[float],
    serializedJSON: JSONObject,
    typeCodeLookup: TypeCodeLookup[LoadContext],
    loadContext: LoadContext,
) -> PersistableScheduler[JSONableCallable, JSONObject]:
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

    def asJSON(self) -> JSONObject:
        return {}


@dataclass
class JSONableBoundMethod(Generic[JSONableSelf]):
    descriptor: JSONableMethodDescriptor[JSONableSelf, Any]
    instance: JSONableSelf

    def __call__(self) -> None:
        self.descriptor.func(self.instance)

    def asJSON(self) -> JSONObject:
        return self.instance.asJSON()

    def typeCodeForJSON(self) -> str:
        return (
            f"{self.instance.typeCodeForJSON()}."
            f"{self.descriptor.func.__name__}"
        )


__JC: Type[JSONableCallable] = JSONableBoundMethod


@dataclass
class JSONableMethodDescriptor(Generic[JSONableSelf, LoadContext]):
    registry: JSONRegistry[LoadContext]
    func: Callable[[JSONableSelf], None]

    def __set_name__(
        self, cls: Type[JSONableInstance[LoadContext]], name: str
    ) -> None:
        self.registry.registerType(cls)

    def __get__(
        self, instance: JSONableSelf, owner: object = None
    ) -> JSONableBoundMethod[JSONableSelf]:
        return JSONableBoundMethod(self, instance)


@dataclass
class LoaderMap(TypeCodeLookup[LoadContext]):
    registry: JSONRegistry[LoadContext]

    def __getitem__(self, key: str) -> JSONDeserializer[LoadContext]:
        def loader(
            ctx: LoadContext, sched: JSONScheduler, json: JSONObject
        ) -> JSONableCallable:
            if key in self.registry.registeredFunctions:
                return self.registry.registeredFunctions[key]
            else:
                typeCode, methodName = key.rsplit(".", 1)
                result: JSONableCallable = getattr(
                    self.registry.registeredInstances[typeCode].fromJSON(
                        self.registry, sched, ctx, json
                    ),
                    methodName,
                )
                return result

        return loader

    def __iter__(self) -> Iterator[str]:
        return iter(self.registry.registeredFunctions.keys())

    def __len__(self) -> int:
        return len(self.registry.registeredFunctions)


class JSONableMethodBinder(Protocol[LoadContextInv]):
    def __call__(
        self,
        instance: RecurrenceConverter[LoadContextInv],
        owner: object = None,
    ) -> JSONableBoundMethod[RecurrenceConverter[LoadContextInv]]:
        ...


@dataclass
class JSONRegistry(Generic[LoadContext]):
    registeredFunctions: dict[str, JSONableCallable] = field(
        default_factory=dict
    )
    registeredInstances: dict[
        str, Type[JSONableInstance[LoadContext]]
    ] = field(default_factory=dict)

    # Can't store the descriptor directly due to https://github.com/python/mypy/issues/15822
    converterMethod: JSONableMethodBinder[LoadContext] = field(init=False)

    def __post_init__(self) -> None:
        # TODO: something about bound methods of generics (specifically
        # RecurrenceConverter[LoadContext].recurrenceWrapper) breaks type
        # inference here so we need an explicit declaration, should report this
        # upstream.
        descriptor: JSONableMethodDescriptor[
            RecurrenceConverter[LoadContext], LoadContext
        ] = self.asMethod(RecurrenceConverter.recurrenceWrapper)
        self.converterMethod = descriptor.__get__

    @property
    def loaders(self) -> LoaderMap[LoadContext]:
        return LoaderMap(self)

    def recurring(
        self,
        initialTime: DateTime[ZoneInfo],
        rule: RuleFunction,
        callback: RepeatingWork,
        scheduler: PersistableScheduler[JSONableCallable, JSONObject],
    ) -> Recurring[JSONableCallable, JSONObject]:
        def convert(
            recurring: Recurring[JSONableCallable, JSONObject]
        ) -> JSONableCallable:
            return self.converterMethod(RecurrenceConverter(self, recurring))

        return Recurring(
            initialTime,
            rule,
            callback,
            convert,
            scheduler,
        )

    def byName(self, cb: Callable[[], None]) -> JSONableCallable:
        func = SerializableFunction(cb, cb.__name__)
        self.registeredFunctions[func.typeCodeForJSON()] = func
        return func

    def asMethod(
        self, method: Callable[[JSONableSelf], None]
    ) -> JSONableMethodDescriptor[JSONableSelf, LoadContext]:
        wrapped = JSONableMethodDescriptor[JSONableSelf, LoadContext](
            self, method
        )

        # I want to stipulate that the method I am taking here must have a
        # 'self' parameter whose type is *at least* as strict as
        # JSONableInstance[LoadContext] but may be stricter than that.
        # However, this would require higher-kinded typevars, in order to make
        # JSONableSelf bounded by JSONableInstance[LoadContext] rather than
        # JSONableInstance[Any]: https://github.com/python/typing/issues/548

        return wrapped

    def registerType(self, cls: Type[JSONableInstance[LoadContext]]) -> None:
        # TODO: honor method name, keep a record of which ones are allowed for
        # this type
        self.registeredInstances[cls.typeCodeForJSON()] = cls


@dataclass
class RecurrenceConverter(Generic[LoadContext]):
    jsonRegistry: JSONRegistry[LoadContext]
    recurring: Recurring[JSONableCallable, JSONObject]

    @classmethod
    def typeCodeForJSON(self) -> str:
        return "recurrence"

    @classmethod
    def fromJSON(
        cls,
        registry: JSONRegistry[LoadContext],
        scheduler: PersistableScheduler[JSONableCallable, JSONObject],
        loadContext: LoadContext,
        json: JSONObject,
    ) -> RecurrenceConverter[LoadContext]:
        ruleFunction = {"daily": daily, "dailyWithSkips": dailyWithSkips}[
            json["rule"]
        ]
        return cls(
            registry,
            Recurring(
                fromisoformat(json["ts"]).replace(tzinfo=ZoneInfo(json["tz"])),
                ruleFunction,
                json["callback"],  # TODO
                lambda it: registry.converterMethod(
                    RecurrenceConverter(registry, it)
                ),
                scheduler,
            ),
        )

    def asJSON(self) -> dict[str, object]:
        when = self.recurring.initialTime
        return {
            "recurring": {
                "ts": when.replace(tzinfo=None).isoformat(),
                "tz": when.tzinfo.key,
                "rule": self.recurring.rule.__name__,  # TODO: lookup table for `RuleFunction` callables
                "callback": "TODO",  # TODO: lookup table for recurring callables (takes)
                # "convert": is self, effectively
                # "scheduler": is what's doing the serializing
            }
        }

    def recurrenceWrapper(self) -> None:
        self.recurring.recur()
