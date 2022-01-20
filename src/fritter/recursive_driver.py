from dataclasses import dataclass
from typing import Callable, Optional, Tuple

from .scheduler import CallHandle, Scheduler



@dataclass
class RecursiveDriver(object):
    _parent: Scheduler
    _call: Optional[CallHandle[float]] = None
    _offset: float = 0  # relative to parent's timestamp
    _running: bool = False
    _pauseTime: float = 0  # *local* (not parent's) timestamp at which we were paused
    _toRunWhenStarted: Optional[Tuple[float, Callable[[], None]]] = None

    def reschedule(self, desiredTime: float, work: Callable[[], None]):
        def _():
            self._toRunWhenStarted = None
            self._call = None
            work()

        if self._call is not None:
            self._call.cancel()
        self._toRunWhenStarted = desiredTime, work
        if self._running:
            self._call = self._parent.callAtTimestamp(desiredTime + self._offset, _)
        else:
            assert (
                self._call is None
            ), f"we weren't running, call should be None not {self._call}"

    def unschedule(self):
        self._toRunWhenStarted = None
        if self._call is not None:
            self._call.cancel()
            self._call = None

    def currentTimestamp(self) -> float:
        if self._running:
            return self._parent.currentTimestamp() - self._offset
        else:
            return self._pauseTime

    # |                       |
    # v recursive driver only v

    def start(self):
        self._offset = self._scheduler.currentTimestamp() + self._pauseTime
        self._pauseTime = 0
        self._running = True
        rws = self._toRunWhenStarted
        if rws is not None:
            self.reschedule(*rws)

    def pause(self):
        self._pauseTime = self.currentTimestamp()
        self._running = False
        if self._call is not None:
            self._call.cancel()
            self._call = None
