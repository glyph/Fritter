from unittest import TestCase

from ..memory_driver import MemoryDriver


class MemoryDriverTests(TestCase):
    def test_advance(self) -> None:
        driver = MemoryDriver()
        work = []
        self.assertEqual(driver.isScheduled(), False)
        driver.reschedule(3.5, lambda: work.append(driver.currentTimestamp()))
        self.assertEqual(driver.isScheduled(), True)
        driver.advance(1)
        self.assertEqual(driver.currentTimestamp(), 1.0)
        self.assertEqual(work, [])
        self.assertEqual(driver.advance(), 2.5)
        self.assertEqual(driver.currentTimestamp(), 3.5)
        self.assertEqual(driver.isScheduled(), False)
        self.assertEqual(driver.advance(), None)
