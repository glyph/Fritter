# -*- test-case-name: fritter.test.test_repeat -*-
"""
Schedule repeated invocations of a function, indicating how many steps have
been passed so that the repeated calls may catch up to real time to preserve
timing accuracy when timers cannot always be invoked promptly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Coroutine, Generic, TypeVar

from ..boundaries import (
    AsyncDriver,
    AsyncType,
    Cancellable,
    RecurrenceRule,
    RepeatingWork,
    Scheduler,
    SomeScheduledCall,
    StepsT,
    StepsTInv,
    WhatT,
    WhenT,
)


RepeatingWhatT = TypeVar("RepeatingWhatT", bound=RepeatingWork[object])
"""
A TypeVar for L{Repeater} to reference a specific type of L{RepeatingWork}.
"""


@dataclass
class Repeater(Generic[WhenT, WhatT, StepsT]):
    """
    A L{Repeater} can call a L{RepeatingWork} function repeatedly.

    @ivar scheduler: The scheduler where the work will be performed.

    @ivar rule: The L{RecurrenceRule} that defines the times at which C{work}
        will be invoked.

    @ivar work: The L{RepeatingWork} that will be performed.

    @ivar convert: Since a L{Scheduler} requires that any work provided be
        specifically of its C{WhatT} type, which may need to have some property
        associated with it beyond its function signature (for example,
        additional attributes for instrumentation or serialization), so this
        C{convert} function will convert this L{Repeater} into a 0-argument
        function that both:

            1. is of the appropriate L{WhatT} for C{scheduler}, and

            2. invokes this L{Repeater}'s C{repeat} method.

    @ivar reference: The current reference time, i.e. the time at which the
        next invocation of C{work} I{should} occur.
    """

    scheduler: Scheduler[WhenT, WhatT, object]
    rule: RecurrenceRule[WhenT, StepsT]
    work: RepeatingWork[StepsT]
    convert: Callable[[Repeater[WhenT, WhatT, StepsT]], WhatT]
    reference: WhenT

    @classmethod
    def new(
        cls,
        scheduler: Scheduler[WhenT, WhatT, object],
        rule: RecurrenceRule[WhenT, StepsT],
        work: RepeatingWork[StepsT],
        convert: Callable[[Repeater[WhenT, WhatT, StepsT]], WhatT],
        reference: WhenT | None = None,
    ) -> Repeater[WhenT, WhatT, StepsT]:
        """
        Create a L{Repeater}, filling out its reference time with the L{current
        time of the given scheduler <Scheduler.now>}, if no other time is
        provided.
        """
        if reference is None:
            reference = scheduler.now()
        return cls(scheduler, rule, work, convert, reference)

    def repeat(self) -> None:
        """
        Repeat the L{work <Repeater.work>} associated with this L{Repeater}.

        Applications should call this once, and only once, after the
        L{Repeater} is created, in order to kick off the repetition.  All
        future calls should be performed via the result of C{convert} being
        called in the scheduler, or the timing of repeated invocations will be
        incorrect.
        """
        now = self.scheduler.now()
        callIncrement, self.reference = self.rule(self.reference, now)
        callRepeat = self.convert(self)
        stopHandle = self.scheduler.callAt(self.reference, callRepeat)
        self.work(callIncrement, stopHandle)


def repeatedly(
    scheduler: Scheduler[WhenT, Callable[[], None], object],
    work: RepeatingWork[StepsT],
    rule: RecurrenceRule[WhenT, StepsT],
) -> None:
    """
    Create a L{Repeater} and call its C{repeat} method.  This is a utility
    function for use when you have a simple repetition set up on a scheduler
    that accepts a baseline 0-argument callable, and does not require any
    L{conversion <Repeater.convert>}.
    """
    Repeater.new(scheduler, rule, work, lambda r: r.repeat).repeat()


@dataclass
class _AsyncStopper(Generic[AsyncType]):
    """
    An implementation of L{Cancellable} which can stop the repetition kicked
    off by L{Async.repeatedly}.
    """

    driver: AsyncDriver[AsyncType]
    result: AsyncType
    timeInProgress: Cancellable | None = None
    asyncInProgress: Cancellable | None = None
    shouldComplete: bool = True

    def cancel(self) -> None:
        if self.timeInProgress is not None:
            self.timeInProgress.cancel()
        if self.asyncInProgress is not None:
            self.asyncInProgress.cancel()
        if self.shouldComplete:
            self.driver.complete(self.result)


@dataclass
class Async(Generic[AsyncType]):
    """
    An L{Async} wraps an L{AsyncDriver} and provides an implementation of
    L{repeatedly} which:

        1. C{await}s each result from its async C{work} callable, so that no
           overlapping work will be performed if an asynchronous operation
           takes longer than the repetition interval,

        2. returns an awaitable that fires when C{stopper.cancel()} has been
           called on the C{stopper} provided to that callable, and

        3. provides a C{.cancel()} implementation on that returned awaitable
           which stops any in-progress async work and raises the appropriate
           cancellation error for your framework back to the caller.

    @ivar asyncDriver: The driver that supplies awaitables for this L{Async} to
        return.
    """

    asyncDriver: AsyncDriver[AsyncType]

    def repeatedly(
        self,
        scheduler: Scheduler[WhenT, Callable[[], None], object],
        rule: RecurrenceRule[WhenT, StepsTInv],
        work: Callable[
            [StepsTInv, Cancellable],
            AsyncType | Coroutine[AsyncType, Any, Any],
        ],
    ) -> AsyncType:
        """
        Kick off a repeated call within the given scheduler, returning an
        L{AsyncType} (i.e. L{Future <asyncio.Future>}, L{Deferred
        <twisted.internet.defer.Deferred>}, or similar, as defined by
        L{Async.asyncDriver}).

        If you call C{.cancel()} on the result of this method, the repetition
        will be stopped and a cancellation error will be signaled to the
        caller.  If, instead, C{work} calls its C{.cancel()} method, then the
        result of this method will complete successfully, returning C{None} to
        a coroutine awaiting it.
        """

        cancelled = False

        def reallyCancel() -> None:
            nonlocal cancelled
            cancelled = True
            asyncStopper.shouldComplete = False
            asyncStopper.cancel()

        asyncStopper: _AsyncStopper[AsyncType] = _AsyncStopper(
            self.asyncDriver,
            self.asyncDriver.newWithCancel(reallyCancel),
        )

        def complete() -> None:
            asyncStopper.asyncInProgress = None
            if asyncStopper.timeInProgress is None and not cancelled:
                repeater.repeat()

        def kickoff(steps: StepsTInv, scheduled: SomeScheduledCall) -> None:
            asyncStopper.timeInProgress = scheduled
            completedSynchronously: bool = False

            async def coro() -> None:
                nonlocal completedSynchronously
                try:
                    await work(steps, asyncStopper)
                finally:
                    if asyncStopper.asyncInProgress is None:
                        completedSynchronously = True
                    else:
                        complete()

            asyncStopper.asyncInProgress = self.asyncDriver.runAsync(coro())
            if completedSynchronously:
                complete()

        def whenReady() -> None:
            asyncStopper.timeInProgress = None
            if asyncStopper.asyncInProgress is None:
                repeater.repeat()

        repeater = Repeater.new(scheduler, rule, kickoff, lambda r: whenReady)
        repeater.repeat()

        return asyncStopper.result
