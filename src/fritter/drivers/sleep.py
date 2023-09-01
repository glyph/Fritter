# -*- test-case-name: fritter.test.test_sleep -*-
"""
Implementation of L{TimeDriver} that can run timers by blocking until all its
timers have been run, sleeping between them as necessary.

This is suitable for batch scripts that don't require an event loop like
L{asyncio <fritter.drivers.asyncio>} or L{twisted <fritter.drivers.twisted>}.
"""
from dataclasses import dataclass
from time import sleep as _sleep, time as _time
from typing import Callable

from ..boundaries import TimeDriver


@dataclass
class SleepDriver:
    """
    Instantiate a L{SleepDriver} with no arguments to get one that sleeps using
    L{time.sleep} and gets the current time with L{time.time}.

    For testing, you can supply those parameters, but for most test cases, you
    should probably prefer a L{fritter.drivers.memory.MemoryDriver}.

    @ivar sleep: The L{time.sleep}-like callable that this driver will use to
        sleep for a given number of seconds.

    @ivar time: The L{time.time}-like callable that this driver will use to get
        the current time.
    """

    sleep: Callable[[float], None] = _sleep
    time: Callable[[], float] = _time
    _work: tuple[float, Callable[[], None]] | None = None

    def reschedule(self, desiredTime: float, work: Callable[[], None]) -> None:
        "Implementation of L{TimeDriver.reschedule}"
        self._work = desiredTime, work

    def unschedule(self) -> None:
        "Implementation of L{TimeDriver.unschedule}"
        self._work = None

    def now(self) -> float:
        "Implementation of L{TimeDriver.now}"
        return self.time()

    def block(self) -> int:
        """
        While any active timer is scheduled with L{reschedule
        <SleepDriver.reschedule>}, sleep until the desired time specified by
        that call, call the work that was scheduled, and repeat.
        """
        worked = 0
        while True:
            scheduled = self._work
            if scheduled is None:
                break
            worked += 1
            self._work, (time, work) = None, scheduled
            self.sleep(max(0, time - self.time()))
            work()
        return worked


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    _CheckSleepDriver: type[TimeDriver[float]] = SleepDriver
