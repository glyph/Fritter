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

    def test_unschedule(self) -> None:
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

        times = 0

        def once() -> None:
            nonlocal times
            times += 1

        scheduler.callAt(1, once)
        two = scheduler.callAt(2, once)
        driver.block(1.5)
        self.assertEqual(times, 1)
        two.cancel()
        driver.block(1.5)
        self.assertEqual(times, 1)

    def test_timeout(self) -> None:
        current = 0.0
        sleeps = []
        calls = []

        def sleep(duration: float) -> None:
            nonlocal current
            sleeps.append(duration)
            current += duration

        def time() -> float:
            return current

        driver = SleepDriver(sleep, time)

        def hello() -> None:
            calls.append(1)

        driver.reschedule(1.0, hello)
        result = driver.block(0.4)

        self.assertEqual(sleeps, [0.4])
        self.assertEqual(result, 0)
        self.assertEqual(current, 0.4)
        self.assertEqual(calls, [])

        result = driver.block(0.6)
        self.assertEqual(sleeps, [0.4, 0.6])
        self.assertEqual(result, 1)
        self.assertEqual(current, 1.0)
        self.assertEqual(calls, [1])

        result = driver.block(0.7)
        self.assertEqual(result, 0)
        self.assertEqual(current, 1.0)
        self.assertEqual(calls, [1])
        self.assertEqual(sleeps, [0.4, 0.6])
