# -*- test-case-name: fritter.test.test_json -*-
"""
Serialize L{Scheduler} and the calls scheduled with it to JSON.

To use this module:

    - create a L{JSONRegistry} at module scope

    - decorate your functions and methods with L{JSONRegistry.function} and
      L{JSONRegistry.method}

    - implement L{JSONable.typeCodeForJSON}, L{JSONable.toJSON},
      L{JSONableInstance.fromJSON} as appropriate, until C{mypy} passes on your
      code

    - instantiate a L{JSONableScheduler} with an appropriate driver

    - schedule your functions and methods using it

    - save it with L{JSONRegistry.save}

    - load it later with L{JSONRegistry.load}
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import timedelta
from json import dump as save_json
from json import load as load_json
from pathlib import Path
from typing import (
    Any,
    Callable,
    Generic,
    Iterator,
    ParamSpec,
    Protocol,
    Type,
    TypeVar,
)
from zoneinfo import ZoneInfo

from datetype import DateTime, fromisoformat
from fritter.boundaries import StepsTCon
from fritter.heap import Heap

from ..boundaries import (
    Cancellable,
    RecurrenceRule,
    RepeatingWork,
    StepsT,
    StepsTInv,
    TimeDriver,
)
from ..drivers.datetime import DateTimeDriver
from ..repeat import Repeater
from ..repeat.rules.datetimes import EachYear, EveryDelta
from ..scheduler import FutureCall, Scheduler

LoadContext = TypeVar("LoadContext", contravariant=True)
LoadContextCo = TypeVar("LoadContextCo", covariant=True)
"""
Each L{JSONRegistry} has its own special object passed along to
L{JSONableInstance.fromJSON}, which can be any object.  This TypeVar describes
its type.
"""
LoadContextInv = TypeVar("LoadContextInv")
"""
Like L{LoadContext} but invariant.
"""
JSONObject = dict[str, Any]
"""
A loose description of a JSON-dumpable object.
"""
# TODO: tighten JSONObject up to accurately describe valid input to
# C{json.dumps}.


class HasTypeCode(Protocol):
    """
    The L{HasTypeCode} protocol describes an object with a C{typeCodeForJSON}
    method; this is used as a bound on other types such as L{JSONableCallable},
    L{JSONableRepeatable}, and L{JSONableInstance}.
    """

    def typeCodeForJSON(self) -> str:
        """
        Type-code for the serialized JSON object to be looked up later.
        """


class JSONable(HasTypeCode, Protocol[LoadContextCo]):
    """
    Methods that allow a L{JSONRegistry} to serialize an object as JSON.
    """

    def toJSON(self, registry: JSONRegistry[LoadContextCo]) -> JSONObject:
        """
        Convert this callable to a JSON-serializable dictionary.
        """


class JSONableCallable(JSONable[LoadContextCo], Protocol):
    """
    A callable that can be serialized as JSON.
    """

    def __call__(self) -> None:
        """
        Do the work of the callable.
        """


JSONableScheduler = Scheduler[
    DateTime[ZoneInfo], JSONableCallable[LoadContextInv]
]
"""
A JSONable scheduler is a L{Scheduler} which tracks time as a L{ZoneInfo}-aware
C{datetype.DateTime} and only accepts L{JSONableCallable} objects as work to be
performed, so that they can be serialized later.

@note: The type-checker can make sure that your callalbles are json-able, but
    they can't make sure that they're registered with the correct
    L{JSONRegistry}; mixing and matching different registries will be a runtime
    error.
