"""
L{fritter.boundaries} describes the boundaries between different parts of the
system and its interface with your application code.  It contains L{Protocol}s,
L{TypeVar}s, and constant values, but no logic of its own.
"""

from __future__ import annotations
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


class CancellableAwaitable(Protocol[Yield, Send, Return]):
    """
    An object which can be both awaited and canceled.
    """

    def __await__(self) -> Generator[Yield, Send, Return]:
        """
        This object may be awaited.
        """

    def cancel(self) -> object:
        """
        This object may be canceled.
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


class Cancellable(Protocol):
    """
    An object that can be cancelled.
    """

    def cancel(self) -> object:
        """
        Cancel an operation in progress.
        """


class RepeatingWork(Protocol):
    """
    L{RepeatingWork} is work that can be performed repeatedly in a loop.
    """

    def __call__(self, steps: int, stopper: Cancellable) -> None:
        """
        Do the work.

        @param steps: The number of steps which have passed since the previous
            invocation.

        @param stopper: An object that you can call cancel() on to stop the
            repetition.
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
