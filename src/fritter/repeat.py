# -*- test-case-name: fritter.test.test_repeat -*-
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Callable, Coroutine, Generic, TypeVar
from zoneinfo import ZoneInfo

from datetype import DateTime

from fritter.boundaries import Cancellable

from .boundaries import AsyncDriver, AsyncType, RepeatingWork
from .scheduler import Scheduler, WhatT, WhenT

RuleFunction = Callable[[WhenT, WhenT], tuple[int, WhenT]]
RepeatingWhatT = TypeVar("RepeatingWhatT", bound=RepeatingWork)
AnyWhat = Callable[[], None]
DTZ = DateTime[ZoneInfo]
DTRule = RuleFunction[DTZ]


@dataclass(frozen=True)
class EveryDelta:
    delta: timedelta

    def __call__(self, reference: DTZ, current: DTZ) -> tuple[int, DTZ]:
        count = 0
        nextDesired = reference
        while nextDesired <= current:
            count += 1
            nextDesired += self.delta
        return count, nextDesired


@dataclass
class EverySecond:
    seconds: float

    def __call__(self, reference: float, current: float) -> tuple[int, float]:
        elapsed = current - reference
        count, remainder = divmod(elapsed, self.seconds)
        return int(count) + 1, current + (self.seconds - remainder)


weekly: DTRule = EveryDelta(timedelta(weeks=1))
daily: DTRule = EveryDelta(timedelta(days=1))
hourly: DTRule = EveryDelta(timedelta(hours=1))

_everyIsRuleFunction: Callable[[float], RuleFunction[float]]
_everyIsRuleFunction = EverySecond


@dataclass
class Repeater(Generic[WhenT, WhatT, RepeatingWhatT]):
    scheduler: Scheduler[WhenT, WhatT]
    rule: RuleFunction[WhenT]
    work: RepeatingWhatT
    convert: Callable[[Repeater[WhenT, WhatT, RepeatingWhatT]], WhatT]
    reference: WhenT

    @classmethod
    def new(
        cls,
        scheduler: Scheduler[WhenT, WhatT],
        rule: RuleFunction[WhenT],
        work: RepeatingWhatT,
        convert: Callable[[Repeater[WhenT, WhatT, RepeatingWhatT]], WhatT],
        reference: WhenT | None = None,
    ) -> Repeater[WhenT, WhatT, RepeatingWhatT]:
        if reference is None:
            reference = scheduler.now()
        return cls(scheduler, rule, work, convert, reference)

    def repeat(self) -> None:
        now = self.scheduler.now()
        callIncrement, self.reference = self.rule(self.reference, now)
        callRepeat = self.convert(self)
        self.work(
            callIncrement, self.scheduler.callAt(self.reference, callRepeat)
        )


def repeatedly(
    scheduler: Scheduler[WhenT, Callable[[], None]],
    work: RepeatingWork,
    rule: RuleFunction[WhenT],
) -> None:
    Repeater.new(scheduler, rule, work, lambda r: r.repeat).repeat()


@dataclass
class AsyncStopper(Generic[AsyncType]):
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
    asyncDriver: AsyncDriver[AsyncType]

    def repeatedly(
        self,
        scheduler: Scheduler[WhenT, AnyWhat],
        rule: RuleFunction[WhenT],
        work: Callable[
            [int, Cancellable], AsyncType | Coroutine[AsyncType, Any, Any]
        ],
    ) -> AsyncType:
        def reallyCancel() -> None:
            asyncStopper.shouldComplete = False
            asyncStopper.cancel()

        asyncStopper: AsyncStopper[AsyncType] = AsyncStopper(
            self.asyncDriver,
            self.asyncDriver.newWithCancel(reallyCancel),
        )

        def complete() -> None:
            asyncStopper.asyncInProgress = None
            if asyncStopper.timeInProgress is None:
                repeater.repeat()

        def kickoff(steps: int, stopper: Cancellable) -> None:
            asyncStopper.timeInProgress = stopper

            if asyncStopper.asyncInProgress is not None:
                return

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
