from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Optional

from .scheduler import CallHandle, Scheduler
from .boundaries import AsyncType, AsyncDriver, RepeatingWork


@dataclass
class Repeating(Generic[AsyncType]):
    work: RepeatingWork
    _scheduler: Scheduler[float]
    _driver: AsyncDriver[AsyncType]
    _running: Optional[AsyncType] = None
    _pending: Optional[CallHandle[float]] = None

    @property
    def running(self) -> bool:
        return self._running is not None

    def start(self, interval: float, now: bool = True) -> AsyncType:
        self._running = self._driver.newWithCancel(self.stop)
        startTime = self._scheduler.currentTimestamp()
        last = 0

        def one() -> None:
            nonlocal last
            elapsed = self._scheduler.currentTimestamp() - startTime
            count = int(elapsed // interval)
            try:
                self.work(count - last)
            except BaseException:
                running = self._running
                self._running = None
                self._driver.unhandledError(self.work, running)
            else:
                last = count
                if self._running:
                    self._scheduler.callAtTimestamp(
                        (interval * (count + 1)) + startTime, one
                    )

        if now:
            one()
        else:
            self._scheduler.callAtTimestamp((interval) + startTime, one)
        return self._running

    def stop(self) -> None:
        running = self._running
        self._running = None
        if running is not None:
            self._driver.complete(running)
