from typing import (
    Any,
    Awaitable,
    Callable,
    Coroutine,
    Generator,
    Iterator,
    Optional,
    Protocol,
    TypeVar,
)


class PriorityComparable(Protocol):
    def __lt__(self, other: Any) -> bool:
        ...

    def __le__(self, other: Any) -> bool:
        ...


T = TypeVar("T", bound=PriorityComparable)
T1 = TypeVar("T1", bound=PriorityComparable, contravariant=True)

Yield = TypeVar("Yield", covariant=True)
Send = TypeVar("Send", contravariant=True)
Return = TypeVar("Return", covariant=True)


class Awaitish(Protocol[Yield, Send, Return]):
    def __await__(self) -> Generator[Yield, Send, Return]:
        ...

    def cancel(self) -> object:
        ...


AsyncType = TypeVar("AsyncType", bound=Awaitish[Any, Any, Any])


class PriorityQueue(Protocol[T]):
    """
    High-level specification of a priority queue.
    """

    def add(self, item: T) -> None:
        """
        Add an item to the priority queue.
        """

    def get(self) -> Optional[T]:
        """
        Consume the lowest item from the priority queue.
        """

    def peek(self) -> Optional[T]:
        """
        Examine the lowest item from the priority queue.
        """

    def remove(self, item: T) -> bool:
        """
        Remove an item and return whether it was removed or not.
        """

    def __iter__(self) -> Iterator[T]:
        """
        Iterate all of the values in the priority queue, in an unspecified
        order.
        """


class TimeDriver(Protocol[T]):
    def reschedule(self, newTime: T, work: Callable[[], None]) -> None:
        ...

    def unschedule(self) -> None:
        ...

    def now(self) -> T:
        ...


class Cancellable(Protocol):
    def cancel(self) -> object:
        """
        Cancel an operation in progress.
        """


class RepeatingWork(Protocol):
    """
    The signature of work that is repeated in a loop.
    """

    def __call__(self, steps: int, stopper: Cancellable) -> None:
        """
        @param steps: The number of steps which have passed since the previous
            invocation.

        @param stopper: An object that you can call cancel() on to stop the
            repetition.
        """


class AsyncDriver(Protocol[AsyncType]):
    def newWithCancel(self, cancel: Callable[[], None]) -> AsyncType:
        """
        Create a new future-ish object with the given callback to execute when
        canceled.
        """

    def complete(self, asyncObj: AsyncType) -> None:
        """
        The asynchronous operation completed successfully.
        """

    def runAsync(
        self, coroutine: Coroutine[AsyncType, Any, Any]
    ) -> Cancellable:
        """
        Run the given coroutine.
        """


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # ancillary explicit type checks
    from asyncio import Future

    from twisted.internet.defer import Deferred

    fill: Any = object
    f: Future[None] = fill
    d: Deferred[None] = fill
    awt: Awaitish[Any, Any, Any] = f

    async def what() -> None:
        ...

    awt = d
    c: Cancellable = d
