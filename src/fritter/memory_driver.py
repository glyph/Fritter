from dataclasses import dataclass
from typing import Callable, Optional, Tuple


@dataclass
class MemoryDriver(object):
    _currentTime: float = 0
    _scheduledWork: Optional[Tuple[float, Callable[[], None]]] = None

    def reschedule(self, desiredTime: float, work: Callable[[], None]):
        self._scheduledWork = desiredTime, work

    def unschedule(self):
        self._scheduledWork = None

    def currentTimestamp(self) -> float:
        return self._currentTime

    def advance(self, delta: Optional[float] = None) -> None:
        self._currentTime += delta
        while self._scheduledWork is not None:
            when, what = self._scheduledWork
            if when > self._currentTime:
                break
            self._scheduledWork = None
            what()
