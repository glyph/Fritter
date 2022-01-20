from dataclasses import dataclass
from typing import Callable, Optional

from .scheduler import CallHandle, Scheduler


@dataclass
class RecursiveDriver(object):
    _scheduler: Scheduler
    _call: Optional[CallHandle[float]] = None

    def reschedule(self, desiredTime: float, work: Callable[[], None]):
        def _():
            self._call = None
            work()

        if self._call is not None:
            self._call.cancel()
        self._call = self._scheduler.callAtTimestamp(desiredTime, _)

    def unschedule(self):
        if self._call is not None:
            self._call.cancel()
            self._call = None

    def currentTimestamp(self) -> float:
        return self._scheduler.currentTimestamp()
