# -*- test-case-name: fritter.test.test_repeat -*-
"""
Schedule repeated invocations of a function, indicating how many steps have
been passed so that the repeated calls may catch up to real time to preserve
timing accuracy when timers cannot always be invoked promptly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import IntEnum
from typing import (
    Any,
    Callable,
    Coroutine,
    Generic,
    Protocol,
    TypeVar,
)
from zoneinfo import ZoneInfo

from datetype import DateTime

from .boundaries import (
    AsyncDriver,
    AsyncType,
    Cancellable,
    RepeatingWork,
    StepsT,
)
from .scheduler import Scheduler, WhatT, WhenT

StepsTInv = TypeVar("StepsTInv")


class RecurrenceRule(Protocol[WhenT, StepsT]):
    """
    A L{RecurrenceRule} is a callable that takes a reference time and a current
    time, and computes series of steps between the current recurrence and a new
    reference time for the next call.

    Depending on the application, C{StepsT} type can either be an integer
    (i.e.: a count of the number of steps that have passed between the
    reference time and the current time) or a collection of specific previous
    step timestamps, usually a collection of C{WhenT}.
    """

    def __call__(
        self, reference: WhenT, current: WhenT
    ) -> tuple[StepsT, WhenT]:
        """
        Given a reference time and a current time, compute the steps between
        the calls and the next reference time.

        @param reference: the time at which the current invocation was
            I{scheduled} to occur; i.e. the time that the call was computed to
            have been called.

        @param current: the time at which the current invocation I{actually}
            occurred; i.e. the time that the event loop got around to actually
            calling the function.

        @note: The delta between the reference time and the current time will
            I{often} be quite small.  If a system is running actively and is
            not overloaded, then this delta will be close to zero.  However,
            there are cases (some examples: a laptop goes to sleep, then wakes
            up hours later; a program schedules a call in a database and is not
            run for several weeks) when this delta can be very large.

        @return: a 2-tuple of:

                1. I{steps}; the recurrences that were expected to have
                   occurred between C{reference} and the I{current time}.  So
                   for example, for a L{RecurrenceRule} representing a
                   once-every-5-seconds recurrence, if your reference time were
                   1.0 and your current time were 15.0, then your step count
                   should be 2, since recurrences should have occurred at 6.0
                   and 11.0.  Alternately, for a C{RecurrenceRule[float,
                   list[float]]} with the same scheduled times, C{steps} will
                   be C{[6.0, 11.0]}.

                2. I{next reference time}; time at which the next recurrence
                   I{should} occur.  In our previous example, where our
                   reference time was 1.0 and current time was 15.0, the next
                   desired time should be 16.0, since that's the next 5-second
                   recurrence after 11.0.
        """


RepeatingWhatT = TypeVar("RepeatingWhatT", bound=RepeatingWork[object])
"""
A TypeVar for L{Repeater} to reference a specific type of L{RepeatingWork}.
"""

DTRule = RecurrenceRule[DateTime[ZoneInfo], int]
"""
A type alias to describe a recurrence rule function that operates on aware
datetimes.
"""


@dataclass(frozen=True)
class EveryDelta:
    """
    An L{EveryDelta} is a L{RecurrenceRule} based on a L{timedelta}, that can
    cause civil times to repeat.

    @ivar delta: the time delta between recurrences
    """

    delta: timedelta

    def __call__(
        self,
        reference: DateTime[ZoneInfo],
        current: DateTime[ZoneInfo],
    ) -> tuple[int, DateTime[ZoneInfo]]:
        """
        Compute a step count and next desired recurrence time based on a
        reference time and a current time in aware datetimes, and the timedelta
        in C{self.delta}.

        @see: L{RecurrenceRule}
        """
        count = 0
        nextDesired = reference
        while nextDesired <= current:
            count += 1
            nextDesired += self.delta
        return count, nextDesired


@dataclass
class EverySecond:
    """
    An L{EveryDelta} is a L{RecurrenceRule} based on a L{timedelta}, that can
    cause civil times to repeat.

    @ivar seconds: the number of seconds between recurrences.
    """

    seconds: float

    def __call__(self, reference: float, current: float) -> tuple[int, float]:
        """
        Compute a step count and next desired recurrence time based on a
        reference time and a current time in floating-point POSIX timestamps
        like those returned by L{time.time} and L{datetime.datetime.timestamp},
        and number of seconds in L{self.seconds <EverySecond.seconds>}.

        @see: L{RecurrenceRule}
        """
        elapsed = current - reference
        count, remainder = divmod(elapsed, self.seconds)
        return int(count) + 1, current + (self.seconds - remainder)


weekly: DTRule = EveryDelta(timedelta(weeks=1))
"""
Weekly datetime-based delta.
"""


class Day(IntEnum):
    Monday = 0
    Tuesday = 1
    Wednesday = 2
    Thursday = 3
    Friday = 4
    Saturday = 5
    Sunday = 6


@dataclass
class CustomWeekly:
    days: set[Day]
    hour: int
    minute: int
    second: int = 0


def customWeekly(
    days: set[Day], hour: int, minute: int, second: int = 0
) -> RecurrenceRule[DateTime[ZoneInfo], list[DateTime[ZoneInfo]]]:
    """
    Repeat every week, on each weekday in the given set of C{days}, at the
    given C{hour}, C{minute}, and C{second}.
    """
    sdays = sorted([day.value for day in days])
    assert days, "cannot pass an empty set of days"

    def _(
        reference: DateTime[ZoneInfo], current: DateTime[ZoneInfo]
    ) -> tuple[list[DateTime[ZoneInfo]], DateTime[ZoneInfo]]:
        steps: list[DateTime[ZoneInfo]] = []
        refDay = reference.date().weekday()
        weekOffset = 0
        while True:
            for sday in sdays:
                daydelta = timedelta(days=(weekOffset + sday) - refDay)
                candidate = (reference + daydelta).replace(
                    hour=hour, minute=minute, second=second, microsecond=0
                )

                if candidate < reference:
                    # earlier than the reference time, let's ignore
                    continue

                if candidate <= current:
                    # after the reference time but before the current time,
                    # record as a missed step, then continue
                    steps.append(candidate)
                    continue

                # it's after the reference *and* after the current time, we're
                # done
                return steps, candidate
            weekOffset += 7

    return _


daily: DTRule = EveryDelta(timedelta(days=1))
"""
Daily datetime-based rule.
"""

hourly: DTRule = EveryDelta(timedelta(hours=1))
"""
Hourly datetime-based rule.
"""

_everyIsRecurrenceRule: Callable[[float], RecurrenceRule[float, int]]
_everyIsRecurrenceRule = EverySecond


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

    scheduler: Scheduler[WhenT, WhatT]
    rule: RecurrenceRule[WhenT, StepsT]
    work: RepeatingWork[StepsT]
    convert: Callable[[Repeater[WhenT, WhatT, StepsT]], WhatT]
    reference: WhenT

    @classmethod
    def new(
        cls,
        scheduler: Scheduler[WhenT, WhatT],
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
    scheduler: Scheduler[WhenT, Callable[[], None]],
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
        scheduler: Scheduler[WhenT, Callable[[], None]],
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

        def kickoff(steps: StepsTInv, stopper: Cancellable) -> None:
            asyncStopper.timeInProgress = stopper
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
