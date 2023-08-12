from asyncio.exceptions import InvalidStateError, CancelledError
from unittest import TestCase

from ..drivers.asyncio import AsyncioAsyncDriver


class AsyncDriverTests(TestCase):
    def setUp(self) -> None:
        self.called = 0

    def call(self) -> None:
        self.called += 1

    def test_complete(self) -> None:
        driver = AsyncioAsyncDriver()

        def cancel() -> None:
            pass

        f = driver.newWithCancel(self.call)
        with self.assertRaises(InvalidStateError):
            f.result()

        driver.complete(f)
        self.assertIsNone(f.result())

    def test_cancel(self) -> None:
        driver = AsyncioAsyncDriver()

        f = driver.newWithCancel(self.call)
        with self.assertRaises(InvalidStateError):
            f.result()
        f.cancel()
        with self.assertRaises(CancelledError):
            f.result()


