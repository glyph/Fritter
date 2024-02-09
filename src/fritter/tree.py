# -*- test-case-name: fritter.test.test_tree -*-

"""
Groups of timers that may be paused, resumed, or time-scaled together.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Generic,
    Optional,
    Protocol,
    Self,
    Tuple,
    TypeVar,
    overload,
)

from fritter.boundaries import PriorityComparable

from .scheduler import FutureCall, Scheduler

_BranchTime = TypeVar("_BranchTime", bound=PriorityComparable)
_TrunkTime = TypeVar("_TrunkTime", bound=PriorityComparable)
_TrunkDelta = TypeVar("_TrunkDelta")


class Scale(Protocol[_BranchTime, _TrunkTime, _TrunkDelta]):
    """
    A L{Scale} defines a translation between a child, or "branch" time scale,
    and a parent, or "trunk" time scale.
    """

    def up(self, offset: _TrunkDelta, time: _BranchTime) -> _TrunkTime:
        """
        Translate C{time} from the branch time scale into the trunk time scale.
        """

    def down(self, offset: _TrunkDelta, time: _TrunkTime) -> _BranchTime:
        """
        Translate C{time} from the trunk time scale into the branch time scale.
        """

    def shift(
        self, pauseTime: _BranchTime | None, currentTime: _TrunkTime
    ) -> _TrunkDelta:
        """
        Shift the current scale forward to incorporate
        """


DT = TypeVar("DT")


class Deltable(PriorityComparable, Protocol[DT]):
    def __add__(self, addend: DT) -> Self: ...

    @overload
    def __sub__(self, subtrahend: Self) -> DT: ...

    @overload
    def __sub__(self, subtrahend: DT) -> Self: ...


WhenT = TypeVar("WhenT", bound=Deltable[Any])


@dataclass
class NoScale(Generic[DT]):
    T = TypeVar("T", bound=Deltable[DT])

    def up(self, offset: DT, time: T) -> T:
        if offset is None:
            return time
        return time + offset

    def down(self, offset: DT, time: T) -> T:
        if offset is None:
            return time
        return time - offset

    def shift(self, pauseTime: T | None, currentTime: T) -> DT:
        if pauseTime is None:
            return None  # type:ignore[return-value]
        return currentTime - pauseTime


_BranchFloat = TypeVar("_BranchFloat", bound=float)
_TrunkFloat = TypeVar("_TrunkFloat", bound=float)


@dataclass
class _FloatScale(Generic[_BranchFloat, _TrunkFloat]):
    _factor: float

    """
    Amount to subtract from trunk's timestamp to get to this driver's base
    relative timestamp - in trunk's (unscaled, not branch) time-scale.  When a
    L{_BranchDriver} is created, it has a default offset of 0, which means that
    the moment '.start()' is called, that is time 0 in branch time.
    """

    _fudge: _BranchFloat = 0.0  # type:ignore[assignment]
    """
    An epsilon value computed to always be large enough that the conversion up
    to trunk and down to branch time scale will not result in time going
    backwards.
    """

    def up(self, offset: _TrunkFloat, time: _BranchFloat) -> _TrunkFloat:
        computed = (time / self._factor) + offset
        trunk: _TrunkFloat
        trunk = computed  # type:ignore[assignment]
        roundTripped: _BranchFloat = self.down(offset, trunk)
        self._fudge = _subtract(time, roundTripped)
        return trunk

    def down(
        self, offset: _TrunkFloat, trunkTime: _TrunkFloat
    ) -> _BranchFloat:
        computed = ((trunkTime - offset) * self._factor) + self._fudge
        branch: _BranchFloat = computed  # type:ignore[assignment]
        return branch

    def shift(
        self, pauseTime: _BranchFloat | None, currentTime: _TrunkFloat
    ) -> _TrunkFloat:
        delta = (pauseTime / self._factor) if pauseTime else 0.0
        trunkDelta: _TrunkFloat
        trunkDelta = delta  # type:ignore[assignment]
        return _subtract(currentTime, trunkDelta)


def timesFaster(factor: float) -> Scale[float, float, float]:
    """
    Scale a C{float} time-scale by C{factor}.  e.g., in ::

        group, child = branch(parent, timesFaster(3.0))

    C{child} will be a child scheduler running 3 times faster than C{parent}.
    """
    return _FloatScale(factor)


class Group(Protocol[WhenT, _TrunkDelta]):
    """
    A L{Group} presents an interface to control a group of timers collected
    into a scheduler; pausing the group, unpausing it, or making its relative
    rate of progress faster or slower.
    """

    scale: Scale[WhenT, WhenT, _TrunkDelta]
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


@overload
def branch(
    trunk: Scheduler[WhenT, Callable[[], None]],
    scale: Scale[WhenT, WhenT, _TrunkDelta],
) -> tuple[
    Group[WhenT, _TrunkDelta], Scheduler[WhenT, Callable[[], None]]
]: ...


@overload
def branch(
    trunk: Scheduler[float, Callable[[], None]]
) -> tuple[Group[float, float], Scheduler[float, Callable[[], None]]]: ...


def branch(
    trunk: Scheduler[WhenT, Callable[[], None]],
    scale: Scale[WhenT, WhenT, _TrunkDelta] | None = None,
) -> tuple[Group[WhenT, _TrunkDelta], Scheduler[WhenT, Callable[[], None]]]:
    """
    Derive a branch (child) scheduler from a trunk (trunk) scheduler.
    """
    if scale is None:
        scale = NoScale[_TrunkDelta]()
        # scale = timesFaster(1)  # type:ignore
    assert scale is not None
    driver: _BranchDriver[WhenT, WhenT, _TrunkDelta] = _BranchDriver(
        trunk, scale, scale.shift(None, trunk.now())
    )
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
class _BranchDriver(Generic[_TrunkTime, _BranchTime, _TrunkDelta]):
    """
    Implementation of L{TimeDriver} for L{Scheduler} that is stacked on top of
    another L{Scheduler}.
    """

    trunk: Scheduler[_TrunkTime, Callable[[], None]]
    """
    The scheduler that this driver is a branch of.
    """
    # TODO: support for a generic WhatT would be nice here, but we have our own
    # function that needs to be scheduled with the trunk scheduler, and so we
    # couldn't meaningfully integrate with a higher-level persistent scheduler.

    _scale: Scale[_BranchTime, _TrunkTime, _TrunkDelta]
    """
    How much faster the branch time coordinate system is within this scheduler?
    i.e.: with a scale factor of 2, that means time is running 2 times faster
    in this branch temporal coordinate system, and C{self.callAt(3.0, X)} will
    run C{X} when the trunk's current timestamp is 1.5.
    """
    _offset: _TrunkDelta

    _pauseTime: _BranchTime | None = None
    """
    Timestamp at which we were last paused, if we were last paused.
    """

    _scheduleWhenStarted: Optional[Tuple[_BranchTime, Callable[[], None]]] = (
        None
    )

    _call: Optional[FutureCall[_TrunkTime, Callable[[], None]]] = None
    _running: bool = False

    def reschedule(
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

        def clearAndRun() -> None:
            self._scheduleWhenStarted = None
            self._call = None
            work()

        self._call = self.trunk.callAt(
            self._scale.up(self._offset, desiredTime), clearAndRun
        )

    def unschedule(self) -> None:
        self._scheduleWhenStarted = None
        if self._call is not None:
            self._call.cancel()
            self._call = None

    def now(self) -> _BranchTime:
        if self._running:
            return self._scale.down(self._offset, self.trunk.now())
        assert (
            self._pauseTime is not None
        ), "If a timer has been paused, _pauseTime must have been set"
        return self._pauseTime

    # implementation of 'Group' interface

    def unpause(self) -> None:
        if self._running:
            return
        # shift forward the offset to skip over the time during which we were
        # paused.
        self._offset = self._scale.shift(self._pauseTime, self.trunk.now())
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
    def scale(self) -> Scale[_BranchTime, _TrunkTime, _TrunkDelta]:
        """
        @see: L{Scale}
        """
        return self._scale

    @scale.setter
    def scale(
        self, newScale: Scale[_BranchTime, _TrunkTime, _TrunkDelta]
    ) -> None:
        """
        Change this recursive driver to be running at the time scale of
        C{newScale}.  i.e. C{driver.scale = timesFaster(3.0)} will change this
        driver's rate of time passing to be 3x faster than its trunk, presuming
        it is a float-based timer.
        """
        wasRunning = self._running
        if wasRunning:
            self.pause()
            self._scale = newScale
            self.unpause()
        else:
            self._scale = newScale
