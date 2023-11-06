from typing import Any, Callable
from unittest import TestCase

from twisted.internet.defer import CancelledError, Deferred, succeed

from ..boundaries import Cancellable
from ..drivers.memory import MemoryDriver
from ..drivers.twisted import TwistedAsyncDriver
from ..repeat import EverySecond, Async, repeatedly
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

        def canceled(d: Deferred[None]) -> None:
            return

        pending: Deferred[None] = Deferred(canceled)
        succeeding: int = 0

        async def asynchronously() -> None:
            nonlocal succeeding
            if succeeding:
                succeeding = succeeding - 1
                await pending
            else:
                with self.assertRaises(CancelledError):
                    await pending

        async def synchronously() -> None:
            pass

        repeatCall: Deferred[None]

        def go(how: Callable[[], Any]) -> None:
            nonlocal repeatCall
            repeatCall = Async(tad).repeatedly(
                Scheduler(mem),
                EverySecond(1),
                lambda times, stopper: how(),
            )

        async def run(how: Callable[[], Any]) -> None:
            go(how)
            with self.assertRaises(CancelledError):
                await repeatCall

        tad.runAsync(run(asynchronously))
        self.assertTrue(mem.isScheduled())
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
