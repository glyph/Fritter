# -*- test-case-name: fritter.test.test_testing -*-
"""
In-memory implementation of L{TimeDriver} for use in tests and batch scripts.
"""

from __future__ import annotations

from types import NotImplementedType
from dataclasses import dataclass, field
from math import inf, nextafter
from typing import (
    Callable,
    Optional,
    Protocol,
    Tuple,
    TYPE_CHECKING,
    TypeVar,
    Generic,
)
import sys

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

from fritter.boundaries import PriorityComparable

from ..boundaries import TimeDriver


class Numberish(PriorityComparable, Protocol):
    """
    Minimal abstract type to describe L{GeneralMemoryDriver}'s requirements of
    its value.
    """

    def __sub__(self, other: Self) -> Self: ...
    def __lt__(self, other: Self) -> bool | NotImplementedType: ...
    def __add__(self, other: Self) -> Self: ...


if TYPE_CHECKING:
    from decimal import Decimal
    from fractions import Fraction

    _numberishDescribesFloat: Numberish = 0.0
    _numberishDescribesInt: Numberish = 0
    _numberishDescribesDecimal: Numberish = Decimal()
    _numberishDescribesFraction: Numberish = Fraction()

WhenT = TypeVar("WhenT", bound=Numberish)


@dataclass
class GeneralMemoryDriver(Generic[WhenT]):
    """
    A L{GeneralMemoryDriver} is an in-memory L{TimeDriver} that only moves when
    L{advance <GeneralMemoryDriver.advance>} is called.
    """

    _currentTime: WhenT
    _scheduledWork: Optional[Tuple[WhenT, Callable[[], None]]]
    _nextgreater: Callable[[WhenT], WhenT]
    _zero: WhenT
    _inf: WhenT

    def reschedule(self, desiredTime: WhenT, work: Callable[[], None]) -> None:
        """
        Schedule the given work to happen at the given time.

        @note: In order to avoid infinite loops where time is not moving
            forward while work is being scheduled at the current moment or in
            the past, time (as referenced by L{MemoryDriver.now}) will always
            advance by at least one U{ULP
            <https://en.wikipedia.org/wiki/Unit_in_the_last_place>}, so if
            C{desiredTime} is before or exactly C{now}, by the time C{work} is
            run, C{now} will be very slightly greater.

        @see: L{TimeDriver.reschedule}
        """
        minInterval = self._nextgreater(self._currentTime)
        self._scheduledWork = max(minInterval, desiredTime), work

    def unschedule(self) -> None:
        "L{TimeDriver.unschedule}"
        self._scheduledWork = None

    def now(self) -> WhenT:
        "L{TimeDriver.now}"
        return self._currentTime

    # |   memory driver only  |
    # v                       v

    def advance(self, delta: WhenT | None = None) -> WhenT | None:
        """
        Advance the clock of L{this driver <MemoryDriver>} by C{delta} seconds.

        If no C{delta} is provided, then advance until the next scheduled time
        when this driver would run something.

        @return: the amount of time that was advanced, or None if no work was
            scheduled.
        """
        if delta is None:
            if self._scheduledWork is not None:
                delta = max(
                    self._zero, self._scheduledWork[0] - self._currentTime
                )
            else:
                return None
        self._currentTime += delta
        while (self._scheduledWork is not None) and (
            self._currentTime >= self._scheduledWork[0]
        ):
            what = self._scheduledWork[1]
            self._scheduledWork = None
            what()
        return delta

    def step(self, until: WhenT | None = None, maxCalls: int = 100) -> int:
        """
        If any work is scheduled, move the clock forward (but only forward) to
        exactly the time that the work is due.  If work is scheduled earlier
        than C{.now()}, it will be run without adjusting time.
        """
        calls = 0
        while (
            self._scheduledWork is not None
            and self._scheduledWork[0]
            < (self._inf if until is None else until)
            and calls < maxCalls
        ):
            calls += 1
            desiredTime, work = self._scheduledWork
            self._currentTime = max(desiredTime, self._currentTime)
            self._scheduledWork = None
            work()
        if until is not None:
            self._currentTime = until
        return calls

    def isScheduled(self) -> bool:
        """
        Does this driver currently have work scheduled with it?
        """
        return self._scheduledWork is not None


@dataclass
class MemoryDriver(GeneralMemoryDriver[float]):
    """
    A L{MemoryDriver} is a L{GeneralMemoryDriver} for floating-point
    timestamps, with a bunch of defaults set to reasonable values.
    """

    _currentTime: float = 0.0
    _scheduledWork: Optional[Tuple[float, Callable[[], None]]] = None
    _nextgreater: Callable[[float], float] = field(
        default_factory=lambda: lambda it: nextafter(it, inf)
    )
    _zero: float = 0.0
    _inf: float = inf


_DriverTypeCheck: type[TimeDriver[float]] = MemoryDriver


@dataclass
class DiscreteDriver(Generic[WhenT]):
    """
    A L{DiscreteDriver} advances time in a series of I{discrete steps}, meaning
    that while your scheduled callable is running, the C{now} value will
    reflect the time at which your callable was scheduled.
    """

    _discrete: GeneralMemoryDriver[WhenT]
    _driver: TimeDriver[WhenT]

    def reschedule(self, desiredTime: WhenT, work: Callable[[], None]) -> None:
        """
        Implement L{TimeDriver.reschedule}.
        """

        def step() -> None:
            self._discrete.step(until=self._driver.now())

        self._driver.reschedule(desiredTime, step)
        self._discrete.reschedule(desiredTime, work)

    def unschedule(self) -> None:
        """
        Implement L{TimeDriver.unschedule}.
        """
        self._driver.unschedule()
        self._discrete.unschedule()

    def now(self) -> WhenT:
        """
        Return the time of the currently running, or last run scheduled work.
        """
        return self._discrete.now()


_DriverTypeCheck2: type[TimeDriver[float]] = DiscreteDriver
