from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, Optional

from .boundaries import AsyncDriver, AsyncType, RepeatingWork
from .scheduler import CallHandle, Scheduler, WhatT


class AlreadyRunning(Exception):
    """
    The timer is already running.
    """


class NotRunning(Exception):
    """
    The timer is not running.
    """


@dataclass
class Repeating(Generic[AsyncType, WhatT]):
    work: RepeatingWork
    _scheduler: Scheduler[float, Callable[[], None]]
    _driver: AsyncDriver[AsyncType]
    _running: Optional[AsyncType] = None
    _pending: Optional[CallHandle[float, Callable[[], None]]] = None

    @property
    def running(self) -> bool:
        return self._running is not None

    def _noLongerRunning(self) -> Optional[AsyncType]:
        running, self._running = self._running, None
        return running

    def start(self, interval: float, now: bool = True) -> AsyncType:
        if self._running is not None:
            raise AlreadyRunning(f"Repeating({self.work}) is already running.")
        self._running = self._driver.newWithCancel(self.stop)
        startTime = self._scheduler.now()
        last = 0

        def one() -> None:
            nonlocal last
            self._pending = None
            elapsed = self._scheduler.now() - startTime
            count = int(elapsed // interval)
            try:
                self.work(count - last)
            except BaseException:
                self._driver.unhandledError(self.work, self._noLongerRunning())
            else:
                last = count
                if self._running is not None:
                    self._pending = self._scheduler.callAt(
                        (interval * (count + 1)) + startTime, one
                    )

        if now:
            one()
        else:
            self._scheduler.callAt((interval) + startTime, one)
        return self._running

    def stop(self, raiseIfNotRunning: bool = True) -> None:
        if (running := self._noLongerRunning()) is not None:
            self._driver.complete(running)
        elif raiseIfNotRunning:
            raise NotRunning(
                f"Repeating({self.work}) is not currently running."
            )
