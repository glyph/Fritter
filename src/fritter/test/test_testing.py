from unittest import TestCase

from ..drivers.memory import MemoryDriver


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
