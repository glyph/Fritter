# -*- test-case-name: fritter.test.test_scheduler -*-
"""
A L{Scheduler} is the core interface of Fritter; a collection of timed calls
scheduled by L{callAt <Scheduler.callAt>} connected to a L{TimeDriver} that
causes them to actually be called.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import count
from typing import Callable, Generic, TypeAlias, overload

from .boundaries import IDT, PriorityQueue, Scheduler, TimeDriver, WhatT, WhenT
from .heap import Heap


@dataclass(eq=True, order=True)
class ScheduledCall(Generic[WhenT, WhatT, IDT]):
    """
    A handle to a future call.

    @ivar when: When will this call be run?

    @ivar what: What work will this call perform?

    @ivar id: An identifier unique to the scheduler for identifying this call.
    """

    when: WhenT = field(compare=True)
    what: WhatT = field(compare=False)
    id: IDT = field(compare=True)
    called: bool = field(compare=False)
    canceled: bool = field(compare=False)
    _canceller: Callable[[ScheduledCall[WhenT, WhatT, IDT]], None] = field(
        compare=False
    )

    def cancel(self) -> None:
        """
        Cancel this L{ScheduledCall}, making it so that it will not be invoked
        in the future.  If the work described by C{when} has already been
        called, or this call has already been cancelled, do nothing.
        """
        if self.called:
            # nope
            return
        if self.canceled:
            # nope
            return
        self.canceled = True
        self._canceller(self)


CallScheduler: TypeAlias = Scheduler[
    WhenT, WhatT, ScheduledCall[WhenT, WhatT, IDT]
]


@dataclass
class _HeapSchedulerImpl(Generic[WhenT, WhatT, IDT]):
    """
    A L{Scheduler} allows for scheduling work (of the type C{WhatT}, which must
    be at least a 0-argument None-returning callable) at a given time
    (C{WhenT}, which much be sortable as a L{PriorityComparable}).

    @ivar driver: The L{TimeDriver} that this L{Scheduler} will use.
    """

    driver: TimeDriver[WhenT]
    _newID: Callable[[], IDT]
    _q: PriorityQueue[ScheduledCall[WhenT, WhatT, IDT]]
    _maxWorkBatch: int = 0xFF

    def now(self) -> WhenT:
        """
        Relay C{now} to our L{TimeDriver}.
        """
        return self.driver.now()

    def callAt(
        self, when: WhenT, what: WhatT
    ) -> ScheduledCall[WhenT, WhatT, IDT]:
        """
        Call C{what} at the time C{when} according to the L{TimeDriver}
        associated with this L{Scheduler}.

        @return: a L{ScheduledCall} that describes the pending call and allows
            for cancelling it.
        """

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

        def _cancelCall(toRemove: ScheduledCall[WhenT, WhatT, IDT]) -> None:
            old = self._q.peek()
            self._q.remove(toRemove)
            new = self._q.peek()
            if new is None:
                self.driver.unschedule()
            elif old is None or new is not old:
                self.driver.reschedule(new.when, advanceToNow)

        previously = self._q.peek()
        call = ScheduledCall(
            when, what, self._newID(), False, False, _cancelCall
        )
        self._q.add(call)
        currently = self._q.peek()
        # We just added a thing it can't be None even though peek has that
        # signature
        assert currently is not None
        if previously is None or previously.when != currently.when:
            self.driver.reschedule(currently.when, advanceToNow)
        return call


_TypeCheck: type[
    Scheduler[
        float,
        Callable[[], None],
        ScheduledCall[float, Callable[[], None], int],
    ]
] = _HeapSchedulerImpl


@overload
def newScheduler(
    driver: TimeDriver[WhenT],
    nextID: Callable[[], IDT],
    queue: PriorityQueue[ScheduledCall[WhenT, WhatT, IDT]] | None = None,
) -> CallScheduler[WhenT, WhatT, IDT]: ...


@overload
def newScheduler(
    driver: TimeDriver[WhenT],
    *,
    queue: PriorityQueue[ScheduledCall[WhenT, WhatT, int]] | None = None,
) -> CallScheduler[WhenT, WhatT, int]: ...


def newScheduler(
    driver: TimeDriver[WhenT],
    nextID: Callable[[], IDT] | None = None,
    queue: PriorityQueue[ScheduledCall[WhenT, WhatT, IDT]] | None = None,
) -> CallScheduler[WhenT, WhatT, IDT]:
    """
    Create a new in-memory scheduler.

    @param driver: The L{TimeDriver} to use for the new scheduler.

    @param queue: If desired, a custom L{PriorityQueue} implementation.  By
        default, a new L{Heap} will be used.

    @param nextID: A callable that will generate new opaque IDs.  By default,
        sequential integers will be used.
    """
    if nextID is None:
        nextCounter = count().__next__
        nextID = nextCounter  # type:ignore[assignment]
        assert nextID is not None
    if queue is None:
        queue = Heap()
    return _HeapSchedulerImpl(driver, nextID, queue)


__all__ = [
    "ScheduledCall",
    "newScheduler",
    "CallScheduler",
]
