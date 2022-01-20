from dataclasses import dataclass, field
from heapq import heappop, heappush
from typing import Generic, List, Optional

from .boundaries import T


@dataclass
class HeapPriorityQueue(Generic[T]):
    _values: List[T] = field(default_factory=list)

    def add(self, item: T) -> None:
        heappush(self._values, item)

    def get(self) -> Optional[T]:
        if not self._values:
            return None
        return heappop(self._values)

    def peek(self) -> Optional[T]:
        if not self._values:
            return None
        return self._values[0]

    def remove(self, item: T) -> bool:
        try:
            self._values.remove(item)
        except ValueError:
            return False
        else:
            return True
