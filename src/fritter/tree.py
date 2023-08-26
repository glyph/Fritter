# -*- test-case-name: fritter.test.test_tree -*-

"""
Groups of timers that may be paused, resumed, or time-scaled together.
"""

from __future__ import annotations
from dataclasses import dataclass
from .scheduler import FutureCall
from typing import Callable, NewType, Optional, Protocol, Tuple, TypeVar

from .scheduler import Scheduler

_BranchTime = NewType("_BranchTime", float)
_TrunkTime = NewType("_TrunkTime", float)


class Group(Protocol):
    """
    A L{Group} presents an interface to control a group of timers collected
    into a scheduler; pausing the group, unpausing it, or making its relative
    rate of progress faster or slower.
    """

    scaleFactor: float
    """
    How much faster the branch time coordinate system is within this scheduler?
    i.e.: with a scale factor of 2, that means time is running 2 times faster
    in this branch temporal coordinate system, and C{self.callAt(3.0,
    X)} will run C{X} when the trunk's current timestamp is 1.5.
    """

    def unpause(self) -> None:
        """
        Start the group of timers again.
        """

    def pause(self) -> None:
        """
        Pause the group of timers.
        """


def branch(
    trunk: Scheduler[float, Callable[[], None]], scaleFactor: float = 1.0
) -> tuple[Group, Scheduler[float, Callable[[], None]]]:
    """
    Derive a branch (child) scheduler from a trunk (trunk) scheduler.
    """
    driver = _BranchDriver(trunk)
    driver.scaleFactor = scaleFactor
    branchScheduler: Scheduler[float, Callable[[], None]] = Scheduler(driver)
    driver.unpause()
    return driver, branchScheduler


_F = TypeVar("_F", bound=float)


def _add(someFloat: _F, other: _F) -> _F:
    return someFloat + other  # type:ignore[return-value]


def _subtract(someFloat: _F, other: _F) -> _F:
    return someFloat - other  # type:ignore[return-value]


@dataclass
class _BranchDriver:
    """
    Implementation of L{TimeDriver} for L{Scheduler} that is stacked on top of
    another L{Scheduler}.
    """

    trunk: Scheduler[float, Callable[[], None]]
    """
    The scheduler that this driver is a branch of.
    """

    # TODO: support for generic types would be nice here, but:

    # 1. for the time type, things have to be multiplied and divided by the
    #    scaling factor, which means it needs to be a float. Even using a
    #    TypeVar bound to `float` here creates a ton of awkward casts below.

    # 2. for the work type, we have our own function that needs to be scheduled
    #    with the trunk scheduler, and so we couldn't meaningfully integrate
    #    with a higher-level persistent scheduler.

    _scaleFactor: float = 1.0
    """
    How much faster the branch time coordinate system is within this scheduler?
    i.e.: with a scale factor of 2, that means time is running 2 times faster
    in this branch temporal coordinate system, and C{self.callAt(3.0,
    X)} will run C{X} when the trunk's current timestamp is 1.5.
    """

    _call: Optional[FutureCall[_TrunkTime, Callable[[], None]]] = None

    _offset: _TrunkTime = _TrunkTime(0.0)
    """
    Amount to subtract from trunk's timestamp to get to this driver's base
    relative timestamp - in trunk's (unscaled, not branch) time-scale.  When a
    L{_BranchDriver} is created, it has a default offset of 0, which means that
    the moment '.start()' is called, that is time 0 in branch time.
    """

    _running: bool = False
    _pauseTime: _BranchTime = _BranchTime(0.0)
    """
    Timestamp at which we were last paused.
    """
    _fudge: _BranchTime = _BranchTime(0.0)

    _scheduleWhenStarted: Optional[
        Tuple[_BranchTime, Callable[[], None]]
    ] = None

    def _branchToTrunk(self, branchTime: _BranchTime) -> _TrunkTime:
        return _TrunkTime((branchTime / self._scaleFactor) + self._offset)

    def _trunkToBranch(self, trunkTime: _TrunkTime) -> _BranchTime:
        return _BranchTime((trunkTime - self._offset) * self._scaleFactor)

    @property
    def _trunk(self) -> Scheduler[_TrunkTime, Callable[[], None]]:
        return self.trunk  # type:ignore[return-value]

    def reschedule(self, desiredTime: float, work: Callable[[], None]) -> None:
        self._reschedule(_BranchTime(desiredTime), work)

    def _reschedule(
        self, desiredTime: _BranchTime, work: Callable[[], None]
    ) -> None:
        assert (
            self._call is None or self._running
        ), f"we weren't running, call should be None not {self._call}"
        self._scheduleWhenStarted = desiredTime, work
        if not self._running:
            return

        if self._call is not None:
            self._call.cancel()

        trunkTimestamp = self._branchToTrunk(desiredTime)
        roundTripped: _BranchTime = self._trunkToBranch(trunkTimestamp)
        self._fudge = _subtract(desiredTime, roundTripped)

        def clearAndRun() -> None:
            self._scheduleWhenStarted = None
            self._call = None
            work()

        self._call = self._trunk.callAt(trunkTimestamp, clearAndRun)

    def unschedule(self) -> None:
        self._scheduleWhenStarted = None
        if self._call is not None:
            self._call.cancel()
            self._call = None

    def now(self) -> float:
        return self._now()

    def _now(self) -> _BranchTime:
        if self._running:
            return _add(self._trunkToBranch(self._trunk.now()), self._fudge)
        else:
            return self._pauseTime

    # implementation of 'Group' interface

    def unpause(self) -> None:
        if self._running:
            return
        # shift forward the offset to skip over the time during which we were
        # paused.
        trunkTime: _TrunkTime = self._trunk.now()
        trunkDelta: _TrunkTime = _TrunkTime(
            self._pauseTime / self._scaleFactor
        )

        # We need to cast to the NewType again here because the results of
        # NewType arithmetic are the base types.
        self._offset = _TrunkTime(trunkTime - trunkDelta)
        self._pauseTime = _BranchTime(0.0)
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
        The scale factor is how much faster than its trunk time passes in this
        driver.
        """
        return self._scaleFactor

    @scaleFactor.setter
    def scaleFactor(self, newScaleFactor: float) -> None:
        """
        Change this recursive driver to be running at `newScaleFactor` times
        its trunk scheduler's rate.  i.e. driver.changeScaleFactor(3.0) will
        change this driver's rate of time passing to be 3x faster than its
        trunk.
        """
        wasRunning = self._running
        if wasRunning:
            self.pause()
            self._scaleFactor = newScaleFactor
            self.unpause()
        else:
            self._scaleFactor = newScaleFactor
