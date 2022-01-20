from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from twisted.internet.defer import Deferred
from twisted.logger import Logger

from .scheduler import CallHandle, Scheduler


log = Logger()


@dataclass
class Repeating(object):
    c: Callable[[int], None]
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
                self.c(count - last)
            except:
                running = self._running
                if running is not None:
                    self._running = None
                    running.errback()
                else:
                    log.failure("while running callback {c}", c=self.c)
            else:
                last = count
                if self._running:
                    self.s.callAtTimestamp((interval * (count + 1)) + startTime, one)
        if now:
            one()
        else:
            self.s.callAtTimestamp((interval) + startTime, one)
        return self._running

    def stop(self):
        running = self._running
        self._running = None
        if running:
            running.callback(None)
