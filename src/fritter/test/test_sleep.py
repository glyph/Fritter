from fritter.drivers.sleep import SleepDriver
from fritter.scheduler import SimpleScheduler

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
        scheduler = SimpleScheduler(driver)

        threeCalledAt = None
        sevenCalledAt = None

        def three() -> None:
            nonlocal threeCalledAt
            threeCalledAt = driver.now()

        def seven() -> None:
            nonlocal sevenCalledAt
            sevenCalledAt = driver.now()

        scheduler.callAt(3.0, three)
        scheduler.callAt(7.0, seven)
        driver.block()

        self.assertEqual(threeCalledAt, 3.0)
        self.assertEqual(sevenCalledAt, 7.0)
        self.assertEqual(sleeps, [3.0, 4.0])

    def test_timeout(self) -> None:
        current = 0.0
        sleeps = []

        def sleep(duration: float) -> None:
            nonlocal current
            sleeps.append(duration)
            current += duration

        def time() -> float:
            return current

        driver = SleepDriver(sleep, time)

        def hello() -> None:
            ...

        driver.reschedule(1.0, hello)
        result = driver.block(0.5)

        self.assertEqual(sleeps, [0.5])
        self.assertEqual(result, 0)
        self.assertEqual(current, 0.5)
