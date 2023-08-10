from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Callable, Generic, TypeVar
from zoneinfo import ZoneInfo

from datetype import DateTime

from .boundaries import AsyncDriver, AsyncType, RepeatingWork
from .scheduler import CallHandle, Scheduler, WhatT, WhenT

RuleFunction = Callable[[WhenT, WhenT], tuple[int, WhenT]]
RepeatingWhatT = TypeVar("RepeatingWhatT", bound=RepeatingWork)
AnyWhat = Callable[[], None]
DTZ = DateTime[ZoneInfo]
DTRule = RuleFunction[DTZ]


@dataclass
class Repeating(Generic[WhenT, WhatT, RepeatingWhatT]):
    reference: WhenT
    rule: RuleFunction[WhenT]
    callable: RepeatingWhatT
    convert: Callable[[Repeating[WhenT, WhatT, RepeatingWhatT]], WhatT]
    scheduler: Scheduler[WhenT, WhatT]

    def repeat(self) -> CallHandle[WhenT, WhatT]:
        callIncrement, self.reference = self.rule(
            self.reference, self.scheduler.now()
        )
        callRepeat = self.convert(self)
        self.callable(callIncrement)
        return self.scheduler.callAt(self.reference, callRepeat)


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
        count, remainder = divmod(reference - current, self.seconds)
        return int(count), current + (self.seconds - remainder)


weekly: DTRule = EveryDelta(timedelta(weeks=1))
daily: DTRule = EveryDelta(timedelta(days=1))
hourly: DTRule = EveryDelta(timedelta(hours=1))

_everyIsRuleFunction: Callable[[float], RuleFunction[float]]
_everyIsRuleFunction = EverySecond


def repeatAsync(
    work: Callable[[int], AsyncType],
    rule: RuleFunction[WhenT],
    asyncDriver: AsyncDriver[AsyncType],
    scheduler: Scheduler[WhenT, AnyWhat],
) -> AsyncType:
    currentlyRunning: bool = False
    awaitingRepeatence: bool = False
    pendingRepeat = None
    pendingAsync = None

    def doRepeat() -> None:
        nonlocal pendingRepeat
        pendingRepeat = repeating.repeat()

    def stop() -> None:
        if pendingRepeat is not None:
            pendingRepeat.cancel()
        if pendingAsync is not None:
            pendingAsync.cancel()
        if result is not None:
            asyncDriver.complete(result)

    def someWork(steps: int) -> None:
        nonlocal pendingAsync

        async def coro() -> None:
            nonlocal currentlyRunning, awaitingRepeatence, pendingAsync
            currentlyRunning = True
            try:
                await work(steps)
            finally:
                pendingAsync = None
                currentlyRunning = False
                if awaitingRepeatence:
                    awaitingRepeatence = False
                    doRepeat()

        pendingAsync = asyncDriver.runAsync(coro())

    def repeatWhenDone() -> None:
        nonlocal awaitingRepeatence
        if currentlyRunning:
            awaitingRepeatence = True
        else:
            doRepeat()

    now = scheduler.driver.now()
    repeating = Repeating(
        now, rule, someWork, lambda _: repeatWhenDone, scheduler
    )
    result = asyncDriver.newWithCancel(stop)
    doRepeat()
    return result
