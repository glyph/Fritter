from __future__ import annotations

from twisted.internet.task import Clock
from twisted.trial.unittest import SynchronousTestCase

from ..drivers.twisted import TwistedAsyncDriver, TwistedTimeDriver, scheduler


class TestAsyncDriver(SynchronousTestCase):
    def setUp(self) -> None:
        self.calls = 0

    def called(self) -> None:
        self.calls += 1

    def test_complete(self) -> None:
        driver = TwistedAsyncDriver()
        d = driver.newWithCancel(self.called)
        self.assertNoResult(d)
        driver.complete(d)
        self.assertIsNone(self.successResultOf(d))

    def test_cancel(self) -> None:
        driver = TwistedAsyncDriver()
        d = driver.newWithCancel(self.called)
        self.assertNoResult(d)
        d.cancel()
        self.failureResultOf(d)

    def test_runAsync(self) -> None:
        driver = TwistedAsyncDriver()
        operation = driver.newWithCancel(self.called)

        before = 0
        after = 0

        async def aCoroutine() -> None:
            nonlocal before, after
            before += 1
            await operation
            after += 1

        self.assertEqual(before, 0)
        self.assertEqual(after, 0)
        driver.runAsync(aCoroutine())
        self.assertEqual(before, 1)
        self.assertEqual(after, 0)
        driver.complete(operation)
        self.assertEqual(after, 1)


class TestTimeDriver(SynchronousTestCase):
    def setUp(self) -> None:
        self.calls = 0

    def called(self) -> None:
        self.calls += 1

    def test_now(self) -> None:
        clock = Clock()
        driver = TwistedTimeDriver(clock)
        clock.advance(1234)
        self.assertEqual(driver.now(), 1234.0)
        self.assertEqual(clock.getDelayedCalls(), [])

    def test_schedule(self) -> None:
        clock = Clock()
        driver = TwistedTimeDriver(clock)
        driver.reschedule(1.0, self.called)
        clock.advance(0.5)
        self.assertEqual(self.calls, 0)
        clock.advance(0.6)
        self.assertEqual(self.calls, 1)
        self.assertEqual(clock.getDelayedCalls(), [])

    def test_reschedule(self) -> None:
        clock = Clock()
        driver = TwistedTimeDriver(clock)
        driver.reschedule(1.0, self.called)
        clock.advance(0.5)
        self.assertEqual(self.calls, 0)
        driver.reschedule(2.0, self.called)
        clock.advance(0.6)
        self.assertEqual(self.calls, 0)
        clock.advance(0.9)
        self.assertEqual(self.calls, 1)
        self.assertEqual(clock.getDelayedCalls(), [])

    def test_unschedule(self) -> None:
        clock = Clock()
        driver = TwistedTimeDriver(clock)
        driver.reschedule(1.0, self.called)
        clock.advance(0.5)
        self.assertEqual(self.calls, 0)
        driver.unschedule()
        self.assertEqual(self.calls, 0)
        clock.advance(0.9)
        self.assertEqual(self.calls, 0)
        driver.unschedule()  # no-op, no exception
        self.assertEqual(clock.getDelayedCalls(), [])

    def test_schedulerDefault(self) -> None:
        sched = scheduler()
        self.assertIsInstance(sched.driver, TwistedTimeDriver)

    def test_scheduler(self) -> None:
        sched = scheduler(clock := Clock())
        stuff = []

        def hello() -> None:
            stuff.append("hello")

        sched.callAt(50, hello)
        self.assertEqual(stuff, [])
        clock.advance(60)
        self.assertEqual(stuff, ["hello"])
