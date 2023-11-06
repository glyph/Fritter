# -*- test-case-name: fritter.test.test_json -*-
"""
Serialize L{Scheduler} and the calls scheduled with it to JSON.

To use this module:

    - create a L{JSONRegistry} at module scope

    - decorate your functions and methods with L{JSONRegistry.function} and
      L{JSONRegistry.method}

    - implement L{JSONable.typeCodeForJSON}, L{JSONable.asJSON},
      L{JSONableInstance.fromJSON} as appropriate, until C{mypy} passes on your
      code

    - instantiate a L{JSONableScheduler} with an appropriate driver

    - schedule your functions and methods using it

    - save it with L{JSONRegistry.save}

    - load it later with L{JSONRegistry.load}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Callable, Generic, ParamSpec, Protocol, Type, TypeVar
from zoneinfo import ZoneInfo

from datetype import DateTime, fromisoformat
from fritter.repeat import EveryDelta

from ..boundaries import Cancellable, RepeatingWork, TimeDriver
from ..drivers.datetime import DateTimeDriver
from ..repeat import RecurrenceRule, Repeater
from ..scheduler import Scheduler

LoadContext = TypeVar("LoadContext", contravariant=True)
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


class JSONable(HasTypeCode, Protocol):
    """
    Methods that allow a L{JSONRegistry} to serialize an object as JSON.
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


JSONableScheduler = Scheduler[DateTime[ZoneInfo], JSONableCallable]
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


class JSONableRepeatable(JSONable, RepeatingWork, Protocol):
    """
    A callable that can be serialized as JSON, with a signature that can be
    used for repeated calls with L{JSONRegistry.repeatedly}.
    """


