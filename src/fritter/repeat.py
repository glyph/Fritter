from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

from twisted.internet.defer import Deferred
from twisted.logger import Logger

from .scheduler import CallHandle, Scheduler


log = Logger()


class RepeatingWork(Protocol):
    """
    The signature of work that is repeated in a loop.
    """

    def __call__(self, steps: int) -> object:
        """
        @param framesPassed: The number of steps which have passed since the
            previous invocation.
        """


@dataclass
class Repeating(object):
    work: RepeatingWork
    s: Scheduler
    _running: Optional[Deferred[None]] = None
    _pending: Optional[CallHandle[float]] = None

    @property
    def running(self) -> bool:
        return self._running is not None

    def start(self, interval: float, now: bool = True) -> Deferred[None]:
        self._running = Deferred(lambda it: self.stop())
        startTime = self.s.currentTimestamp()
        last = 0

        def one() -> None:
            nonlocal last
            elapsed = self.s.currentTimestamp() - startTime
            count = int(elapsed // interval)
            try:
                self.work(count - last)
            except BaseException:
                running = self._running
                if running is not None:
                    self._running = None
                    running.errback()
                else:
                    log.failure("while running doing work {work}", work=self.work)
            else:
                last = count
                if self._running:
                    self.s.callAtTimestamp((interval * (count + 1)) + startTime, one)

        if now:
            one()
        else:
            self.s.callAtTimestamp((interval) + startTime, one)
        return self._running

    def stop(self) -> None:
        running = self._running
        self._running = None
        if running:
            running.callback(None)
