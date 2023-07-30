from dataclasses import dataclass
from typing import Callable, Optional, Tuple

from .scheduler import CallHandle, Scheduler


@dataclass
class RecursiveDriver:
    _parent: Scheduler[float, Callable[[], None]]

    # TODO: support for generic types would be nice here, but things have to be
    # multiplied and divided by the scaling factor, which means it needs to be
    # a float. Even using a TypeVar bound to `float` here creates a ton of
    # awkward casts below.

    _call: Optional[CallHandle[float, Callable[[], None]]] = None
    _offset: float = 0
    """
    amount to subtract from parent's timestamp to get to this driver's
    relative timestamp - in parent's (unscaled) time-scale
    """

    _running: bool = False
    _pauseTime: float = (
        0.0  # *local* (not parent's) timestamp at which we were paused
    )
    _scheduleWhenStarted: Optional[Tuple[float, Callable[[], None]]] = None
    _scaleFactor: float = 1.0  # how much faster the local time coordinate
    # system is within this scheduler.

    def reschedule(self, desiredTime: float, work: Callable[[], None]) -> None:

        assert (
            self._call is None or self._running
        ), f"we weren't running, call should be None not {self._call}"

        self._scheduleWhenStarted = desiredTime, work
        if not self._running:
            return

        if self._call is not None:
            self._call.cancel()

        parentTimestamp = (desiredTime / self._scaleFactor) + self._offset

        def clearAndRun() -> None:
            self._scheduleWhenStarted = None
            self._call = None
            work()

        self._call = self._parent.callAtTimestamp(parentTimestamp, clearAndRun)

    def unschedule(self) -> None:
        self._scheduleWhenStarted = None
        if self._call is not None:
            self._call.cancel()
            self._call = None

    def currentTimestamp(self) -> float:
        if self._running:
            return (
                self._parent.currentTimestamp() - self._offset
            ) * self._scaleFactor
        else:
            return self._pauseTime

    # |                       |
    # v recursive driver only v

    def start(self) -> None:
        if self._running:
            return
        parentTime = self._parent.currentTimestamp()
        self._offset = parentTime - (self._pauseTime / self._scaleFactor)
        self._pauseTime = 0
        self._running = True
        scheduleWhenStarted = self._scheduleWhenStarted
        if scheduleWhenStarted is not None:
            desiredTime, work = scheduleWhenStarted
            self.reschedule(desiredTime, work)

    def pause(self) -> None:
        self._pauseTime = self.currentTimestamp()
        self._running = False
        if self._call is not None:
            self._call.cancel()
            self._call = None

    @property
    def scaleFactor(self) -> float:
        """
        The scale factor is how much faster than its parent time passes in this
        driver.
        """
        return self._scaleFactor

    @scaleFactor.setter
    def scaleFactor(self, newScaleFactor: float) -> None:
        """
        Change this recursive driver to be running at `newScaleFactor` times
        its parent scheduler's rate.  i.e. driver.changeScaleFactor(3.0) will
        change this driver's rate of time passing to be 3x faster than its
        parent.
        """
        wasRunning = self._running
        if wasRunning:
            self.pause()
            self._scaleFactor = newScaleFactor
            self.start()
        else:
            self._scaleFactor = newScaleFactor
