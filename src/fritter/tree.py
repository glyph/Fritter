# -*- test-case-name: fritter.test.test_tree -*-
from dataclasses import dataclass
from typing import Callable, NewType, Optional, Protocol, Tuple

from .scheduler import CallHandle, Scheduler

LocalTime = NewType("LocalTime", float)
ParentTime = NewType("ParentTime", float)


class Group(Protocol):
    """
    A L{Group} presents an interface to control a group of timers collected
    into a scheduler; pausing the group, unpausing it, or making its relative
    rate of progress faster or slower.
    """

    scaleFactor: float
    """
    How much faster the local time coordinate system is within this scheduler?
    i.e.: with a scale factor of 2, that means time is running 2 times faster
    in this local temporal coordinate system, and C{self.callAt(3.0,
    X)} will run C{X} when the parent's current timestamp is 1.5.
    """

    def unpause(self) -> None:
        """
        Start the group of timers again.
        """

    def pause(self) -> None:
        """
        Pause the group of timers.
        """


def child(
    parent: Scheduler[float, Callable[[], None]], scaleFactor: float = 1.0
) -> tuple[Group, Scheduler[float, Callable[[], None]]]:
    """
    Derive a child scheduler from a parent scheduler.
    """
    driver = _ChildDriver(parent)
    driver.scaleFactor = scaleFactor
    childScheduler: Scheduler[float, Callable[[], None]] = Scheduler(driver)
    driver.unpause()
    return driver, childScheduler


@dataclass
class _ChildDriver:
    parent: Scheduler[float, Callable[[], None]]
    """
    The scheduler that this driver is a child of.
    """

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
    in this local temporal coordinate system, and C{self.callAt(3.0,
    X)} will run C{X} when the parent's current timestamp is 1.5.
    """

    _call: Optional[CallHandle[ParentTime, Callable[[], None]]] = None

    _offset: ParentTime = ParentTime(0.0)
    """
    Amount to subtract from parent's timestamp to get to this driver's base
    relative timestamp - in parent's (unscaled, not local) time-scale.  When a
    L{ChildDriver} is created, it has a default offset of 0, which means that
    the moment '.start()' is called, that is time 0 in local time.
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
        return self.parent  # type:ignore[return-value]

    def reschedule(self, desiredTime: float, work: Callable[[], None]) -> None:
        self._reschedule(LocalTime(desiredTime), work)

    def _reschedule(
        self, desiredTime: LocalTime, work: Callable[[], None]
    ) -> None:
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

        self._call = self._parent.callAt(parentTimestamp, clearAndRun)

    def unschedule(self) -> None:
        self._scheduleWhenStarted = None
        if self._call is not None:
            self._call.cancel()
            self._call = None

    def now(self) -> float:
        return self._now()

    def _now(self) -> LocalTime:
        if self._running:
            return self._parentToLocal(self._parent.now())
        else:
            return self._pauseTime

    # implementation of 'Group' interface

    def unpause(self) -> None:
        if self._running:
            return
        # shift forward the offset to skip over the time during which we were
        # paused.
        parentTime: ParentTime = self._parent.now()
        parentDelta: ParentTime = ParentTime(
            self._pauseTime / self._scaleFactor
        )

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
        self._pauseTime = self._now()
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
            self.unpause()
        else:
            self._scaleFactor = newScaleFactor
