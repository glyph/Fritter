from unittest import TestCase

from fritter.drivers.memory import MemoryDriver
from twisted.internet.defer import Deferred, succeed, CancelledError

from ..drivers.twisted import TwistedAsyncDriver
from ..repeat import EverySecond, repeatAsync
from ..scheduler import Scheduler


class RepeatTestCase(TestCase):
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

        repeatAsync(
            lambda times: Deferred.fromCoroutine(tick(times)),
            EverySecond(15),
            tad,
            Scheduler(mem),
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

        def step(steps: int) -> Deferred[None]:
            nonlocal count
            count += steps
            return succeed(None)

        def isDone() -> bool:
            return count >= threshold

        tad = TwistedAsyncDriver()
        mem = MemoryDriver()
        done = False

        async def task() -> None:
            nonlocal done
            await repeatAsync(
                step, EverySecond(1), tad, Scheduler(mem), isDone
            )
            done = True

        tad.runAsync(task())
        for ignored in range(threshold):
            mem.advance()
        self.assertTrue(done)
        self.assertEqual(count, threshold)

    def test_cancel(self) -> None:
        tad = TwistedAsyncDriver()
        mem = MemoryDriver()

        def canceled(d: Deferred[None]) -> None:
            return

        pending: Deferred[None] = Deferred(canceled)

        async def step() -> None:
            with self.assertRaises(CancelledError):
                await pending

        repeatCall = repeatAsync(
            lambda times: Deferred.fromCoroutine(step()),
            EverySecond(1),
            tad,
            Scheduler(mem),
        )

        async def run() -> None:
            with self.assertRaises(CancelledError):
                await repeatCall

        tad.runAsync(run())
        self.assertTrue(mem.isScheduled())
        repeatCall.cancel()
        self.assertFalse(mem.isScheduled())
