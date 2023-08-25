from __future__ import annotations

from asyncio.events import new_event_loop
from asyncio.exceptions import CancelledError, InvalidStateError
from contextvars import Context
from dataclasses import dataclass
from typing import Callable
from unittest import TestCase

from twisted.internet.task import Clock

from ..boundaries import Cancellable
from ..drivers.asyncio import AsyncioTimeDriver, AsyncioAsyncDriver, scheduler


@dataclass
class AsyncioClock:
    """
    Minimal translation of Twisted interface into Asyncio interface.
    """

    clock: Clock

    def call_at(
        self,
        when: float,
        callback: Callable[[], None],
        *args: object,
        context: Context | None = None,
    ) -> Cancellable:
        assert context is None, "context not yet supported"
        return self.clock.callLater(
            when - self.clock.seconds(),
            callback,
            *args,
        )

    def time(self) -> float:
        return self.clock.seconds()


class AsyncDriverTests(TestCase):
    def setUp(self) -> None:
        self.called = 0
        self.loop = new_event_loop()

    def tearDown(self) -> None:
        self.loop.close()

    def call(self) -> None:
        self.called += 1

    def test_complete(self) -> None:
        driver = AsyncioAsyncDriver(self.loop)

        f = driver.newWithCancel(self.call)
        with self.assertRaises(InvalidStateError):
            f.result()

        async def a() -> None:
            driver.complete(f)
            await f

        self.loop.run_until_complete(a())
        self.assertEqual(self.called, 0)
        self.assertIsNone(f.result())

    def test_cancel(self) -> None:
        driver = AsyncioAsyncDriver(self.loop)
        f = driver.newWithCancel(self.call)
        with self.assertRaises(InvalidStateError):
            f.result()
        self.assertEqual(self.called, 0)

        async def a() -> None:
            f.cancel()
            with self.assertRaises(CancelledError):
                await f

        self.loop.run_until_complete(a())
        self.assertEqual(self.called, 1)
        with self.assertRaises(CancelledError):
            f.result()

    def test_runAsync(self) -> None:
        driver = AsyncioAsyncDriver(self.loop)

        # Set up a bunch of futures to ensure tasks are run independently
        # because runAsync doesn't return an awaitable.

        f1 = driver.newWithCancel(self.call)
        f2 = driver.newWithCancel(self.call)
        f3 = driver.newWithCancel(self.call)
        f4 = driver.newWithCancel(self.call)
        f5 = driver.newWithCancel(self.call)
        f6 = driver.newWithCancel(self.call)
        e1 = driver.newWithCancel(self.call)
        e2 = driver.newWithCancel(self.call)
        concurrent = []

        async def c1() -> None:
            concurrent.append("c1")
            await f1
            f3.set_result(None)
            await e1
            concurrent.append("c3")
            f5.set_result(None)

        async def c2() -> None:
            concurrent.append("c2")
            await f2
            f4.set_result(None)
            await e2
            concurrent.append("c4")
            f6.set_result(None)

        async def t() -> None:
            f1.set_result(None)
            f2.set_result(None)
            await f3
            await f4
            self.assertEqual(concurrent, ["c1", "c2"])
            e1.set_result(None)
            e2.set_result(None)
            await f5
            await f6
            self.assertEqual(concurrent, ["c1", "c2", "c3", "c4"])

        driver.runAsync(c1())
        driver.runAsync(c2())

        self.loop.run_until_complete(t())
        self.assertEqual(self.called, 0)


class TimeDriverTests(TestCase):
    def setUp(self) -> None:
        self.called = 0

    def call(self) -> None:
        self.called += 1

    def test_schedule(self) -> None:
        driver = AsyncioTimeDriver(AsyncioClock(clock := Clock()))
        driver.reschedule(3.0, self.call)
        self.assertEqual(self.called, 0)
        clock.advance(4.0)
        self.assertEqual(self.called, 1)

    def test_now(self) -> None:
        driver = AsyncioTimeDriver(AsyncioClock(clock := Clock()))
        clock.advance(7.2)
        self.assertEqual(driver.now(), 7.2)

    def test_reschedule(self) -> None:
        driver = AsyncioTimeDriver(AsyncioClock(clock := Clock()))
        driver.reschedule(3.0, self.call)
        self.assertEqual(self.called, 0)
        driver.reschedule(5.0, self.call)
        clock.advance(4.0)
        self.assertEqual(self.called, 0)
        clock.advance(1.0)
        self.assertEqual(self.called, 1)

    def test_unschedule(self) -> None:
        driver = AsyncioTimeDriver(AsyncioClock(clock := Clock()))
        driver.reschedule(3.0, self.call)
        self.assertEqual(self.called, 0)
        driver.unschedule()
        clock.advance(4.0)
        self.assertEqual(self.called, 0)
        driver.unschedule()  # safe no-op

    def test_scheduler(self) -> None:
        sched = scheduler(AsyncioClock(clock := Clock()))
        stuff = []

        def hello() -> None:
            stuff.append("hello")

        sched.callAt(50, hello)
        self.assertEqual(stuff, [])
        clock.advance(60)
        self.assertEqual(stuff, ["hello"])

    def test_schedulerDefaults(self) -> None:
        sched = scheduler()
        self.assertIsInstance(sched.driver, AsyncioTimeDriver)
