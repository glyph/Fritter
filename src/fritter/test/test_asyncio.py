from asyncio.events import TimerHandle, new_event_loop
from asyncio.exceptions import CancelledError, InvalidStateError
from contextvars import Context
from dataclasses import dataclass
from typing import Callable
from unittest import TestCase

from fritter.boundaries import Cancelable
from fritter.drivers.asyncio import AsyncioTimeDriver
from twisted.internet.task import Clock

from ..drivers.asyncio import AsyncioAsyncDriver


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
    ) -> Cancelable:
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

    def call(self) -> None:
        self.called += 1

    def test_complete(self) -> None:
        driver = AsyncioAsyncDriver(self.loop)

        f = driver.newWithCancel(self.call)
        with self.assertRaises(InvalidStateError):
            f.result()

        driver.complete(f)
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
