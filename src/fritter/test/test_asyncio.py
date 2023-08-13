from asyncio import run
from asyncio.events import new_event_loop
from asyncio.exceptions import CancelledError, InvalidStateError
from asyncio.futures import Future
from unittest import TestCase

from ..drivers.asyncio import AsyncioAsyncDriver


class AsyncDriverTests(TestCase):
    def setUp(self) -> None:
        self.called = 0
        self.loop = new_event_loop()

    def call(self) -> None:
        self.called += 1

    def test_complete(self) -> None:
        driver = AsyncioAsyncDriver(self.loop)

        def cancel() -> None:
            pass

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
