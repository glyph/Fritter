"""
Implementation of L{PriorityQueue} in terms of the standard library's
L{heappop} and L{heappush} functions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from heapq import heappop, heappush
from typing import Generic, Iterator, List, Optional

from .boundaries import PriorityQueue, Prioritized


@dataclass
class Heap(Generic[Prioritized]):
    """
    A simple implementation of a priority queue using the standard library's
    L{heappop} and L{heappush} functions.
    """

    _values: List[Prioritized] = field(default_factory=list)

    def add(self, item: Prioritized) -> None:
        "Implementation of L{PriorityQueue.add}"
        heappush(self._values, item)

    def get(self) -> Optional[Prioritized]:
        "Implementation of  L{PriorityQueue.get}"
        if not self._values:
            return None
        return heappop(self._values)

    def peek(self) -> Optional[Prioritized]:
        "Implementation of L{PriorityQueue.peek}"
        if not self._values:
            return None
        return self._values[0]

    def remove(self, item: Prioritized) -> bool:
        "Implementation of L{PriorityQueue.remove}"
        try:
            self._values.remove(item)
        except ValueError:
            return False
        else:
            return True

    def __iter__(self) -> Iterator[Prioritized]:
        "Implementation of L{PriorityQueue.__iter__}"
        return iter(self._values)


_HeapIsQueue: type[PriorityQueue[int]] = Heap[int]
