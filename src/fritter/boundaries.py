from typing import Any, Callable, Optional, Protocol, TypeVar


class PriorityComparable(Protocol):
    def __lt__(self, other: Any) -> bool:
        ...

    def __le__(self, other: Any) -> bool:
        ...


T = TypeVar("T", bound=PriorityComparable)
T1 = TypeVar("T1", bound=PriorityComparable, contravariant=True)


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


class TimeDriver(Protocol[T]):
    def reschedule(self, newTime: T, work: Callable[[], None]) -> None:
        ...

    def unschedule(self) -> None:
        ...

    def currentTimestamp(self) -> T:
        ...


class RepeatingWork(Protocol):
    """
    The signature of work that is repeated in a loop.
    """

    def __call__(self, steps: int) -> None:
        """
        @param steps: The number of steps which have passed since the previous
            invocation.
        """


AsyncType = TypeVar("AsyncType")


class AsyncDriver(Protocol[AsyncType]):
    def newWithCancel(self, cancel: Callable[[], None]) -> AsyncType:
        """
        Create a new future-ish object with the given callback to execute when
        canceled.
        """

    def complete(self, asyncObj: AsyncType) -> None:
        "The asynchronous operation completed successfully."

    def unhandledError(
        self,
        applicationCode: RepeatingWork,
        inProgressObj: Optional[AsyncType],
    ) -> None:
        "called in an exception scope when"
