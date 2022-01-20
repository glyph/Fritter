from typing import Any, Callable, Optional, Protocol, TypeVar


class PriorityComparable(Protocol):
    def __lt__(self, other: Any) -> bool:
        ...


T = TypeVar("T", bound=PriorityComparable)


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


class Driver(Protocol):
    def reschedule(self, newTime: float, work: Callable[[], None]) -> None:
        ...

    def unschedule(self):
        ...

    def currentTimestamp(self) -> float:
        ...
