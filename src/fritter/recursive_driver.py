# -*- test-case-name: fritter.test.test_tree -*-
from dataclasses import dataclass
from typing import Callable, Optional, Tuple, NewType

from .scheduler import CallHandle, Scheduler

LocalTime = NewType("LocalTime", float)
ParentTime = NewType("ParentTime", float)

@dataclass
class RecursiveDriver:
    parent: Scheduler[float, Callable[[], None]]
    "the parent scheduler"

    # TODO: support for generic types would be nice here, but:

    # 1. for the time type, things have to be multiplied and divided by the
    #    scaling factor, which means it needs to be a float. Even using a
    #    TypeVar bound to `float` here creates a ton of awkward casts below.

    # 2. for the work type, we have our own function that needs to be scheduled
    #    with the parent scheduler, and so we couldn't meaningfully integrate
    #    with a higher-level persistent scheduler.

    _scaleFactor: float = 1.0
    """
    How much faster the local time coordinate system is within this scheduler?
    i.e.: with a scale factor of 2, that means time is running 2 times faster
    in this local temporal coordinate system, and C{self.callAtTimestamp(3.0,
    X)} will run C{X} when the parent's current timestamp is 1.5.
    """

    _call: Optional[CallHandle[ParentTime, Callable[[], None]]] = None

    _offset: ParentTime = ParentTime(0.0)
    """
    Amount to subtract from parent's timestamp to get to this driver's base
    relative timestamp - in parent's (unscaled, not local) time-scale.  When a
    L{RecursiveDriver} is created, it has a default offset of 0, which means
    that the moment '.start()' is called, that is time 0 in local time.
    """

    _running: bool = False
    _pauseTime: LocalTime = LocalTime(0.0)
    """
    Timestamp at which we were last paused.
    """

    _scheduleWhenStarted: Optional[Tuple[LocalTime, Callable[[], None]]] = None

    def _localToParent(self, localTime: LocalTime) -> ParentTime:
        return ParentTime((localTime / self._scaleFactor) + self._offset)

    def _parentToLocal(self, parentTime: ParentTime) -> LocalTime:
        return LocalTime((parentTime - self._offset) * self._scaleFactor)

    @property
    def _parent(self) -> Scheduler[ParentTime, Callable[[], None]]:
        return self.parent      # type:ignore[return-value]

    def reschedule(self, desiredTime: float, work: Callable[[], None]) -> None:
        self._reschedule(LocalTime(desiredTime), work)

    def _reschedule(self, desiredTime: LocalTime, work: Callable[[], None]) -> None:
        assert (
            self._call is None or self._running
        ), f"we weren't running, call should be None not {self._call}"
        self._scheduleWhenStarted = desiredTime, work
        if not self._running:
            return

        if self._call is not None:
            self._call.cancel()

        parentTimestamp = self._localToParent(desiredTime)

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
        return self._currentTimestamp()

    def _currentTimestamp(self) -> LocalTime:
        if self._running:
            return self._parentToLocal(self._parent.currentTimestamp())
        else:
            return self._pauseTime

    # |                       |
    # v recursive driver only v

    def start(self) -> None:
        if self._running:
            return
        # shift forward the offset to skip over the time during which we were
        # paused.
        parentTime: ParentTime = self._parent.currentTimestamp()
        parentDelta: ParentTime = ParentTime(self._pauseTime / self._scaleFactor)

        # We need to cast to the NewType again here because the results of
        # NewType arithmetic are the base types.
        self._offset = ParentTime(parentTime - parentDelta)
        self._pauseTime = LocalTime(0.0)
        self._running = True
        scheduleWhenStarted = self._scheduleWhenStarted
        if scheduleWhenStarted is not None:
            desiredTime, work = scheduleWhenStarted
            self._reschedule(desiredTime, work)

    def pause(self) -> None:
        self._pauseTime = self._currentTimestamp()
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
