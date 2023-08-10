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
