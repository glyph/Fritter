# -*- test-case-name: fritter.test.test_testing -*-
"""
In-memory implementation of L{TimeDriver} for use in tests and batch scripts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import inf, nextafter
from typing import Callable, Optional, Tuple

from ..boundaries import TimeDriver


@dataclass
class MemoryDriver:
    """
    In-memory L{TimeDriver} that only moves when L{advance
    <MemoryDriver.advance>} is called.
    """

    _currentTime: float = 0.0
    _scheduledWork: Optional[Tuple[float, Callable[[], None]]] = None

    def reschedule(self, desiredTime: float, work: Callable[[], None]) -> None:
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
        minInterval = nextafter(self._currentTime, inf)
        self._scheduledWork = max(minInterval, desiredTime), work

    def unschedule(self) -> None:
        "L{TimeDriver.unschedule}"
        self._scheduledWork = None

    def now(self) -> float:
        "L{TimeDriver.now}"
        return self._currentTime

    # |   memory driver only  |
    # v                       v

    def advance(self, delta: Optional[float] = None) -> float | None:
        """
        Advance the clock of L{this driver <MemoryDriver>} by C{delta} seconds.

        If no C{delta} is provided, then advance until the next scheduled time
        when this driver would run something.

        @return: the amount of time that was advanced, or None if no work was
            scheduled.
        """
        if delta is None:
            if self._scheduledWork is not None:
                delta = max(0, self._scheduledWork[0] - self._currentTime)
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

    def step(self, until: float | None = None, maxCalls: int = 100) -> int:
        """
        If any work is scheduled, move the clock forward (but only forward) to
        exactly the time that the work is due.  If work is scheduled earlier
        than C{.now()}, it will be run without adjusting time.
        """
        calls = 0
        while (
            self._scheduledWork is not None
            and self._scheduledWork[0] < (inf if until is None else until)
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


_DriverTypeCheck: type[TimeDriver[float]] = MemoryDriver


@dataclass
class DiscreteDriver:
    """
    A L{DiscreteDriver} advances time in a series of I{discrete steps}, meaning
    that while your scheduled callable is running, the C{now} value will
    reflect the time at which your callable was scheduled.
    """

    _driver: TimeDriver[float]
    _discrete: MemoryDriver = field(default_factory=MemoryDriver)

    def reschedule(self, desiredTime: float, work: Callable[[], None]) -> None:
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

    def now(self) -> float:
        """
        Implement L{TimeDriver.now}.
        """
        return self._discrete.now()


_DriverTypeCheck2: type[TimeDriver[float]] = DiscreteDriver
