# -*- test-case-name: fritter.test.test_scheduler -*-
"""
A L{Scheduler} is the core interface of Fritter; a collection of timed calls
scheduled by L{callAt <Scheduler.callAt>} connected to a L{TimeDriver} that
causes them to actually be called.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import count
from typing import Callable, Generic, overload

from .boundaries import (
    IDT,
    PriorityQueue,
    ScheduledCall,
    ScheduledState,
    Scheduler,
    TimeDriver,
    WhatT,
    WhenT,
)
from .heap import Heap


@dataclass(eq=True, order=True)
class ConcreteScheduledCall(Generic[WhenT, WhatT, IDT]):
    """
    A handle to a call that has been scheduled.
    """

    _when: WhenT = field(compare=True)
    _what: WhatT | None = field(compare=False)
    _id: IDT = field(compare=True)

    _called: bool = field(compare=False)
    _cancelled: bool = field(compare=False)
    _canceller: (
        Callable[[ConcreteScheduledCall[WhenT, WhatT, IDT]], None] | None
    ) = field(compare=False)

    def _call(self) -> None:
        """
        Invoke the callable and adjust the state.
        """
        assert self._what is not None, "ScheduledCall invoked twice."
        self._called = True
        try:
            self._what()
        finally:
            self._what = None

    @property
    def id(self) -> IDT:
        """
        Return a unique identifier for this scheduled call.
        """
        return self._id

    @property
    def when(self) -> WhenT:
        """
        Return the original time at which the call will be scheduled.
        """
        return self._when

    @property
    def what(self) -> WhatT | None:
        """
        If this has not been called or cancelled, return the original callable
        that was scheduled.

        @note: To break cycles, this will only have a non-C{None} value when in
            L{ScheduledState.pending}.
        """
        return self._what

    @property
    def state(self) -> ScheduledState:
        """
        Is this call still waiting to be called, or has it been called or
        cancelled?
        """
        if self._cancelled:
            return ScheduledState.cancelled
        if self._called:
            return ScheduledState.called
        assert self._what is not None
        return ScheduledState.pending

    def cancel(self) -> None:
        """
        Cancel this L{ScheduledCall}, making it so that it will not be invoked
        in the future.  If the work described by C{when} has already been
        called, or this call has already been cancelled, do nothing.
        """
        if self._canceller is None:
            return
        self._cancelled = True
        try:
            self._canceller(self)
        finally:
            self._canceller = None


@dataclass
class _PriorityQueueBackedSchedulerImpl(Generic[WhenT, WhatT, IDT]):
    """
    A L{Scheduler} allows for scheduling work (of the type C{WhatT}, which must
    be at least a 0-argument None-returning callable) at a given time
    (C{WhenT}, which much be sortable as a L{PriorityComparable}).

    @ivar driver: The L{TimeDriver} that this L{Scheduler} will use.
    """

    driver: TimeDriver[WhenT]
    _newID: Callable[[], IDT]
    _q: PriorityQueue[ConcreteScheduledCall[WhenT, WhatT, IDT]]
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
                and each._when <= timestamp
                and workPerformed < self._maxWorkBatch
            ):
                popped = self._q.get()
                assert popped is each
                each._call()
                workPerformed += 1
            upNext = self._q.peek()
            if upNext is not None:
                self.driver.reschedule(upNext._when, advanceToNow)

        def _cancelCall(
            toRemove: ConcreteScheduledCall[WhenT, WhatT, IDT]
        ) -> None:
            old = self._q.peek()
            self._q.remove(toRemove)
            new = self._q.peek()
            if new is None:
                self.driver.unschedule()
            elif old is None or new is not old:
                self.driver.reschedule(new._when, advanceToNow)

        previously = self._q.peek()
        call = ConcreteScheduledCall(
            when, what, self._newID(), False, False, _cancelCall
        )
        self._q.add(call)
        currently = self._q.peek()
        # We just added a thing it can't be None even though peek has that
        # signature
        assert currently is not None
        if previously is None or previously._when != currently._when:
            self.driver.reschedule(currently._when, advanceToNow)
        return call


_TypeCheck: type[Scheduler[float, Callable[[], None], int]] = (
    _PriorityQueueBackedSchedulerImpl
)


@overload
def schedulerFromDriver(
    driver: TimeDriver[WhenT],
    nextID: Callable[[], IDT],
    queue: (
        PriorityQueue[ConcreteScheduledCall[WhenT, WhatT, IDT]] | None
    ) = None,
) -> Scheduler[WhenT, WhatT, IDT]: ...


@overload
def schedulerFromDriver(
    driver: TimeDriver[WhenT],
    *,
    queue: (
        PriorityQueue[ConcreteScheduledCall[WhenT, WhatT, int]] | None
    ) = None,
) -> Scheduler[WhenT, WhatT, int]: ...


def schedulerFromDriver(
    driver: TimeDriver[WhenT],
    nextID: Callable[[], IDT] | None = None,
    queue: (
        PriorityQueue[ConcreteScheduledCall[WhenT, WhatT, IDT]] | None
    ) = None,
) -> Scheduler[WhenT, WhatT, IDT]:
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
        # I really just want https://peps.python.org/pep-0696/ here (the
        # default type for "IDT" is "int", "nextCounter" is Callable[, int]
        # where we want a Callable[, IDT] and there's no way to tell mypy those
        # are the same but only in this case), but we'll have to wait for
        # Python 3.13.
        nextID = nextCounter  # type:ignore[assignment]
        assert (
            nextID is not None
        ), "itertools.count.__next__ just isn't None, but mypy can't tell"
    return _PriorityQueueBackedSchedulerImpl[WhenT, WhatT, IDT](
        driver, nextID, Heap() if queue is None else queue
    )


__all__ = [
    "ConcreteScheduledCall",
    "schedulerFromDriver",
]
