from fritter.drivers.sleep import SleepDriver
from unittest import TestCase


class TestSleeping(TestCase):
    def test_sleep(self) -> None:
        sleeps = []
        current = 0.0
        def sleep(duration: float) -> None:
            nonlocal current
            sleeps.append(duration)
            current += duration
        def time() -> float:
            return current
        driver = SleepDriver(sleep=sleep, time=time)
        threeCalledAt = None
        sevenCalledAt = None
        def three() -> None:
            nonlocal threeCalledAt
            threeCalledAt = driver.now()
        def seven() -> None:
            nonlocal sevenCalledAt
            sevenCalledAt = driver.now()
