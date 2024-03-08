"""
L{fritter.boundaries} describes the boundaries between different parts of the
system and its interface with your application code.  It contains L{Protocol}s,
L{TypeVar}s, and constant values, but no logic of its own.
"""

from __future__ import annotations

import sys
from enum import Enum, auto
from typing import (
    Any,
    Callable,
    Coroutine,
    Generator,
    Iterator,
    Optional,
    Protocol,
    TypeVar,
)
from zoneinfo import ZoneInfo

from datetype import DateTime

if sys.version_info >= (3, 12):
    from calendar import Day
else:
    from enum import IntEnum

    class Day(IntEnum):
        MONDAY = 0
        TUESDAY = 1
        WEDNESDAY = 2
        THURSDAY = 3
        FRIDAY = 4
        SATURDAY = 5
        SUNDAY = 6


class PriorityComparable(Protocol):
    """
    Protocol describing an object that can be compared for the purposes of a
    L{PriorityQueue}.
    """

    def __lt__(self, other: Any) -> bool:
        """
        Is C{self} lower priority than C{other}?
        """

    def __le__(self, other: Any) -> bool:
        """
        Is C{self} lower I{or} the same priority as C{other}?
        """


Prioritized = TypeVar("Prioritized", bound=PriorityComparable)
"""
A TypeVar for objects that can be compared for relative priority.
"""

Yield = TypeVar("Yield", covariant=True)
"""
Yield TypeVar for generators and coroutines.
"""
Send = TypeVar("Send", contravariant=True)
"""
Send TypeVar for generators and coroutines.
"""
Return = TypeVar("Return", covariant=True)
"""
Return TypeVar for generators and coroutines.
"""


class Cancellable(Protocol):
    """
    An object that can be cancelled.
    """

    def cancel(self) -> object:
        """
        Cancel an operation in progress.
        """


class CancellableAwaitable(Cancellable, Protocol[Yield, Send, Return]):
    """
    An object which can be both awaited and cancelled.
    """

    def __await__(self) -> Generator[Yield, Send, Return]:
        """
        This object may be awaited.
        """


AsyncType = TypeVar("AsyncType", bound=CancellableAwaitable[Any, Any, Any])
"TypeVar bound to a L{CancellableAwaitable}"


class PriorityQueue(Protocol[Prioritized]):
    """
    High-level specification of a priority queue.
    """

    def add(self, item: Prioritized) -> None:
        """
        Add an item to the priority queue.
        """

    def get(self) -> Optional[Prioritized]:
        """
        Consume the lowest item from the priority queue.
        """

    def peek(self) -> Optional[Prioritized]:
        """
        Examine the lowest item from the priority queue without modifying the
        queue.
        """

    def remove(self, item: Prioritized) -> bool:
        """
        Remove an item and return whether it was removed or not.
        """

    def __iter__(self) -> Iterator[Prioritized]:
        """
        Iterate all of the values in the priority queue, in an unspecified
        order.
        """


class TimeDriver(Protocol[Prioritized]):
    """
    Driver interface that allows Fritter to schedule objects onto a third party
    library.
    """

    def reschedule(
        self, newTime: Prioritized, work: Callable[[], None]
    ) -> None:
        """
        Schedule C{work} to occur at C{newTime}, removing any previous C{work}
        scheduled by prior calls to C{reschedule}.
        """

    def unschedule(self) -> None:
        """
        Remove any previously-scheduled C{work}.
        """

    def now(self) -> Prioritized:
        """
        Get the current time according to the underlying library.
        """


StepsT = TypeVar("StepsT", covariant=True)
"""
A type representing the record of steps that have passed in a recurrence rule.
"""
StepsTCon = TypeVar("StepsTCon", contravariant=True)
""" L{StepsT} (Contravariant) """
StepsTInv = TypeVar("StepsTInv")
""" L{StepsT} (Invariant) """

WhenT = TypeVar("WhenT", bound=PriorityComparable)
"""
TypeVar for representing a time at which something can occur; a temporal
coordinate in a timekeeping system.
"""
WhenTCo = TypeVar("WhenTCo", bound=PriorityComparable, covariant=True)
"L{WhenT} (Covariant)"
WhatT = TypeVar("WhatT", bound=Callable[[], None])
"""
TypeVar for representing a unit of work that can take place within the context
of a L{Scheduler}.
"""
WhatTCo = TypeVar("WhatTCo", bound=Callable[[], None], covariant=True)
"L{WhatT} (Covariant)"

IDT = TypeVar("IDT")
"""
TypeVar for representing the opaque identifier of ScheduledCall objects.
"""
IDTCo = TypeVar("IDTCo", covariant=True)
"L{IDT} (Covariant)"

CallTCo = TypeVar("CallTCo", bound=Cancellable, covariant=True)
"""
TypeVar for representing a cancelable call handle.
"""


class RepeatingWork(Protocol[StepsTCon]):
    """
    L{RepeatingWork} is work that can be performed repeatedly in a loop.
    """

    def __call__(self, steps: StepsTCon, scheduled: SomeScheduledCall) -> None:
        """
        Do the work that needs to be repeated.

        @param steps: The steps which have passed since the previous
            invocation.

        @param scheduled: The in-progress L{ScheduledCall} that you can call
            cancel() on to stop the repetition.
        """


