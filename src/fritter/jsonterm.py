# -*- test-case-name: fritter.test.test_longterm -*-
from __future__ import annotations

from dataclasses import dataclass, field
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Generic,
    Mapping,
    ParamSpec,
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


class JSONableRecurring(JSONable, Protocol):
    def __call__(self, steps: int) -> None:
        """
        Do some recurring work.
        """


if TYPE_CHECKING:
    __R: RepeatingWork
    __JR: JSONableRecurring
    __R = __JR

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


def _whatJSON(what: JSONable) -> JSONObject:
    return {
        "type": what.typeCodeForJSON(),
        "data": what.asJSON(),
    }


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
                "what": _whatJSON(item.what),
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


SomeCallable = TypeVar("SomeCallable", bound=Callable[..., Any])
SomeSignature = ParamSpec("SomeSignature")


@dataclass
class SerializableFunction(Generic[SomeSignature]):
    original: Callable[SomeSignature, object]
    typeCode: str

    def __call__(
        self, *args: SomeSignature.args, **kwargs: SomeSignature.kwargs
    ) -> None:
        self.original(*args, **kwargs)

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
class JSONableBoundRecurring(Generic[JSONableSelf]):
    descriptor: JSONableRecurringDescriptor[JSONableSelf, Any]
    instance: JSONableSelf

    def __call__(self, steps: int) -> None:
        self.descriptor.func(self.instance, steps)

    def asJSON(self) -> JSONObject:
        return self.instance.asJSON()

    def typeCodeForJSON(self) -> str:
        return (
            f"{self.instance.typeCodeForJSON()}."
            f"{self.descriptor.func.__name__}"
        )


@dataclass
class JSONableRecurringDescriptor(Generic[JSONableSelf, LoadContext]):
    registry: JSONRegistry[LoadContext]
    func: Callable[[JSONableSelf, int], None]

    def __set_name__(
        self, cls: Type[JSONableInstance[LoadContext]], name: str
    ) -> None:
        self.registry.registerType(cls)

    def __get__(
        self, instance: JSONableSelf, owner: object = None
    ) -> JSONableBoundRecurring[JSONableSelf]:
        return JSONableBoundRecurring(self, instance)


class JSONableMethodBinder(Protocol[LoadContextInv]):
    def __call__(
        self,
        instance: RecurrenceConverter[LoadContextInv],
        owner: object = None,
    ) -> JSONableBoundMethod[RecurrenceConverter[LoadContextInv]]:
        ...


class HasTypeCode(Protocol):
    def typeCodeForJSON(self) -> str:
        ...


JSONableType = TypeVar("JSONableType", bound=HasTypeCode)


@dataclass
class SpecificTypeRegistration(Generic[JSONableType]):
    registered: dict[str, JSONableType] = field(default_factory=dict)

    def add(self, item: JSONableType) -> JSONableType:
        self.registered[item.typeCodeForJSON()] = item
        return item

    def get(self, typeCode: str) -> JSONableType | None:
        return self.registered.get(typeCode, None)


