from unittest import TestCase

from ..drivers.memory import MemoryDriver, DiscreteDriver


epsilon = 1e-100


class MemoryDriverTests(TestCase):
    def test_advance(self) -> None:
        driver = MemoryDriver()
        work = []
        self.assertEqual(driver.isScheduled(), False)
        driver.reschedule(3.5, lambda: work.append(driver.now()))
        self.assertEqual(driver.isScheduled(), True)
        driver.advance(1)
        self.assertEqual(driver.now(), 1.0)
        self.assertEqual(work, [])
        self.assertEqual(driver.advance(), 2.5)
        self.assertEqual(driver.now(), 3.5)
        self.assertEqual(driver.isScheduled(), False)
        self.assertEqual(driver.advance(), None)

    def test_noBackwards(self) -> None:
        driver = MemoryDriver()
        count = 0

        def work() -> None:
            nonlocal count
            count += 1
            driver.reschedule(0, work)

        driver.reschedule(0, work)
        driver.advance()
        self.assertEqual(count, 1)
        self.assertGreater(driver.now(), 0.0)
        self.assertLess(driver.now(), 1e-20)

    def test_step(self) -> None:
        driver = MemoryDriver()
        self.assertEqual(driver.isScheduled(), False)
        count = 0

        def forever() -> None:
            nonlocal count
            count += 1
            driver.reschedule(0, forever)

        driver.reschedule(0, forever)
        steps = driver.step()
        self.assertEqual(steps, 100)
        self.assertEqual(count, 100)
        self.assertTrue(driver.now() < epsilon)

    def test_step2(self) -> None:
        driver = MemoryDriver()
        count = 0
        nows = []

        def add20() -> None:
            nonlocal count
            count += 1
            nows.append(driver.now())
            driver.reschedule(driver.now() + 20.0, add20)

        driver.reschedule(10.0, add20)
        steps = driver.step(maxCalls=5)
        self.assertEqual(steps, 5)
        self.assertEqual(count, 5)
        self.assertEqual(driver.now(), 90.0)
        steps = driver.step(maxCalls=1)
        self.assertEqual(steps, 1)
        self.assertEqual(driver.now(), 110.0)
        self.assertEqual(nows, [10.0, 30.0, 50.0, 70.0, 90.0, 110.0])

    def test_step0(self) -> None:
        driver = MemoryDriver()
        steps = driver.step(until=5.0)
        self.assertEqual(steps, 0)
        self.assertEqual(driver.now(), 5.0)

    def test_step00(self) -> None:
        driver = MemoryDriver()
        steps = driver.step()
        self.assertEqual(steps, 0)
        self.assertEqual(driver.now(), 0.0)

    def test_step1(self) -> None:
        driver = MemoryDriver()
        count = 0

        def justOnce() -> None:
            nonlocal count
            count += 1

        driver.reschedule(10.0, justOnce)
        steps = driver.step()
        self.assertEqual(steps, 1)
        self.assertEqual(count, 1)
        self.assertEqual(driver.now(), 10.0)

    def test_step_early(self) -> None:
        driver = MemoryDriver()
        count = 0

        def early() -> None:
            nonlocal count
            count += 1
            driver.reschedule(0.0, early)

        driver.reschedule(10.0, early)
        steps = driver.step()
        self.assertEqual(steps, 100)
        self.assertEqual(count, 100)
        self.assertGreater(driver.now(), 10.0)
        self.assertLess(10 - driver.now(), epsilon)

    def test_discrete_driver(self) -> None:
        pretendReal = MemoryDriver()
        discrete = DiscreteDriver(pretendReal)
        count = 0
        when = []

        def repeat() -> None:
            nonlocal count
            count += 1
            when.append(now := discrete.now())
            discrete.reschedule(now + 3.0, repeat)

        discrete.reschedule(3.0, repeat)
        pretendReal.advance(9.1)
        self.assertEqual(when, [3.0, 6.0, 9.0])
        self.assertEqual(count, 3)

    def test_continuous_driver(self) -> None:
        continuous = MemoryDriver()
        count = 0
        when = []

        def repeat() -> None:
            nonlocal count
            count += 1
            when.append(now := continuous.now())
            continuous.reschedule(now + 3.0, repeat)

        continuous.reschedule(3.0, repeat)
        continuous.advance(9.1)
        self.assertEqual(when, [9.1])
        self.assertEqual(count, 1)
