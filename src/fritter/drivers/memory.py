"""
In-memory implementation of L{TimeDriver} for use in tests and batch scripts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Tuple

from math import nextafter, inf

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

    def isScheduled(self) -> bool:
        """
        Does this driver currently have work scheduled with it?
        """
        return self._scheduledWork is not None


_DriverTypeCheck: type[TimeDriver[float]] = MemoryDriver