@dataclass
class JSONRegistry(Generic[LoadContext]):
    _functions: SpecificTypeRegistration[JSONableCallable] = field(
        default_factory=SpecificTypeRegistration
    )
    _recurring: SpecificTypeRegistration[JSONableRecurring] = field(
        default_factory=SpecificTypeRegistration
    )
    _instances: SpecificTypeRegistration[
        Type[JSONableInstance[LoadContext]]
    ] = field(default_factory=SpecificTypeRegistration)

    # Can't store the descriptor directly due to
    # https://github.com/python/mypy/issues/15822
    converterMethod: JSONableMethodBinder[LoadContext] = field(init=False)

    def _loadOne(
        self,
        json: JSONObject,
        which: SpecificTypeRegistration[JSONableType],
        ctx: LoadContext,
        sched: JSONScheduler,
    ) -> JSONableType:
        # inverse of _whatJSON
        typeCode = json["type"]
        blob = json["data"]

        if (it := which.get(typeCode)) is not None:
            return it

        classCode, methodName = typeCode.rsplit(".", 1)
        if (instanceType := self._instances.get(classCode)) is not None:
            # TODO: record allowable instance/method pairs so that we have some
            # confidence that the resulting type here is in fact actually
            # `JSONableType`.  probably the right way to do this is to have
            # _instances live on SpecificTypeRegistration rather than be shared
            # between both recurring/non-recurring types
            result: JSONableType = getattr(
                instanceType.fromJSON(self, sched, ctx, blob),
                methodName,
            )
            return result

        # TODO: this is for *long-term* storage of sets of scheduled events, so
        # failing the entire load like this is probably not always an
        # acceptable failure mode.  We should identify any calls that failed to
        # load, remember their uninterpreted blobs to be included again in
        # save() so we don't lose them, then communicate the failure to an
        # object passed to .load()

        raise KeyError(f"cannot interpret type code {repr(typeCode)}")

    def __post_init__(self) -> None:
        # TODO: something about bound methods of generics (specifically
        # RecurrenceConverter[LoadContext].recurrenceWrapper) breaks type
        # inference here so we need an explicit declaration, should report this
        # upstream.
        descriptor: JSONableMethodDescriptor[
            RecurrenceConverter[LoadContext], LoadContext
        ] = self.asMethod(RecurrenceConverter.recurrenceWrapper)
        # this is happening after the fact, not during a class definition, so
        # we need to take care of the __set_name__ step manually.
        descriptor.__set_name__(RecurrenceConverter, "recurrenceWrapper")
        self.converterMethod = descriptor.__get__

    def recurring(
        self,
        initialTime: DateTime[ZoneInfo],
        rule: RuleFunction,
        work: JSONableRecurring,
        scheduler: PersistableScheduler[JSONableCallable, JSONObject],
    ) -> Recurring[JSONableCallable, JSONableRecurring, JSONObject]:
        def convert(
            recurring: Recurring[
                JSONableCallable, JSONableRecurring, JSONObject
            ]
        ) -> JSONableCallable:
            return self.converterMethod(RecurrenceConverter(self, recurring))

        return Recurring(initialTime, rule, work, convert, scheduler)

    def byName(self, cb: Callable[[], None]) -> JSONableCallable:
        return self._functions.add(SerializableFunction(cb, cb.__name__))

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

    def recurringFunction(self, cb: RepeatingWork) -> JSONableRecurring:
        return self._recurring.add(
            SerializableFunction(cb, getattr(cb, "__name__"))
        )

    def recurringMethod(
        self, recurring: Callable[[JSONableSelf, int], None]
    ) -> JSONableRecurringDescriptor[JSONableSelf, LoadContext]:
        wrapped = JSONableRecurringDescriptor[JSONableSelf, LoadContext](
            self, recurring
        )
        return wrapped

    def registerType(self, cls: Type[JSONableInstance[LoadContext]]) -> None:
        # TODO: honor method name, keep a record of which ones are allowed for
        # this type
        self._instances.add(cls)

    def load(
        self,
        runtimeDriver: TimeDriver[float],
        serializedJSON: JSONObject,
        loadContext: LoadContext,
    ) -> PersistableScheduler[JSONableCallable, JSONObject]:
        """
        Load a JSON object in the format serialized from
        L{JSONSerializer.finalize} and a runtime L{TimeDriver}C{[float]},
        returning a L{PersistableScheduler}.
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
            what = self._loadOne(
                callJSON["what"],
                self._functions,
                loadContext,
                new,
            )
            new.scheduler.callAtTimestamp(when, what)
        return new


@dataclass
class RecurrenceConverter(Generic[LoadContext]):
    jsonRegistry: JSONRegistry[LoadContext]
    recurring: Recurring[JSONableCallable, JSONableRecurring, JSONObject]

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
        ruleFunction = {"daily": daily}[  # , "dailyWithSkips": dailyWithSkips
            json["rule"]
        ]
        what = json["callable"]
        return cls(
            registry,
            Recurring(
                fromisoformat(json["ts"]).replace(tzinfo=ZoneInfo(json["tz"])),
                ruleFunction,
                registry._loadOne(
                    what, registry._recurring, loadContext, scheduler
                ),
                lambda it: registry.converterMethod(
                    RecurrenceConverter(registry, it)
                ),
                scheduler,
            ),
        )

    def asJSON(self) -> dict[str, object]:
        when = self.recurring.initialTime
        return {
            "ts": when.replace(tzinfo=None).isoformat(),
            "tz": when.tzinfo.key,
            "rule": self.recurring.rule.__name__,  # TODO: lookup table for `RuleFunction` callables
            "callable": _whatJSON(self.recurring.callable),
            # "convert": is self, effectively
            # "scheduler": is what's doing the serializing
        }

    def recurrenceWrapper(self) -> None:
        self.recurring.recur()
