from __future__ import annotations

from dataclasses import dataclass, field
from itertools import count
from typing import Callable, Generic, TypeVar

from .boundaries import Driver, PriorityComparable, PriorityQueue

T = TypeVar("T", bound=PriorityComparable)

callID = count()


@dataclass(eq=True, order=True)
class FutureCall(Generic[T]):
    when: T = field(compare=True)
    what: Callable[[], None] = field(compare=False)
    id: int = field(compare=True, default_factory=lambda: next(callID))
    called: bool = field(compare=False, default=False)
    canceled: bool = field(compare=False, default=False)


@dataclass
class CallHandle(Generic[T]):
    call: FutureCall[T]
    _scheduler: Scheduler

    def cancel(self):
        if self.call.called:
            # nope
            return
        if self.call.canceled:
            # nope
            return
        self.call.canceled = True
        old = self.scheduler._q.peek()
        self.scheduler._q.remove(self.call)
        new = self.scheduler._q.peek()

        if new is None:
            self.scheduler._q.unschedule()
        elif old is None or new is not old:
            self.scheduler._q.reschedule(new.when, self.scheduler._advanceToNow)


@dataclass
class Scheduler:
    _q: PriorityQueue[FutureCall[float]]
    _driver: Driver

    def currentTimestamp(self) -> float:
        return self._driver.currentTimestamp()

    def callAtTimestamp(
        self, when: float, what: Callable[[], None]
    ) -> CallHandle[float]:
        call = FutureCall(when, what)
        previously = self._q.peek()
        self._q.add(call)
        currently = self._q.peek()
        # We just added a thing it can't be None even though peek has that
        # signature
        assert currently is not None
        if previously is None or previously.when <= currently.when:
            self._driver.reschedule(currently.when, self._advanceToNow)
        return CallHandle(call, self)

    def _advanceToNow(self) -> None:
        timestamp = self._driver.currentTimestamp()
        while (each := self._q.peek()) is not None and timestamp > each.when:
            popped = self._q.get()
            assert popped is each  # not sure if there's a more graceful way to put this
            # todo: failure handling
            each.what()
        upNext = self._q.peek()
        if upNext is not None:
            self._driver.reschedule(upNext.when, self._advanceToNow)
