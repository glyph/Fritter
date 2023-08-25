# -*- test-case-name: fritter.test.test_json -*-
from __future__ import annotations

from dataclasses import dataclass, field
from typing import (
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

from ..boundaries import Cancellable, TimeDriver, RepeatingWork
from ..drivers.datetime import DateTimeDriver
from ..repeat import Repeater, RuleFunction, daily
from ..scheduler import Scheduler

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
    A callable that can be serialized as JSON.
    """

    def __call__(self) -> None:
        """
        Do the work of the callable.
        """


class JSONableRepeatable(JSONable, Protocol):
    def __call__(self, steps: int, stopper: Cancellable) -> None:
        """
        Do some repeatable work.
        """


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
class JSONableBoundRepeatable(Generic[JSONableSelf]):
    descriptor: JSONableRepeatableDescriptor[JSONableSelf, Any]
    instance: JSONableSelf

    def __call__(self, steps: int, stopper: Cancellable) -> None:
        self.descriptor.func(self.instance, steps, stopper)

    def asJSON(self) -> JSONObject:
        return self.instance.asJSON()

    def typeCodeForJSON(self) -> str:
        return (
            f"{self.instance.typeCodeForJSON()}."
            f"{self.descriptor.func.__name__}"
        )


@dataclass
class JSONableRepeatableDescriptor(Generic[JSONableSelf, LoadContext]):
    registry: JSONRegistry[LoadContext]
    func: Callable[[JSONableSelf, int, Cancellable], None]

    def __set_name__(
        self, cls: Type[JSONableInstance[LoadContext]], name: str
    ) -> None:
        self.registry.registerType(cls)

    def __get__(
        self, instance: JSONableSelf, owner: object = None
    ) -> JSONableBoundRepeatable[JSONableSelf]:
        return JSONableBoundRepeatable(self, instance)


class JSONableMethodBinder(Protocol[LoadContextInv]):
    def __call__(
        self,
        instance: RepeatableConverter[LoadContextInv],
        owner: object = None,
    ) -> JSONableBoundMethod[RepeatableConverter[LoadContextInv]]:
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


JSONRepeater = Repeater[
    DateTime[ZoneInfo], JSONableCallable, JSONableRepeatable
]


@dataclass
class JSONRegistry(Generic[LoadContext]):
    _functions: SpecificTypeRegistration[JSONableCallable] = field(
        default_factory=SpecificTypeRegistration
    )
    _repeatable: SpecificTypeRegistration[JSONableRepeatable] = field(
        default_factory=SpecificTypeRegistration
    )
    _instances: SpecificTypeRegistration[
        Type[JSONableInstance[LoadContext]]
    ] = field(default_factory=SpecificTypeRegistration)

    # Can't store the descriptor directly due to
    # https://github.com/python/mypy/issues/15822
    _converterMethod: JSONableMethodBinder[LoadContext] = field(init=False)

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
            # between both repeatable/non-repeatable types
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
        # RepeatableConverter[LoadContext]._performRepeat) breaks type
        # inference here so we need an explicit declaration, should report this
        # upstream.
        descriptor: JSONableMethodDescriptor[
            RepeatableConverter[LoadContext], LoadContext
        ] = self.asMethod(RepeatableConverter._performRepeat)
        # this is happening after the fact, not during a class definition, so
        # we need to take care of the __set_name__ step manually.
        descriptor.__set_name__(RepeatableConverter, "_performRepeat")
        self._converterMethod = descriptor.__get__

    def _repeaterConvert(
        self, repeater: JSONRepeater
    ) -> JSONableBoundMethod[RepeatableConverter[LoadContext]]:
        return self._converterMethod(RepeatableConverter(self, repeater))

    def repeatedly(
        self,
        scheduler: JSONableScheduler,
        rule: RuleFunction[DateTime[ZoneInfo]],
        work: JSONableRepeatable,
        reference: DateTime[ZoneInfo] | None = None,
    ) -> None:
        Repeater.new(
            scheduler,
            rule,
            work,
            self._repeaterConvert,
            reference,
        ).repeat()

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

    def repeatableFunction(self, cb: RepeatingWork) -> JSONableRepeatable:
        return self._repeatable.add(
            SerializableFunction(cb, getattr(cb, "__name__"))
        )

    def repeatableMethod(
        self, repeatable: Callable[[JSONableSelf, int, Cancellable], None]
    ) -> JSONableRepeatableDescriptor[JSONableSelf, LoadContext]:
        wrapped = JSONableRepeatableDescriptor[JSONableSelf, LoadContext](
            self, repeatable
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
        Load a JSON object in the format serialized from L{JSONRegistry.save}
        and a runtime L{TimeDriver}C{[float]}, returning a
        L{JSONableScheduler}.
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
class RepeatableConverter(Generic[LoadContext]):
    jsonRegistry: JSONRegistry[LoadContext]
    repeater: JSONRepeater

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
    ) -> RepeatableConverter[LoadContext]:
        rule = {"daily": daily}[  # , "dailyWithSkips": dailyWithSkips
            json["rule"]
        ]
        what = json["callable"]
        one = registry._loadOne(
            what, scheduler, registry._repeatable, loadContext
        )
        ref = fromisoformat(json["ts"]).replace(tzinfo=ZoneInfo(json["tz"]))
        rep = Repeater(scheduler, rule, one, registry._repeaterConvert, ref)
        return cls(registry, rep)

    def asJSON(self) -> dict[str, object]:
        when = self.repeater.reference
        return {
            "ts": when.replace(tzinfo=None).isoformat(),
            "tz": when.tzinfo.key,
            "rule": {daily: "daily"}[self.repeater.rule],
            "callable": _whatJSON(self.repeater.work),
            # "convert": is self, effectively
            # "scheduler": is what's doing the serializing
        }

    def _performRepeat(self) -> None:
        self.repeater.repeat()


__all__ = [
    "JSONableScheduler",
    "JSONObject",
    "JSONRegistry",
]
