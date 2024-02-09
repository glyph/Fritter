# -*- test-case-name: fritter.test.test_tree -*-

"""
Groups of timers that may be paused, resumed, or time-scaled together.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import (
    Callable,
    Generic,
    Optional,
    Protocol,
    Tuple,
    TypeVar,
)

from fritter.boundaries import PriorityComparable, WhenT

from .scheduler import FutureCall, Scheduler

_BranchTime = TypeVar("_BranchTime", bound=PriorityComparable)
_TrunkTime = TypeVar("_TrunkTime", bound=PriorityComparable)
_TrunkDelta = TypeVar("_TrunkDelta")


class Scale(Protocol[_BranchTime, _TrunkTime]):
    def up(self, time: _BranchTime) -> _TrunkTime:
        ...

    def down(self, time: _TrunkTime) -> _BranchTime:
        ...

    def zero(self) -> _TrunkTime:
        ...

    def shift(self, pauseTime: _BranchTime, currentTime: _TrunkTime) -> None:
        ...

T = TypeVar("T")


@dataclass
class NoScale(Generic[T]):
    _zero: T

    def up(self, time: T) -> T:
        return time

    def down(self, time: T) -> T:
        return time

    def zero(self) -> T:
        return self._zero



_BranchFloat = TypeVar("_BranchFloat", bound=float)
_TrunkFloat = TypeVar("_TrunkFloat", bound=float)

@dataclass
class FloatScale(Generic[_BranchFloat, _TrunkFloat]):
    factor: float

    _offset: _TrunkFloat = 0.0  # type:ignore[assignment]
    _fudge: float = 0.0

    """
    Amount to subtract from trunk's timestamp to get to this driver's base
    relative timestamp - in trunk's (unscaled, not branch) time-scale.  When a
    L{_BranchDriver} is created, it has a default offset of 0, which means that
    the moment '.start()' is called, that is time 0 in branch time.
    """

    def up(self, time: _BranchFloat) -> _TrunkFloat:
        trunk: _TrunkFloat
        computed = ((time / self.factor) + self._offset)
        trunk = computed        # type:ignore[assignment]

        roundTripped: _BranchFloat = self.down(trunk)
        self._fudge = _subtract(time, roundTripped)
        return trunk

    def down(self, trunkTime: _TrunkFloat) -> _BranchFloat:
        computed  = ((trunkTime - self._offset) * self.factor) + self._fudge
        branch: _BranchFloat = computed  # type:ignore[assignment]
        return branch

    def shift(self, pauseTime: _BranchFloat, currentTime: _TrunkTime) -> None:
        trunkDelta = pauseTime / self.factor
        self._offset = currentTime - trunkDelta  # type:ignore[assignment,operator]

    def zero(self) -> _BranchFloat:
        return 0.0              # type:ignore[return-value]


def timesFaster(factor: float) -> FloatScale[float,float]:
    return FloatScale(factor)


class Group(Protocol[WhenT]):
    """
    A L{Group} presents an interface to control a group of timers collected
    into a scheduler; pausing the group, unpausing it, or making its relative
    rate of progress faster or slower.
    """

    scale: Scale[WhenT, WhenT]
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
    trunk: Scheduler[WhenT, Callable[[], None]],
    scale: Scale[WhenT, WhenT],
) -> tuple[Group[WhenT], Scheduler[WhenT, Callable[[], None]]]:
    """
    Derive a branch (child) scheduler from a trunk (trunk) scheduler.
    """
    driver: _BranchDriver[WhenT, WhenT] = _BranchDriver(trunk, scale, scale.zero())
    driver.scale = scale
    branchScheduler: Scheduler[WhenT, Callable[[], None]] = Scheduler(driver)
    driver.unpause()
    return driver, branchScheduler


_F = TypeVar("_F", bound=float)


def _add(someFloat: _F, other: _F) -> _F:
    return someFloat + other  # type:ignore[return-value]


def _subtract(someFloat: _F, other: _F) -> _F:
    return someFloat - other  # type:ignore[return-value]


@dataclass
class _BranchDriver(Generic[_TrunkTime, _BranchTime]):
    """
    Implementation of L{TimeDriver} for L{Scheduler} that is stacked on top of
    another L{Scheduler}.
    """

    trunk: Scheduler[_TrunkTime, Callable[[], None]]
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

    _scale: Scale[_BranchTime, _TrunkTime]
    """
    How much faster the branch time coordinate system is within this scheduler?
    i.e.: with a scale factor of 2, that means time is running 2 times faster
    in this branch temporal coordinate system, and C{self.callAt(3.0,
    X)} will run C{X} when the trunk's current timestamp is 1.5.
    """

    _pauseTime: _BranchTime
    """
    Timestamp at which we were last paused.
    """

    _scheduleWhenStarted: Optional[Tuple[_BranchTime, Callable[[], None]]] = None

    _call: Optional[FutureCall[_TrunkTime, Callable[[], None]]] = None
    _running: bool = False

    def reschedule(self, desiredTime: _BranchTime, work: Callable[[], None]) -> None:
        assert (
            self._call is None or self._running
        ), f"we weren't running, call should be None not {self._call}"
        self._scheduleWhenStarted = desiredTime, work
        if not self._running:
            return

        if self._call is not None:
            self._call.cancel()

        def clearAndRun() -> None:
            self._scheduleWhenStarted = None
            self._call = None
            work()

        self._call = self.trunk.callAt(self._scale.up(desiredTime), clearAndRun)

    def unschedule(self) -> None:
        self._scheduleWhenStarted = None
        if self._call is not None:
            self._call.cancel()
            self._call = None

    def now(self) -> _BranchTime:
        if self._running:
            return self._scale.down(self.trunk.now())
        else:
            return self._pauseTime

    # implementation of 'Group' interface

    def unpause(self) -> None:
        if self._running:
            return
        # shift forward the offset to skip over the time during which we were
        # paused.
        self._scale.shift(self._pauseTime, self.trunk.now())
        self._running = True
        scheduleWhenStarted = self._scheduleWhenStarted
        if scheduleWhenStarted is not None:
            desiredTime, work = scheduleWhenStarted
            self.reschedule(desiredTime, work)

    def pause(self) -> None:
        self._pauseTime = self.now()
        self._running = False
        if self._call is not None:
            self._call.cancel()
            self._call = None

    @property
    def scale(self) -> Scale[_BranchTime, _TrunkTime]:
        """
        The scale factor is how much faster than its trunk time passes in this
        driver.
        """
        return self._scale

    @scale.setter
    def scale(self, newScale: Scale[_BranchTime, _TrunkTime]) -> None:
        """
        Change this recursive driver to be running at `newScale` times
        versus trunk scheduler's rate.  i.e. C{driver.scale = FloatScale(3.0)} will
        change this driver's rate of time passing to be 3x faster than its
        trunk.
        """
        wasRunning = self._running
        if wasRunning:
            self.pause()
            self._scale = newScale
            self.unpause()
        else:
            self._scale = newScale
