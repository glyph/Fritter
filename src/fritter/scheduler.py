# -*- test-case-name: fritter.test.test_scheduler -*-
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Generic, Iterator, TypeVar

from .boundaries import PriorityComparable, PriorityQueue, TimeDriver
from .heap import Heap

WhenT = TypeVar("WhenT", bound=PriorityComparable)
WhatT = TypeVar("WhatT", bound=Callable[[], None])

@dataclass(eq=True, order=True)
class FutureCall(Generic[WhenT, WhatT]):
    """
    A handle to a future call.

    @ivar when: When will this call be run?

    @ivar what: What work will this call perform?

    @ivar id: An ID, unique to the scheduler for identifying this call.
    """
    when: WhenT = field(compare=True)
    what: WhatT = field(compare=False)
    id: int = field(compare=True)
    called: bool = field(compare=False)
    canceled: bool = field(compare=False)
    _canceller: Callable[[FutureCall[WhenT, WhatT]], None]

    def cancel(self) -> None:
        if self.called:
            # nope
            return
        if self.canceled:
            # nope
            return
        self.canceled = True
        self._canceller(self)



@dataclass
class Scheduler(Generic[WhenT, WhatT]):
    """
    A L{Scheduler} allows for scheduling work (of the type C{WhatT}, which must
    be at least a 0-argument None-returning callable) at a given time
    (C{WhenT}, which much be sortable as a L{PriorityComparable}).

    @ivar driver: The L{TimeDriver} that this L{Scheduler} will use.
    """
    driver: TimeDriver[WhenT]
    _q: PriorityQueue[FutureCall[WhenT, WhatT]] = field(default_factory=Heap)
    _maxWorkBatch: int = 0xFF
    counter: int = 0

    def __post_init__(self) -> None:
        """
        Ensure that the supplied priority queue is initially empty.
        """
        if self._q.peek() is not None:
            raise ValueError("Priority queue must be initially empty.")

    def now(self) -> WhenT:
        """
        Relay C{now} to our L{TimeDriver}.
        """
        return self.driver.now()

    def calls(self) -> Iterator[FutureCall[WhenT, WhatT]]:
        """
        Iterate through all the L{FutureCall}s previously scheduled by this
        L{Scheduler}'s L{callAt <Scheduler.callAt>} method.
        """
        return iter(self._q)

    def callAt(self, when: WhenT, what: WhatT) -> FutureCall[WhenT, WhatT]:
        """
        Call C{what} at the time C{when} according to the L{TimeDriver}
        associated with this L{Scheduler}.

        @return: a L{CallHandle} that allows for cancellation of the pending
            call.
        """
        self.counter += 1

        def advanceToNow() -> None:
            timestamp = self.driver.now()
            workPerformed = 0
            while (
                (each := self._q.peek()) is not None
                and each.when <= timestamp
                and workPerformed < self._maxWorkBatch
            ):
                popped = self._q.get()
                assert popped is each
                # not sure if there's a more graceful way to put this
                # todo: failure handling
                each.called = True
                each.what()
                workPerformed += 1
            upNext = self._q.peek()
            if upNext is not None:
                self.driver.reschedule(upNext.when, advanceToNow)

        def _cancelCall(toRemove: FutureCall[WhenT, WhatT]) -> None:
            old = self._q.peek()
            self._q.remove(toRemove)
            new = self._q.peek()
            if new is None:
                self.driver.unschedule()
            elif old is None or new is not old:
                self.driver.reschedule(new.when, advanceToNow)

        previously = self._q.peek()
        call = FutureCall(when, what, self.counter, False, False, _cancelCall)
        self._q.add(call)
        currently = self._q.peek()
        # We just added a thing it can't be None even though peek has that
        # signature
        assert currently is not None
        if previously is None or previously.when != currently.when:
            self.driver.reschedule(currently.when, advanceToNow)
        return call



SimpleScheduler = Scheduler[float, Callable[[], None]]
