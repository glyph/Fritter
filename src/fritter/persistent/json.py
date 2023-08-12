# -*- test-case-name: fritter.test.test_json -*-
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
from fritter.drivers.datetime import DateTimeDriver
from fritter.scheduler import Scheduler

from ..boundaries import RepeatingWork, TimeDriver
from ..repeat import Repeating, RuleFunction, daily

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


class JSONableRepeating(JSONable, Protocol):
    def __call__(self, steps: int) -> None:
        """
        Do some repeating work.
        """


if TYPE_CHECKING:
    __R: RepeatingWork
    __JR: JSONableRepeating
    __R = __JR

JSONDeserializer = Callable[
    [
        LoadContext,
        JSONObject,
    ],
    JSONableCallable,
]
TypeCodeLookup = Mapping[str, JSONDeserializer[LoadContext]]
JSONableScheduler = Scheduler[DateTime[ZoneInfo], JSONableCallable]


class JSONableInstance(JSONable, Protocol[LoadContextInv]):
    @classmethod
    def typeCodeForJSON(cls) -> str:
        ...

    @classmethod
    def fromJSON(
        cls: Type[JSONableSelfCo],
        registry: JSONRegistry[LoadContextInv],
        scheduler: JSONableScheduler,
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
        scheduler: JSONableScheduler,
        loadContext: LoadContextInv,
        json: JSONObject,
    ) -> JSONableSelfCo:
        ...


def _whatJSON(what: JSONable) -> JSONObject:
    return {
        "type": what.typeCodeForJSON(),
        "data": what.asJSON(),
    }


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
class JSONableBoundRepeating(Generic[JSONableSelf]):
    descriptor: JSONableRepeatingDescriptor[JSONableSelf, Any]
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
class JSONableRepeatingDescriptor(Generic[JSONableSelf, LoadContext]):
    registry: JSONRegistry[LoadContext]
    func: Callable[[JSONableSelf, int], None]

    def __set_name__(
        self, cls: Type[JSONableInstance[LoadContext]], name: str
    ) -> None:
        self.registry.registerType(cls)

    def __get__(
        self, instance: JSONableSelf, owner: object = None
    ) -> JSONableBoundRepeating[JSONableSelf]:
        return JSONableBoundRepeating(self, instance)


class JSONableMethodBinder(Protocol[LoadContextInv]):
    def __call__(
        self,
        instance: RepeatenceConverter[LoadContextInv],
        owner: object = None,
    ) -> JSONableBoundMethod[RepeatenceConverter[LoadContextInv]]:
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
    _repeating: SpecificTypeRegistration[JSONableRepeating] = field(
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
        scheduler: JSONableScheduler,
        which: SpecificTypeRegistration[JSONableType],
        ctx: LoadContext,
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
            # between both repeating/non-repeating types
            result: JSONableType = getattr(
                instanceType.fromJSON(self, scheduler, ctx, blob),
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
        # RepeatenceConverter[LoadContext].repeatenceWrapper) breaks type
        # inference here so we need an explicit declaration, should report this
        # upstream.
        descriptor: JSONableMethodDescriptor[
            RepeatenceConverter[LoadContext], LoadContext
        ] = self.asMethod(RepeatenceConverter.repeatenceWrapper)
        # this is happening after the fact, not during a class definition, so
        # we need to take care of the __set_name__ step manually.
        descriptor.__set_name__(RepeatenceConverter, "repeatenceWrapper")
        self.converterMethod = descriptor.__get__

    def repeating(
        self,
        reference: DateTime[ZoneInfo],
        rule: RuleFunction[DateTime[ZoneInfo]],
        work: JSONableRepeating,
        scheduler: JSONableScheduler,
    ) -> Repeating[DateTime[ZoneInfo], JSONableCallable, JSONableRepeating]:
        def convert(
            repeating: Repeating[
                DateTime[ZoneInfo],
                JSONableCallable,
                JSONableRepeating,
            ]
        ) -> JSONableCallable:
            return self.converterMethod(RepeatenceConverter(self, repeating))

        return Repeating(reference, rule, work, convert, scheduler)

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

    def repeatingFunction(self, cb: RepeatingWork) -> JSONableRepeating:
        return self._repeating.add(
            SerializableFunction(cb, getattr(cb, "__name__"))
        )

    def repeatingMethod(
        self, repeating: Callable[[JSONableSelf, int], None]
    ) -> JSONableRepeatingDescriptor[JSONableSelf, LoadContext]:
        wrapped = JSONableRepeatingDescriptor[JSONableSelf, LoadContext](
            self, repeating
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
    ) -> JSONableScheduler:
        """
        Load a JSON object in the format serialized from
        L{JSONSerializer.finalize} and a runtime L{TimeDriver}C{[float]},
        returning a L{Persistence}.
        """
        loadedID = 0
        new: JSONableScheduler = Scheduler(DateTimeDriver(runtimeDriver))
        for callJSON in serializedJSON["scheduledCalls"]:
            loadedID -= 1
            when = fromisoformat(callJSON["when"]).replace(
                tzinfo=ZoneInfo(callJSON["tz"])
            )
            what = self._loadOne(
                callJSON["what"], new, self._functions, loadContext
            )
            new.callAt(when, what)
        return new

    def save(self, scheduler: JSONableScheduler) -> JSONObject:
        # n.b.: `self` not used yet here because we're not validating that all
        # the serializable callables here are present in this specific
        # registry, but that would be a good check to have.
        return {
            "scheduledCalls": [
                {
                    "when": item.when.replace(tzinfo=None).isoformat(),
                    "tz": item.when.tzinfo.key,
                    "what": _whatJSON(item.what),
                    "called": item.called,
                    "canceled": item.canceled,
                }
                for item in scheduler.calls()
            ]
        }


@dataclass
class RepeatenceConverter(Generic[LoadContext]):
    jsonRegistry: JSONRegistry[LoadContext]
    repeating: Repeating[
        DateTime[ZoneInfo], JSONableCallable, JSONableRepeating
    ]

    @classmethod
    def typeCodeForJSON(self) -> str:
        return "repeatence"

    @classmethod
    def fromJSON(
        cls,
        registry: JSONRegistry[LoadContext],
        scheduler: JSONableScheduler,
        loadContext: LoadContext,
        json: JSONObject,
    ) -> RepeatenceConverter[LoadContext]:
        ruleFunction = {"daily": daily}[  # , "dailyWithSkips": dailyWithSkips
            json["rule"]
        ]
        what = json["callable"]

        def convertToMethod(
            it: Repeating[
                DateTime[ZoneInfo],
                JSONableCallable,
                JSONableRepeating,
            ]
        ) -> JSONableCallable:
            return registry.converterMethod(RepeatenceConverter(registry, it))

        return cls(
            registry,
            Repeating(
                fromisoformat(json["ts"]).replace(tzinfo=ZoneInfo(json["tz"])),
                ruleFunction,
                registry._loadOne(
                    what, scheduler, registry._repeating, loadContext
                ),
                convertToMethod,
                scheduler,
            ),
        )

    def asJSON(self) -> dict[str, object]:
        when = self.repeating.reference
        return {
            "ts": when.replace(tzinfo=None).isoformat(),
            "tz": when.tzinfo.key,
            "rule": {daily: "daily"}[self.repeating.rule],
            "callable": _whatJSON(self.repeating.callable),
            # "convert": is self, effectively
            # "scheduler": is what's doing the serializing
        }

    def repeatenceWrapper(self) -> None:
        self.repeating.repeat()

__all__ = [
    "JSONableScheduler",
    "JSONObject",
    "JSONRegistry",
]
