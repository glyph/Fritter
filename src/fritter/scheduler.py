# -*- test-case-name: fritter.test.test_scheduler -*-
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import count
from typing import Callable, Generic, Iterator, TypeVar

from .boundaries import PriorityComparable, PriorityQueue, TimeDriver
from .heap import Heap

WhenT = TypeVar("WhenT", bound=PriorityComparable)
WhatT = TypeVar("WhatT", bound=Callable[[], None])

callID = count()


@dataclass(eq=True, order=True)
class FutureCall(Generic[WhenT, WhatT]):
    when: WhenT = field(compare=True)
    what: WhatT = field(compare=False)
    id: int = field(compare=True, default_factory=lambda: next(callID))
    called: bool = field(compare=False, default=False)
    canceled: bool = field(compare=False, default=False)


@dataclass
class CallHandle(Generic[WhenT, WhatT]):
    call: FutureCall[WhenT, WhatT]
    _canceller: Callable[[FutureCall[WhenT, WhatT]], None]

    def cancel(self) -> None:
        if self.call.called:
            # nope
            return
        if self.call.canceled:
            # nope
            return
        self.call.canceled = True
        self._canceller(self.call)


@dataclass(frozen=True)
class Scheduler(Generic[WhenT, WhatT]):
    driver: TimeDriver[WhenT]
    _q: PriorityQueue[FutureCall[WhenT, WhatT]] = field(default_factory=Heap)

    def __post_init__(self) -> None:
        if self._q.peek() is not None:
            raise ValueError("Priority queue must be initially empty.")

    def now(self) -> WhenT:
        return self.driver.now()

    def calls(self) -> Iterator[FutureCall[WhenT, WhatT]]:
        return iter(self._q)

    def callAt(self, when: WhenT, what: WhatT) -> CallHandle[WhenT, WhatT]:
        call = FutureCall(when, what)

        def _cancelCall(toRemove: FutureCall[WhenT, WhatT]) -> None:
            old = self._q.peek()
            self._q.remove(toRemove)
            new = self._q.peek()
            if new is None:
                self.driver.unschedule()
            elif old is None or new is not old:
                self.driver.reschedule(new.when, self._advanceToNow)

        previously = self._q.peek()
        self._q.add(call)
        currently = self._q.peek()
        # We just added a thing it can't be None even though peek has that
        # signature
        assert currently is not None
        if previously is None or previously.when != currently.when:
            self.driver.reschedule(currently.when, self._advanceToNow)
        return CallHandle(call, _cancelCall)

    def _advanceToNow(self) -> None:
        timestamp = self.driver.now()
        while (each := self._q.peek()) is not None and each.when <= timestamp:
            popped = self._q.get()
            assert popped is each
            # not sure if there's a more graceful way to put this
            # todo: failure handling
            each.called = True
            each.what()
        upNext = self._q.peek()
        if upNext is not None:
            self.driver.reschedule(upNext.when, self._advanceToNow)


SimpleScheduler = Scheduler[float, Callable[[], None]]