class JSONableInstance(JSONable, Protocol[LoadContextInv]):
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
        registry: JSONRegistry[LoadContextInv],
        scheduler: JSONableScheduler,
        loadContext: LoadContextInv,
        json: JSONObject,
    ) -> JSONableSelf:
        """
        Load an instance of this type from the given deserialized JSON object,
        which should be in the format returned by an instance of this class's
        L{asJSON <JSONable.asJSON>} method.
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
    DateTime[ZoneInfo], JSONableCallable, JSONableRepeatable
]
"A L{Repeater} that is constrained to accept only JSON-serializable types."


def _whatJSON(what: JSONable) -> JSONObject:
    """
    Convert a L{JSONable} into a standard JSON-serializable object format.
    """
    return {
        "type": what.typeCodeForJSON(),
        "data": what.asJSON(),
    }


SomeSignature = ParamSpec("SomeSignature")
"""
A description of the parameters passed to a serializable function.
"""


@dataclass
class SerializableFunction(Generic[SomeSignature]):
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

    def asJSON(self) -> JSONObject:
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

    def asJSON(self) -> JSONObject:
        """
        Convert this method's instance to a JSON-dumpable dict.
        """
        return self.instance.asJSON()

    def typeCodeForJSON(self) -> str:
        """
        Combine the bound method's name with its owning class's type code.
        """
        return (
            f"{self.instance.typeCodeForJSON()}."
            f"{self.descriptor.func.__name__}"
        )


__JC: Type[JSONableCallable] = JSONableBoundMethod


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
class JSONableBoundRepeatable(Generic[JSONableSelf]):
    """
    Like L{JSONableBoundMethod}, but for repeating calls.

    @ivar descriptor: the descriptor that this bound method is binding, created
        by L{JSONRegistry.repeatMethod}.

    @ivar instance: the instance that this bound method is bound to; a
        L{JSONableInstance} of some kind.
    """

    descriptor: JSONableRepeatableDescriptor[JSONableSelf, Any]
    instance: JSONableSelf

    def __call__(self, steps: int, stopper: Cancellable) -> None:
        """
        Call this bound method's function with its instance as C{self}.
        """
        self.descriptor.func(self.instance, steps, stopper)

    def asJSON(self) -> JSONObject:
        """
        Convert this method's instance to a JSON-dumpable dict.
        """
        return self.instance.asJSON()

    def typeCodeForJSON(self) -> str:
        """
        Combine the bound method's name with its owning class's type code.
        """
        return (
            f"{self.instance.typeCodeForJSON()}."
            f"{self.descriptor.func.__name__}"
        )


@dataclass
class JSONableRepeatableDescriptor(Generic[JSONableSelf, LoadContext]):
    """
    A descriptor that can bind methods into L{JSONableBoundRepeatable}s.

    @see: L{JSONRegistry.repeatMethod}

    @ivar registry: The L{JSONRegistry} which created this descriptor.
    @ivar func: The callable underlying method function.
    """

    registry: JSONRegistry[LoadContext]
    func: Callable[[JSONableSelf, int, Cancellable], None]

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
    ) -> JSONableBoundRepeatable[JSONableSelf]:
        """
        Bind the decorated method to an instance.
        """
        return JSONableBoundRepeatable(self, instance)


class _JSONableMethodBinder(Protocol[LoadContextInv]):
    """
    Separated description of L{JSONableMethodDescriptor.__get__} that wraps
    L{_JSONableRepeaterWrapper.repeat} to work around U{this issue
    <https://github.com/python/mypy/issues/15822>}.
    """

    def __call__(
        self,
        instance: _JSONableRepeaterWrapper[LoadContextInv],
        owner: object = None,
    ) -> JSONableBoundMethod[_JSONableRepeaterWrapper[LoadContextInv]]:
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
    _functions: _SpecificTypeRegistration[JSONableCallable] = field(
        default_factory=_copyUniversal("_functions")
    )
    _repeatable: _SpecificTypeRegistration[JSONableRepeatable] = field(
        default_factory=_copyUniversal("_repeatable")
    )
    _instances: _SpecificTypeRegistration[
        Type[JSONableInstance[LoadContext]]
    ] = field(default_factory=_copyUniversal("_instances"))

    def _loadOne(
        self,
        json: JSONObject,
        scheduler: JSONableScheduler,
        which: _SpecificTypeRegistration[_JSONableType],
        ctx: LoadContext,
    ) -> _JSONableType:
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

            instance = instanceType.fromJSON(self, scheduler, ctx, blob)
            result: _JSONableType = getattr(instance, methodName)
            return result

        # TODO: this is for *long-term* storage of sets of scheduled events, so
        # failing the entire load like this is probably not always an
        # acceptable failure mode.  We should identify any calls that failed to
        # load, remember their uninterpreted blobs to be included again in
        # save() so we don't lose them, then communicate the failure to an
        # object passed to .load()

        raise KeyError(f"cannot interpret type code {repr(typeCode)}")

    def _repeaterToJSONable(
        self, repeater: JSONRepeater
    ) -> JSONableBoundMethod[_JSONableRepeaterWrapper[LoadContext]]:
        """
        Convert the given L{JSONRepeater} into a method that can be serialized.
        """
        return _JSONableRepeaterWrapper(self, repeater).repeat

    def repeatedly(
        self,
        scheduler: JSONableScheduler,
        rule: RecurrenceRule[DateTime[ZoneInfo]],
        work: JSONableRepeatable,
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

    def function(self, cb: Callable[[], None]) -> JSONableCallable:
        """
        Mark the given 0-argument, None-returning, top-level function as
        possible to serialize within this registry.  It will be serialized by
        its fully-qualified Python name.

        Use like so::

            registry = JSONRegistry[...]()

            @registry.serializedFunction
        """
        return self._functions.add(SerializableFunction(cb, cb.__qualname__))

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

    def repeatFunction(self, cb: RepeatingWork) -> JSONableRepeatable:
        """
        Mark the given function that matches the signature of L{RepeatingWork},
        i.e. one which takes a number of steps and a L{Cancellable} to cancel
        its own repetition, as looked up via its C{__qualname__} attribute.

        @return: a function that mimics the signature of the original function,
            but also conforms to the L{JSONable} protocol.
        """
        return self._repeatable.add(
            SerializableFunction(cb, getattr(cb, "__qualname__"))
        )

    def repeatMethod(
        self, repeatable: Callable[[JSONableSelf, int, Cancellable], None]
    ) -> JSONableRepeatableDescriptor[JSONableSelf, LoadContext]:
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
    ) -> JSONableScheduler:
        """
        Load a JSON object in the format serialized from L{JSONRegistry.save}
        and a runtime L{TimeDriver}C{[float]}, returning a
        L{JSONableScheduler}.
        """
        new: JSONableScheduler = Scheduler(
            DateTimeDriver(runtimeDriver),
            counter=int(serializedJSON.get("counter", "0")),
        )
        for callJSON in serializedJSON["scheduledCalls"]:
            when = fromisoformat(callJSON["when"]).replace(
                tzinfo=ZoneInfo(callJSON["tz"])
            )
            what = self._loadOne(
                callJSON["what"], new, self._functions, loadContext
            )
            new.callAt(when, what)
        return new

    def save(self, scheduler: JSONableScheduler) -> JSONObject:
        """
        Serialize the given L{JSONableScheduler} to a single L{JSONObject}
        which can be passed to L{json.dumps} or L{json.loads}.
        """
        # TODO: `self` not used yet here because we're not validating that all
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
            ],
            "counter": str(scheduler.counter),
        }


_universal = JSONRegistry(
    _SpecificTypeRegistration(),
    _SpecificTypeRegistration(),
    _SpecificTypeRegistration(),
)


@dataclass
class _JSONableRepeaterWrapper(Generic[LoadContext]):
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
    repeater: JSONRepeater

    @classmethod
    def typeCodeForJSON(cls) -> str:
        """
        Return a unique type code (C{"fritter:repetition"}) for this wrapper.
        """
        return "fritter:repetition"

    @classmethod
    def fromJSON(
        cls,
        registry: JSONRegistry[LoadContext],
        scheduler: JSONableScheduler,
        loadContext: LoadContext,
        json: JSONObject,
    ) -> _JSONableRepeaterWrapper[LoadContext]:
        """
        Deserialize a L{_JSONableRepeaterWrapper} from a JSON-dumpable dict
        previously produced by L{_JSONableRepeaterWrapper.asJSON}.
        """
        rule = cls._loadRule(json["rule"])
        what = json["callable"]
        one = registry._loadOne(
            what, scheduler, registry._repeatable, loadContext
        )
        ref = fromisoformat(json["ts"]).replace(tzinfo=ZoneInfo(json["tz"]))
        rep = Repeater(scheduler, rule, one, registry._repeaterToJSONable, ref)
        return cls(registry, rep)

    def _saveRule(self, rule: object) -> object:
        assert isinstance(
            rule, EveryDelta
        ), "Only EveryDelta instances supported so far"
        result: object = rule.delta.__reduce__()[1]
        return result

    @classmethod
    def _loadRule(cls, rule: list[int]) -> EveryDelta:
        return EveryDelta(timedelta(*rule))

    def asJSON(self) -> JSONObject:
        """
        Serialize this L{_JSONableRepeaterWrapper} to a JSON-dumpable dict
        suitable for deserialization with L{_JSONableRepeaterWrapper.fromJSON},
        including its time, IANA timezone identifier, rule function, and
        underlying repeating callable.
        """
        when = self.repeater.reference
        return {
            "ts": when.replace(tzinfo=None).isoformat(),
            "tz": when.tzinfo.key,
            "rule": self._saveRule(self.repeater.rule),
            # TODO: this si just a demo.
            "callable": _whatJSON(self.repeater.work),
            # "convert": is implicitly L{registry._repeaterToJSONable}
            # "scheduler": is what's doing the serializing
        }

    @_universal.method
    def repeat(self) -> None:
        """
        This C{repeat} method is what is actually serialized, using the
        bound-method support in L{JSONRegistry}.  Internally, it is implicitly
        decorated with each registry's L{JSONRegistry.method} decorator.
        """
        self.repeater.repeat()


__all__ = [
    "JSONableScheduler",
    "JSONObject",
    "JSONRegistry",
]
