from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Tuple

from math import nextafter, inf


@dataclass
class MemoryDriver:
    _currentTime: float = 0.0
    _scheduledWork: Optional[Tuple[float, Callable[[], None]]] = None

    def reschedule(self, desiredTime: float, work: Callable[[], None]) -> None:
        minInterval = nextafter(self._currentTime, inf)
        self._scheduledWork = max(minInterval, desiredTime), work

    def unschedule(self) -> None:
        self._scheduledWork = None

    def now(self) -> float:
        return self._currentTime

    # |   memory driver only  |
    # v                       v

    def advance(self, delta: Optional[float] = None) -> float | None:
        if delta is None:
            if self._scheduledWork is not None:
                delta = max(0, self._scheduledWork[0] - self._currentTime)
            else:
                return None
        self._currentTime += delta
        while (self._scheduledWork is not None) and (
            self._currentTime >= self._scheduledWork[0]
        ):
            what = self._scheduledWork[1]
            self._scheduledWork = None
            what()
        return delta

    def isScheduled(self) -> bool:
        return self._scheduledWork is not None