class RecurrenceRule(Protocol[WhenT, StepsT]):
    """
    A L{RecurrenceRule} is a callable that takes a reference time and a current
    time, and computes series of steps between the current recurrence and a new
    reference time for the next call.

    Depending on the application, C{StepsT} type can either be an integer
    (i.e.: a count of the number of steps that have passed between the
    reference time and the current time) or a collection of specific previous
    step timestamps, usually a collection of C{WhenT}.
    """

    def __call__(
        self, reference: WhenT, current: WhenT
    ) -> tuple[StepsT, WhenT]:
        """
        Given a reference time and a current time, compute the steps between
        the calls and the next reference time.

        @param reference: the time at which the current invocation was
            I{scheduled} to occur; i.e. the time that the call was computed to
            have been called.

        @param current: the time at which the current invocation I{actually}
            occurred; i.e. the time that the event loop got around to actually
            calling the function.

        @note: The delta between the reference time and the current time will
            I{often} be quite small.  If a system is running actively and is
            not overloaded, then this delta will be close to zero.  However,
            there are cases (some examples: a laptop goes to sleep, then wakes
            up hours later; a program schedules a call in a database and is not
            run for several weeks) when this delta can be very large.

        @return: a 2-tuple of:

                1. I{steps}; the recurrences that were expected to have
                   occurred between C{reference} and the I{current time}.  So
                   for example, for a L{RecurrenceRule} representing a
                   once-every-5-seconds recurrence, if your reference time were
                   1.0 and your current time were 15.0, then your step count
                   should be 2, since recurrences should have occurred at 6.0
                   and 11.0.  Alternately, for a C{RecurrenceRule[float,
                   list[float]]} with the same scheduled times, C{steps} will
                   be C{[6.0, 11.0]}.

                2. I{next reference time}; time at which the next recurrence
                   I{should} occur.  In our previous example, where our
                   reference time was 1.0 and current time was 15.0, the next
                   desired time should be 16.0, since that's the next 5-second
                   recurrence after 11.0.
        """


class AsyncDriver(Protocol[AsyncType]):
    """
    An L{AsyncDriver} is an interface to a library that supports awaitables
    (such as the standard library L{asyncio}), to allow L{fritter.repeat.Async}
    to return an awaitable of a library-appropriate type.
    """

    def newWithCancel(self, cancel: Callable[[], None]) -> AsyncType:
        """
        Create a new future-ish object with the given callback to execute when
        it is cancelled.
        """

    def complete(self, asyncObj: AsyncType) -> None:
        """
        The asynchronous operation described by a previous call to this
        L{AsyncDriver}'s L{newWithCancel <AsyncDriver.newWithCancel>} method
        completed successfully; un-suspend any coroutine awaiting it.
        """

    def runAsync(self, coroutine: Coroutine[AsyncType, Any, Any]) -> AsyncType:
        """
        Run the given coroutine which awaits upon L{AsyncType}.

        @note: Whether this starts the given coroutine synchronously or waits
            until the next event-loop tick is implementation-defined.
        """


class ScheduledState(Enum):
    pending = auto()
    """
    The call is currently scheduled to be run at some point in the future.
    """

    called = auto()
    """
    The call was successfully invoked by the scheduler.
    """

    cancelled = auto()
    """
    The call was successfully invoked by the scheduler.
    """


class ScheduledCall(Cancellable, Protocol[WhenTCo, WhatTCo, IDTCo]):

    @property
    def id(self) -> IDTCo:
        """
        Return a unique identifier for this scheduled call.
        """

    @property
    def when(self) -> WhenTCo:
        """
        Return the original time at which the call will be scheduled.
        """

    @property
    def what(self) -> WhatTCo | None:
        """
        If this has not been called or cancelled, return the original callable
        that was scheduled.

        @note: To break cycles, this will only have a non-C{None} value when in
            L{ScheduledState.pending}.
        """

    @property
    def state(self) -> ScheduledState:
        """
        Is this call still waiting to be called, or has it been called or
        cancelled?
        """

    def cancel(self) -> None:
        """
        Cancel this L{ScheduledCall}, making it so that it will not be invoked
        in the future.  If the work described by C{when} has already been
        called, or this call has already been cancelled, do nothing.
        """


SomeScheduledCall = ScheduledCall[
    PriorityComparable, Callable[[], None], object
]


class Scheduler(Protocol[WhenT, WhatT, IDTCo]):
    """
    A L{Scheduler} is an object that allows for scheduling of timed calls.
    """

    def now(self) -> WhenT: ...

    def callAt(
        self, when: WhenT, what: WhatT
    ) -> ScheduledCall[WhenT, WhatT, IDTCo]: ...


PhysicalScheduler = Scheduler[float, Callable[[], None], object]
CivilScheduler = Scheduler[DateTime[ZoneInfo], Callable[[], None], object]

__all__ = [
    "AsyncDriver",
    "Cancellable",
    "CancellableAwaitable",
    "CivilScheduler",
    "Day",
    "PhysicalScheduler",
    "PriorityComparable",
    "PriorityQueue",
    "RecurrenceRule",
    "RepeatingWork",
    "ScheduledCall",
    "ScheduledState",
    "Scheduler",
    "SomeScheduledCall",
    "TimeDriver",
]
