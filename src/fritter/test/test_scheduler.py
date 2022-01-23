from unittest import TestCase

from ..scheduler import Scheduler
from ..priority_queue import HeapPriorityQueue
from ..memory_driver import MemoryDriver

class SchedulerTests(TestCase):
    """
    Tests for L{Scheduler}.
    """

    def test_scheduling_simple(self) -> None:
        """
        Scheduling a call
        """
        driver = MemoryDriver()
        scheduler = Scheduler(HeapPriorityQueue(), driver)
        called = 0
        def callme():
            nonlocal called
            called += 1
        scheduler.callAtTimestamp(1.0, callme)
        scheduler.callAtTimestamp(3.0, callme)
        self.assertEqual(0, called)
        driver.advance(2.0)
        self.assertEqual(1, called)
