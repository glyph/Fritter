from datetime import datetime
from itertools import chain
from typing import Any, Callable
from unittest import TestCase
from zoneinfo import ZoneInfo

from datetype import DateTime
from twisted.internet.defer import CancelledError, Deferred, succeed

from ..boundaries import Cancellable, Day, RecurrenceRule
from ..drivers.datetime import DateTimeDriver
from ..drivers.memory import MemoryDriver
from ..drivers.twisted import TwistedAsyncDriver
from ..repeat import Async, repeatedly
from ..repeat.rules.datetimes import EachWeekOn
from ..repeat.rules.seconds import EverySecond
from ..scheduler import Scheduler


class RepeatTestCase(TestCase):
    def test_synchronous(self) -> None:
        mem = MemoryDriver()
        calls = []

        def work(steps: int, stopper: Cancellable) -> None:
            now = mem.now()
            if mem.now() >= 10.0:
                stopper.cancel()
            calls.append((steps, now))

        repeatedly(Scheduler(mem), work, EverySecond(5))

        self.assertTrue(mem.isScheduled())
        self.assertEqual(calls, [(1, 0.0)])
        calls = []
        mem.advance()
        self.assertTrue(mem.isScheduled())
        self.assertEqual(calls, [(1, 5.0)])
        calls = []
        mem.advance()
        self.assertFalse(mem.isScheduled())
        self.assertEqual(calls, [(1, 10.0)])

    def test_repeatEveryIntervalInSeconds(self) -> None:
        tad = TwistedAsyncDriver()
        mem = MemoryDriver()
        count = 0
        calls = []
        event: Deferred[None] = succeed(None)

        async def tick(times: int) -> None:
            nonlocal count, event
            calls.append(f"before {count} ({times})")
            event = Deferred()
            await event
            calls.append(f"after {count}")
            count += 1

        Async(tad).repeatedly(
            Scheduler(mem),
            EverySecond(15),
            lambda times, stopper: tick(times),
        )

        self.assertEqual(calls, ["before 0 (1)"])
        event.callback(None)
        self.assertEqual(calls, ["before 0 (1)", "after 0"])
        del calls[:]
        mem.advance(15.3)
        self.assertEqual(calls, ["before 1 (1)"])
        del calls[:]
        # async operation takes 45 seconds. it's now 60.3.
        mem.advance(45.0)
        self.assertEqual(calls, [])
        event.callback(None)
        # catch-up call is immediately scheduled
        self.assertEqual(calls, ["after 1", "before 2 (3)"])
        del calls[:]
        event.callback(None)
        self.assertEqual(calls, ["after 2"])

    def test_complete(self) -> None:
        count = 0
        threshold = 3

        def step(steps: int, stopper: Cancellable) -> Deferred[None]:
            nonlocal count
            count += steps
            if count >= threshold:
                stopper.cancel()
            return succeed(None)

        tad = TwistedAsyncDriver()
        mem = MemoryDriver()
        done = False

        async def task() -> None:
            nonlocal done
            await Async(tad).repeatedly(Scheduler(mem), EverySecond(1), step)
            done = True

        tad.runAsync(task())
        for ignored in range(threshold):
            mem.advance()
        self.assertTrue(done)
        self.assertEqual(count, threshold)

    def test_cancel(self) -> None:
        tad = TwistedAsyncDriver()
        mem = MemoryDriver()
        succeeding: int = 0
        repeatCall: Deferred[None] | None = None
        pending: Deferred[None]

        def canceled(d: Deferred[None]) -> None:
            return

        pending = Deferred(canceled)

        async def bonk(d: Deferred[None]) -> None:
            # odd idiom for suppressing cancellation to work around
            # https://github.com/nedbat/coveragepy/issues/1595#issuecomment-1931494916
            await d.addErrback(lambda e: e.trap(CancelledError))

        async def asynchronously() -> None:
            nonlocal succeeding
            if succeeding:
                succeeding = succeeding - 1
                await pending
            else:
                await bonk(pending)

        async def synchronously() -> None:
            pass

        def go(how: Callable[[], Any]) -> None:
            nonlocal repeatCall
            repeatCall = Async(tad).repeatedly(
                Scheduler(mem),
                EverySecond(1),
                lambda times, stopper: how(),
            )

        async def run(how: Callable[[], Any]) -> None:
            go(how)
            assert repeatCall is not None, "repeatCall should already be set"
            await bonk(repeatCall)

        tad.runAsync(run(asynchronously))
        self.assertTrue(mem.isScheduled())
        assert repeatCall is not None

        repeatCall.cancel()
        self.assertFalse(mem.isScheduled())
        pending = Deferred(canceled)
        succeeding += 1
        tad.runAsync(run(asynchronously))
        self.assertTrue(mem.isScheduled())
        mem.advance()
        self.assertFalse(mem.isScheduled())
        p, pending = pending, Deferred(canceled)
        p.callback(None)
        self.assertTrue(mem.isScheduled())
        mem.advance()
        repeatCall.cancel()
        tad.runAsync(run(synchronously))
        self.assertTrue(mem.isScheduled())
        repeatCall.cancel()
        self.assertFalse(mem.isScheduled())

    def test_eachWeekOn(self) -> None:
        """
        L{EachWeekOn} provides a recurrence on custom weekdays at custom
        times.
        """
        tad = TwistedAsyncDriver()
        mem = MemoryDriver()
        mem.advance(1706826915.372823)

        TZ = ZoneInfo("America/Los_Angeles")
        dtd = DateTimeDriver(mem, TZ)
        sch = Scheduler[DateTime[ZoneInfo], Callable[[], None]](dtd)
        x = []

        async def record(
            steps: list[DateTime[ZoneInfo]], stopper: Cancellable
        ) -> None:
            x.append((sch.now(), steps, stopper))

        rule: RecurrenceRule[
            DateTime[ZoneInfo], list[DateTime[ZoneInfo]]
        ] = EachWeekOn(
            days={Day.MONDAY, Day.WEDNESDAY, Day.FRIDAY},
            hour=15,
            minute=10,
        )

        Async(tad).repeatedly(sch, rule, record)

        mem.advance()
        mem.advance()
        mem.advance(86401 * 5)
        mem.advance(86401 * 24)

        [
            (start, _, _),
            (first, tries1, _),
            (second, tries2, _),
            (fourth, tries4, _),
            *rest,
        ] = x
        self.assertEqual(tries1, [datetime(2024, 2, 2, 15, 10, tzinfo=TZ)])
        self.assertEqual(tries2, [datetime(2024, 2, 5, 15, 10, tzinfo=TZ)])
        self.assertEqual(
            tries4,
            [
                datetime(2024, 2, 7, 15, 10, tzinfo=TZ),
                datetime(2024, 2, 9, 15, 10, tzinfo=TZ),
            ],
        )
        self.assertEqual(datetime(2024, 2, 2, 15, 10, tzinfo=TZ), first)
        self.assertEqual(datetime(2024, 2, 5, 15, 10, tzinfo=TZ), second)
        # 2/7, 2/9 skipped!
        self.assertEqual(datetime(2024, 2, 10, 15, 10, 5, tzinfo=TZ), fourth)
        bigSkip = [
            *[
                datetime(2024, 2, n, 15, 10, tzinfo=TZ)
                for n in [12, 14, 16, 19, 21, 23, 26, 28]
            ],
            *[datetime(2024, 3, n, 15, 10, tzinfo=TZ) for n in [1, 4]],
        ]
        self.maxDiff = 99999
        actual = list(chain(*[tries for (_, tries, _) in rest]))
        self.assertEqual(bigSkip, actual)
