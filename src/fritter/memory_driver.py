from dataclasses import dataclass
from typing import Callable, Optional, Tuple


@dataclass
class MemoryDriver(object):
    _currentTime: float = 0.0
    _scheduledWork: Optional[Tuple[float, Callable[[], None]]] = None

    def reschedule(self, desiredTime: float, work: Callable[[], None]) -> None:
        self._scheduledWork = desiredTime, work

    def unschedule(self) -> None:
        self._scheduledWork = None

    def currentTimestamp(self) -> float:
        return self._currentTime

    # |   memory driver only  |
    # v                       v

    def advance(self, delta: Optional[float] = None) -> None:
        if delta is None:
            if self._scheduledWork is not None:
                delta = self._scheduledWork[0] - self._currentTime
            else:
                return
        self._currentTime += delta
        while (self._scheduledWork is not None) and (
            self._currentTime >= self._scheduledWork[0]
        ):
            what = self._scheduledWork[1]
            self._scheduledWork = None
            what()

    def isScheduled(self) -> bool:
        return self._scheduledWork is not None
