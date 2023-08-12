from asyncio.exceptions import InvalidStateError
from unittest import TestCase

from ..drivers.asyncio import AsyncioAsyncDriver


class AsyncDriverTests(TestCase):
    def test_newWithCancel(self) -> None:
        driver = AsyncioAsyncDriver()

        def cancel() -> None:
            pass

        f = driver.newWithCancel(cancel)
        with self.assertRaises(InvalidStateError):
            f.result()
        driver.complete(f)
        self.assertIsNone(f.result())