"""
# TODO: datetype API docs?


class JSONableRepeatable(
    JSONable[LoadContextCo], RepeatingWork[StepsTCon], Protocol
):
    """
    A callable that can be serialized as JSON, with a signature that can be
    used for repeated calls with L{JSONRegistry.repeatedly}.
    """


class MissingPersistentCall(Exception):
    """
    A serialized persistent-call handle was missing.
    """


@dataclass
class LoadProcess(Generic[LoadContextInv]):
    """
    A L{LoadProcess} collects the parameters to one top-level call to
    L{JSONRegistry.load}.
    """

    registry: JSONRegistry[LoadContextInv]
    scheduler: JSONableScheduler[LoadContextInv]
    context: LoadContextInv

    def loadFutureCall(
        self, obj: Any
    ) -> FutureCall[DateTime[ZoneInfo], JSONableCallable[LoadContextInv]]:
        callID = obj["id"]
        for call in self.scheduler._q:
            if call.id == callID:
                return call
        raise MissingPersistentCall(callID)


class JSONableInstance(JSONable[LoadContextInv], Protocol):
    """
    A class that conforms to L{JSONableInstance} can be both serialized to and
    deserialized from JSON by a L{JSONRegistry}.  L{JSONableInstance}.
    """

    @classmethod
    def typeCodeForJSON(cls) -> str:
        """
        On a L{JSONableInstance}, the C{typeCodeForJSON} method must be a
        L{classmethod}, because the class needs to be registered for
        I{de}-serialization at class-definition time, before any instances
        exist.

        @see: L{HasTypeCode}
        """

    @classmethod
    def fromJSON(
        cls: Type[JSONableSelf],
        load: LoadProcess[LoadContextInv],
        json: JSONObject,
    ) -> JSONableSelf:
        """
        Load an instance of this type from the given deserialized JSON object,
        which should be in the format returned by an instance of this class's
        L{toJSON <JSONable.toJSON>} method.
        """


JSONableSelf = TypeVar(
    "JSONableSelf",
    bound=JSONableInstance[Any],
    # See comment in JSONRegistry.method about this bound.
)
"""
TypeVar for binding C{self} on methods that want to be serialized by
L{JSONRegistry.method}.
"""

_JSONableType = TypeVar("_JSONableType", bound=HasTypeCode)
"Binding for internal generic tracking of JSONable types."

JSONRepeater = Repeater[
    DateTime[ZoneInfo],
    JSONableCallable[LoadContext],
    StepsT,
]
"A L{Repeater} that is constrained to accept only JSON-serializable types."


def _whatJSON(
    registry: JSONRegistry[LoadContextInv], what: JSONable[LoadContextInv]
) -> JSONObject:
    """
    Convert a L{JSONable} into a standard JSON-serializable object format.
    """
    return {
        "type": what.typeCodeForJSON(),
        "data": what.toJSON(registry),
    }


SomeSignature = ParamSpec("SomeSignature")
"""
A description of the parameters passed to a serializable function.
"""


@dataclass
class SerializableFunction(Generic[LoadContext, SomeSignature]):
    """
    Wrapper around a function that conforms with L{JSONable}.
    """

    original: Callable[SomeSignature, object]
    typeCode: str

    def __call__(
        self, *args: SomeSignature.args, **kwargs: SomeSignature.kwargs
    ) -> None:
        """
        Delegate invocation to the wrapped callable.
        """
        self.original(*args, **kwargs)

    def typeCodeForJSON(self) -> str:
        """
        Return the static type code supplied at construction time.
        """
        return self.typeCode

    def toJSON(self, registry: JSONRegistry[LoadContext]) -> JSONObject:
        """
        Return an empty object.
        """
        return {}


@dataclass
class JSONableBoundMethod(Generic[JSONableSelf]):
    """
    A bound method that conforms to L{JSONable} and can be serialized and
    deserialized.

    @ivar descriptor: the descriptor that this bound method is binding, created
        by L{JSONRegistry.method}.

    @ivar instance: the instance that this bound method is bound to; a
        L{JSONableInstance} of some kind.
    """

    descriptor: JSONableMethodDescriptor[JSONableSelf, Any]
    instance: JSONableSelf

    def __call__(self) -> None:
        """
        Call this bound method's function with its instance as C{self}.
        """
        self.descriptor.func(self.instance)

    def toJSON(self, registry: JSONRegistry[LoadContext]) -> JSONObject:
        """
        Convert this method's instance to a JSON-dumpable dict.
        """
        return self.instance.toJSON(registry)

    def typeCodeForJSON(self) -> str:
        """
        Combine the bound method's name with its owning class's type code.
        """
        return (
            f"{self.instance.typeCodeForJSON()}."
            f"{self.descriptor.func.__name__}"
        )


__JC: Type[JSONableCallable[object]] = JSONableBoundMethod[
    JSONableInstance[object]
]


@dataclass
class JSONableMethodDescriptor(Generic[JSONableSelf, LoadContext]):
    """
    A descriptor that can bind methods into L{JSONableBoundMethod}s.

    @see: L{JSONRegistry.method}

    @ivar registry: The L{JSONRegistry} which created this descriptor.
    @ivar func: The callable underlying method function.
    """

    registry: JSONRegistry[LoadContext]
    func: Callable[[JSONableSelf], None]

    def __set_name__(
        self, cls: Type[JSONableInstance[LoadContext]], name: str
    ) -> None:
        """
        Register the class of the decorated method when the decorator is
        registered with the class, via the protocol of L{object.__set_name__}.
        """
        self.registry._registerJSONableType(cls)

    def __get__(
        self, instance: JSONableSelf, owner: object = None
    ) -> JSONableBoundMethod[JSONableSelf]:
        """
        Bind the decorated method to an instance.
        """
        return JSONableBoundMethod(self, instance)


@dataclass
class JSONableBoundRepeatable(Generic[JSONableSelf, LoadContext, StepsTInv]):
    """
    Like L{JSONableBoundMethod}, but for repeating calls.

    @ivar descriptor: the descriptor that this bound method is binding, created
        by L{JSONRegistry.repeatMethod}.

    @ivar instance: the instance that this bound method is bound to; a
        L{JSONableInstance} of some kind.
    """

    descriptor: JSONableRepeatableDescriptor[JSONableSelf, Any, StepsTInv]
    instance: JSONableSelf

    def __call__(self, steps: StepsTInv, stopper: Cancellable) -> None:
        """
        Call this bound method's function with its instance as C{self}.
        """
        self.descriptor.func(self.instance, steps, stopper)

    def toJSON(self, registry: JSONRegistry[LoadContext]) -> JSONObject:
        """
        Convert this method's instance to a JSON-dumpable dict.
        """
        return self.instance.toJSON(registry)

    def typeCodeForJSON(self) -> str:
        """
        Combine the bound method's name with its owning class's type code.
        """
        return (
            f"{self.instance.typeCodeForJSON()}."
            f"{self.descriptor.func.__name__}"
        )


@dataclass
class JSONableRepeatableDescriptor(Generic[JSONableSelf, LoadContext, StepsT]):
    """
    A descriptor that can bind methods into L{JSONableBoundRepeatable}s.

    @see: L{JSONRegistry.repeatMethod}

    @ivar registry: The L{JSONRegistry} which created this descriptor.
    @ivar func: The callable underlying method function.
    """

    registry: JSONRegistry[LoadContext]
    func: Callable[[JSONableSelf, StepsT, Cancellable], None]

    def __set_name__(
        self, cls: Type[JSONableInstance[LoadContext]], name: str
    ) -> None:
        """
        Register the class of the decorated method when the decorator is
        registered with the class, via the protocol of L{object.__set_name__}.
        """
        self.registry._registerJSONableType(cls)

    def __get__(
        self, instance: JSONableSelf, owner: object = None
    ) -> JSONableBoundRepeatable[JSONableSelf, LoadContext, StepsT]:
        """
        Bind the decorated method to an instance.
        """
        return JSONableBoundRepeatable(self, instance)


class _JSONableMethodBinder(Protocol[LoadContextInv, StepsTInv]):
    """
    Separated description of L{JSONableMethodDescriptor.__get__} that wraps
    L{_JSONableRepeaterWrapper.repeat} to work around U{this issue
    <https://github.com/python/mypy/issues/15822>}.
    """

    def __call__(
        self,
        instance: _JSONableRepeaterWrapper[LoadContextInv, StepsTInv],
        owner: object = None,
    ) -> JSONableBoundMethod[
        _JSONableRepeaterWrapper[LoadContextInv, StepsTInv]
    ]:
        """
        Bind the method.
        """


@dataclass
class _SpecificTypeRegistration(Generic[_JSONableType]):
    """
    General container for registering a specific kind of type (instances, plain
    callables, repeated callables).

    @ivar registered: The specific type registration.
    """

    registered: dict[str, _JSONableType] = field(default_factory=dict)

    def copy(self) -> _SpecificTypeRegistration[_JSONableType]:
        """
        Copy the given L{_SpecificTypeRegistration} to derive another from it.
        """
        return _SpecificTypeRegistration(self.registered.copy())

    def add(self, item: _JSONableType) -> _JSONableType:
        """
        Add the given type to the registry, keyed by its C{typeCodeForJSON}.
        """
        self.registered[item.typeCodeForJSON()] = item
        return item

    def get(self, typeCode: str) -> _JSONableType | None:
        """
        Get a type from the registry by the result of its C{typeCodeForJSON}
        classmethod, previously registered by L{_SpecificTypeRegistration.add}.
        """
        return self.registered.get(typeCode, None)


_universal: JSONRegistry[object]
"""
Create a registry for universally-serializable types.  Right now its only
member is L{_JSONableRepeaterWrapper}, to allow for its `repeat` method to
appear as serializable to all serializable schedulers.
"""


def _copyUniversal(
    name: str,
) -> Callable[[], _SpecificTypeRegistration[_JSONableType]]:
    """
    Derive a registry type registration from the universal registry type
    registration.
    """

    def _() -> _SpecificTypeRegistration[_JSONableType]:
        result: _SpecificTypeRegistration[_JSONableType] = getattr(
            _universal, name
        )
        return result.copy()

    return _


_JSONableCallableT = TypeVar(
    "_JSONableCallableT",
    bound=JSONableCallable[Any] | JSONableRepeatable[Any, Any],
)

RRuleT = TypeVar("RRuleT", bound=RecurrenceRule[DateTime[ZoneInfo], Any])
RRuleTx = TypeVar(
    "RRuleTx",
    bound=RecurrenceRule[DateTime[ZoneInfo], Any],
    contravariant=True,
)


class RuleJSONIfier(HasTypeCode, Protocol[RRuleT]):
    """
    External serializer for a recurrence rule.
    """

    def ruleFromJSON(self, json: JSONObject) -> RRuleT:
        """
        Construct a recurrence rule from the given JSON object.
        """

    def ruleAsJSON(self, rule: RRuleT) -> JSONObject:
        """
        Serialize the recurrence rule from the given JSON object.
        """


@dataclass
class JSONRegistry(Generic[LoadContext]):
    """
    A L{JSONRegistry} maintains a set of functions and methods (and the classes
    those methods are defined on) that can scheduled against a L{Scheduler} and
    then persisted into a JSON blob to reconstitute that scheduler later.

    Use a L{JSONRegistry} by instantiatint it at module scope and then using
    its methods as decorators on functions and methods.
    """

    # TODO: implement merging multiple registries together so that objects from
    # different libraries can live in the same blob
    _functions: _SpecificTypeRegistration[JSONableCallable[LoadContext]] = (
        field(default_factory=_copyUniversal("_functions"))
    )
    _repeatable: _SpecificTypeRegistration[
        JSONableRepeatable[LoadContext, Any]
    ] = field(default_factory=_copyUniversal("_repeatable"))
    _instances: _SpecificTypeRegistration[
        Type[JSONableInstance[LoadContext]]
    ] = field(default_factory=_copyUniversal("_instances"))
    _rules: _SpecificTypeRegistration[
        RuleJSONIfier[RecurrenceRule[DateTime[ZoneInfo], Any]]
    ] = field(default_factory=_copyUniversal("_rules"))
    _ruletype2jsonifier: dict[
        type[RecurrenceRule[DateTime[ZoneInfo], object]],
        RuleJSONIfier[RecurrenceRule[DateTime[ZoneInfo], Any]],
    ] = field(default_factory=lambda: _universal._ruletype2jsonifier.copy())

    def _loadRRule(
        self, json: JSONObject
    ) -> RecurrenceRule[DateTime[ZoneInfo], Any]:
        typeCode = json["type"]
        blob = json["data"]

        if (it := self._rules.get(typeCode)) is not None:
            return it.ruleFromJSON(blob)

        raise KeyError(f"cannot interpret rule type code {repr(typeCode)}")

    def _saveRRule(
        self, rule: RecurrenceRule[DateTime[ZoneInfo], Any]
    ) -> JSONObject:
        ser = self._ruletype2jsonifier[type(rule)]
        return {
            "type": ser.typeCodeForJSON(),
            "data": ser.ruleAsJSON(rule),
        }

    def _registerRRule(
        self,
        ruleType: Type[RRuleTx],
        serializer: RuleJSONIfier[RRuleTx],
    ) -> None:
        # TODO: there's a variance problem here, I think?
        self._rules.add(serializer)  # type:ignore[arg-type]
        self._ruletype2jsonifier[ruleType] = (
            serializer  # type:ignore[assignment]
        )

    def _loadOne(
        self,
        json: JSONObject,
        which: _SpecificTypeRegistration[_JSONableCallableT],
        load: LoadProcess[LoadContext],
    ) -> _JSONableCallableT:
        """
        Convert the given JSON-dumpable dict into an object of C{_JSONableType}
        via its L{JSONableInstance.fromJSON} classmethod registered in the
        given L{_SpecificTypeRegistration}.
        """
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

            instance = instanceType.fromJSON(load, blob)
            result: _JSONableCallableT = getattr(instance, methodName)
            return result

        # TODO: this is for *long-term* storage of sets of scheduled events, so
        # failing the entire load like this is probably not always an
        # acceptable failure mode.  We should identify any calls that failed to
        # load, remember their uninterpreted blobs to be included again in
        # save() so we don't lose them, then communicate the failure to an
        # object passed to .load()

        raise KeyError(f"cannot interpret type code {repr(typeCode)}")

    def _repeaterToJSONable(
        self, repeater: JSONRepeater[LoadContext, StepsT]
    ) -> JSONableBoundMethod[_JSONableRepeaterWrapper[LoadContext, StepsT]]:
        """
        Convert the given L{JSONRepeater} into a method that can be serialized.
        """
        return _JSONableRepeaterWrapper(self, repeater).repeat

    def repeatedly(
        self,
        scheduler: JSONableScheduler[LoadContext],
        rule: RecurrenceRule[DateTime[ZoneInfo], StepsT],
        work: JSONableRepeatable[LoadContext, StepsT],
        reference: DateTime[ZoneInfo] | None = None,
    ) -> None:
        """
        Call C{work} repeatedly, according to C{rule}, with intervals computed
        according to the given C{reference} time (or C{scheduler}'s current
        time, if not given).

        If you want to stop the repetition, C{work} is passed a L{Cancellable}
        that you can call C{.cancel()} on to do so.

        @see: L{fritter.repeat}
        """
        Repeater.new(
            scheduler, rule, work, self._repeaterToJSONable, reference
        ).repeat()

    def function(
        self, cb: Callable[[], None]
    ) -> JSONableCallable[LoadContext]:
        """
        Mark the given 0-argument, None-returning, top-level function as
        possible to serialize within this registry.  It will be serialized by
        its fully-qualified Python name.

        Use like so::

            registry = JSONRegistry[...]()

            @registry.serializedFunction
        """
        func: JSONableCallable[LoadContext] = SerializableFunction(
            cb, cb.__qualname__
        )
        return self._functions.add(func)

    def method(
        self, method: Callable[[JSONableSelf], None]
    ) -> JSONableMethodDescriptor[JSONableSelf, LoadContext]:
        """
        Mark the given method, defined at class scope in a class complying with
        the L{JSONableInstance} protocol, as possible to serialize within this
        registry.
        """
        # I want to stipulate that the method I am taking here must have a
        # 'self' parameter whose type is *at least* as strict as
        # JSONableInstance[LoadContext] but may be stricter than that.
        # However, this would require higher-kinded typevars, in order to make
        # JSONableSelf bounded by JSONableInstance[LoadContext] rather than
        # JSONableInstance[Any]: https://github.com/python/typing/issues/548
        return JSONableMethodDescriptor(self, method)

    def repeatFunction(
        self, cb: RepeatingWork[StepsT]
    ) -> JSONableRepeatable[LoadContext, StepsT]:
        """
        Mark the given function that matches the signature of L{RepeatingWork},
        i.e. one which takes a number of steps and a L{Cancellable} to cancel
        its own repetition, as looked up via its C{__qualname__} attribute.

        @return: a function that mimics the signature of the original function,
            but also conforms to the L{JSONable} protocol.
        """
        func: JSONableRepeatable[LoadContext, StepsT] = SerializableFunction(
            cb, getattr(cb, "__qualname__")
        )
        return self._repeatable.add(func)

    def repeatMethod(
        self, repeatable: Callable[[JSONableSelf, StepsT, Cancellable], None]
    ) -> JSONableRepeatableDescriptor[JSONableSelf, LoadContext, StepsT]:
        """
        Mark the given method that matches the signature of L{RepeatingWork},
        i.e. one which takes a number of steps and a L{Cancellable} to cancel
        its own repetition, as looked up via its C{__qualname__} attribute.

        @note: The registration occurs when the class is defined, specifically
            in the C{__set_name__} hook in the returned descriptor, so if you
            are calling this in an esoteric context outside a normal class
            definition, be sure to invoke that hook as well.

        @return: a descriptor that mimics the signature of the original method.
        """
        return JSONableRepeatableDescriptor(self, repeatable)

    def _registerJSONableType(
        self, cls: Type[JSONableInstance[LoadContext]]
    ) -> None:
        """
        Mark the given class as serializable via this registry, keyed by its
        L{JSONable.typeCodeForJSON} method.  Used internally as supporting
        L{JSONRegistry.method} and L{JSONRegistry.repeatMethod}.
        """
        self._instances.add(cls)

    def load(
        self,
        runtimeDriver: TimeDriver[float],
        serializedJSON: JSONObject,
        loadContext: LoadContext,
    ) -> tuple[JSONableScheduler[LoadContext], Callable[[], JSONObject]]:
        """
        Load a JSON object in the format serialized from L{JSONRegistry.save}
        and a runtime L{TimeDriver}C{[float]}, returning a
        L{JSONableScheduler}.
        """
        h: Heap[
            FutureCall[DateTime[ZoneInfo], JSONableCallable[LoadContext]]
        ] = Heap()
        new: JSONableScheduler[LoadContext] = Scheduler(
            DateTimeDriver(runtimeDriver),
            h,
            counter=int(serializedJSON.get("counter", "0")),
        )
        load = LoadProcess(self, new, loadContext)
        loads = []
        for callJSON in serializedJSON["scheduledCalls"]:
            when = fromisoformat(callJSON["when"]).replace(
                tzinfo=ZoneInfo(callJSON["tz"])
            )

            # Establish the FutureCall to allow for circular reference to its
            # 'what', with a fake callable.
            fakeWhat: JSONableCallable[LoadContext]
            fakeWhat = None  # type:ignore[assignment]

            placeholder = new.callAt(when, fakeWhat)
            placeholder.id = callJSON["id"]

            loads.append((placeholder, callJSON["what"]))
            # callAt needs a way to communicate future call counters (IDs)

        for ph, wt in loads:
            ph.what = self._loadOne(wt, self._functions, load)
        return new, self._saverFor(h, new)

    def new(
        self, driver: TimeDriver[DateTime[ZoneInfo]]
    ) -> tuple[JSONableScheduler[LoadContext], Callable[[], JSONObject]]:
        """
        Create a new L{JSONableScheduler} with the same type as if it had been
        loaded by this L{JSONRegistry}.
        """
        h: Heap[
            FutureCall[DateTime[ZoneInfo], JSONableCallable[LoadContext]]
        ] = Heap()
        s = Scheduler(driver, h)
        return s, self._saverFor(h, s)

    def saveFutureCall(
        self,
        futureCall: FutureCall[
            DateTime[ZoneInfo], JSONableCallable[LoadContextInv]
        ],
    ) -> dict[str, object]:
        """
        Convert a L{FutureCall} into a JSON-serializable object.
        """
        return {"id": futureCall.id}

    def _saverFor(
        self,
        h: Heap[FutureCall[DateTime[ZoneInfo], JSONableCallable[LoadContext]]],
        s: JSONableScheduler[LoadContext],
    ) -> Callable[[], JSONObject]:
        def save() -> JSONObject:
            """
            Serialize the given L{JSONableScheduler} to a single L{JSONObject}
            which can be passed to L{json.dumps} or L{json.loads}.
            """
            # TODO: `self` not used yet here because we're not validating that
            # all the serializable callables here are present in this specific
            # registry, but that would be a good check to have.
            return {
                "scheduledCalls": [
                    {
                        "when": item.when.replace(tzinfo=None).isoformat(),
                        "tz": item.when.tzinfo.key,
                        "what": _whatJSON(self, item.what),
                        "called": item.called,
                        "canceled": item.canceled,
                        "id": item.id,
                    }
                    for item in h
                ],
                "counter": str(s.counter),
            }

        return save


_universal = JSONRegistry(
    _SpecificTypeRegistration(),
    _SpecificTypeRegistration(),
    _SpecificTypeRegistration(),
    _SpecificTypeRegistration(),
    {},
)


class _EveryDeltaJSONifier:
    def typeCodeForJSON(self) -> str:
        return "fritter:fixed-delta"

    def ruleFromJSON(self, json: JSONObject) -> EveryDelta:
        return EveryDelta(timedelta(*json["delta"]))

    def ruleAsJSON(self, rule: EveryDelta) -> JSONObject:
        return {"delta": rule.delta.__reduce__()[1]}


class _YearlyJSONifier:
    def typeCodeForJSON(self) -> str:
        return "fritter:yearly"

    def ruleFromJSON(self, json: JSONObject) -> EachYear:
        return EachYear(json["years"])

    def ruleAsJSON(self, rule: EachYear) -> JSONObject:
        return {"years": rule.years}


_universal._registerRRule(EveryDelta, _EveryDeltaJSONifier())
_universal._registerRRule(EachYear, _YearlyJSONifier())


def dateTypeAsJSON(dt: DateTime[ZoneInfo]) -> dict[str, str]:
    return {
        "ts": dt.replace(tzinfo=None).isoformat(),
        "tz": dt.tzinfo.key,
    }


def dateTypeFromJSON(dtjs: dict[str, str]) -> DateTime[ZoneInfo]:
    return fromisoformat(dtjs["ts"]).replace(tzinfo=ZoneInfo(dtjs["tz"]))


@dataclass
class _JSONableRepeaterWrapper(Generic[LoadContext, StepsT]):
    """
    Since a L{Scheduler} can only contain C{work} of a given type, which must
    have a 0-argument, C{None}-returning signature, and L{JSONRegistry.save}
    serializes its scheduler by enumerating its future calls, this is a wrapper
    with a special method registered with I{all} L{JSONRegistry}s
    automatically, to provide a JSON-serialization format for a repeated call
    with the repeat-call signature (i.e., C{(steps, stopper)}).

    @see: L{fritter.repeat}

    @ivar jsonRegistry: The specific L{JSONRegistry} to which this
        repeater-wrapper is bound.

    @ivar repeater: The L{JSONable} repeating call that can itself be
        serialized.
    """

    jsonRegistry: JSONRegistry[LoadContext]
    repeater: JSONRepeater[LoadContext, StepsT]

    @classmethod
    def typeCodeForJSON(cls) -> str:
        """
        Return a unique type code (C{"fritter:repetition"}) for this wrapper.
        """
        return "fritter:repetition"

    @classmethod
    def fromJSON(
        cls,
        load: LoadProcess[LoadContext],
        json: JSONObject,
    ) -> _JSONableRepeaterWrapper[LoadContext, StepsT]:
        """
        Deserialize a L{_JSONableRepeaterWrapper} from a JSON-dumpable dict
        previously produced by L{_JSONableRepeaterWrapper.toJSON}.
        """
        rule: RecurrenceRule[DateTime[ZoneInfo], StepsT] = (
            load.registry._loadRRule(json["rule"])
        )
        what = json["callable"]
        one = load.registry._loadOne(what, load.registry._repeatable, load)
        ref = dateTypeFromJSON(json)
        rep = Repeater(
            load.scheduler, rule, one, load.registry._repeaterToJSONable, ref
        )
        return cls(load.registry, rep)

    def toJSON(self, registry: JSONRegistry[object]) -> JSONObject:
        """
        Serialize this L{_JSONableRepeaterWrapper} to a JSON-dumpable dict
        suitable for deserialization with L{_JSONableRepeaterWrapper.fromJSON},
        including its time, IANA timezone identifier, rule function, and
        underlying repeating callable.
        """
        # because StepsT is parameterizable in Repeater.work, we can't make
        # Repeater.work itself be a TypeVar.
        work: JSONable[object] = self.repeater.work  # type:ignore[assignment]
        return {
            "rule": registry._saveRRule(self.repeater.rule),
            "callable": _whatJSON(registry, work),
            # "convert": is implicitly L{registry._repeaterToJSONable}
            # "scheduler": is what's doing the serializing
            **dateTypeAsJSON(self.repeater.reference),
        }

    @_universal.method
    def repeat(self) -> None:
        """
        This C{repeat} method is what is actually serialized, using the
        bound-method support in L{JSONRegistry}.  Internally, it is implicitly
        decorated with each registry's L{JSONRegistry.method} decorator.
        """
        self.repeater.repeat()


@contextmanager
def schedulerAtPath(
    registry: JSONRegistry[LoadContext],
    driver: TimeDriver[float],
    path: Path,
    context: LoadContext,
) -> Iterator[JSONableScheduler[LoadContext]]:
    if path.exists():
        with path.open() as rf:
            scheduler, saver = registry.load(driver, load_json(rf), context)
    else:
        scheduler, saver = registry.new(DateTimeDriver(driver))
    yield scheduler
    with path.open("w") as wf:
        save_json(saver(), wf)


__all__ = [
    "JSONableScheduler",
    "JSONObject",
    "JSONRegistry",
    "JSONableRepeatable",
    "schedulerAtPath",
    "dateTypeAsJSON",
    "dateTypeFromJSON",
]
