from typing import Callable
from unittest import TestCase

from ..memory_driver import MemoryDriver
from ..priority_queue import HeapPriorityQueue
from ..scheduler import Scheduler


class SchedulerTests(TestCase):
    """
    Tests for L{Scheduler}.
    """

    def test_schedulingSimple(self) -> None:
        """
        Scheduling a call
        """
        driver = MemoryDriver()
        scheduler = Scheduler(HeapPriorityQueue(), driver)
        called = 0

        def callme() -> None:
            nonlocal called
            called += 1

        scheduler.callAtTimestamp(1.0, callme)
        scheduler.callAtTimestamp(3.0, callme)
        self.assertEqual(0, called)
        driver.advance(2.0)
        self.assertEqual(1, called)

    def test_canceling(self) -> None:
        """
        CallHandle.cancel() cancels an outstanding call.
        """
        scheduler = Scheduler(HeapPriorityQueue(), driver := MemoryDriver())
        callTimes = []

        def record(event: str) -> Callable[[], None]:
            def result() -> None:
                callTimes.append((scheduler.currentTimestamp(), event))

            return result

        scheduler.callAtTimestamp(1.0, record("a"))
        bHandle = scheduler.callAtTimestamp(2.0, record("b"))
        scheduler.callAtTimestamp(3.0, record("c"))
        didCancel = []

        def bCancel() -> None:
            didCancel.append(True)
            bHandle.cancel()

        scheduler.callAtTimestamp(1.5, bCancel)
        self.assertEqual(callTimes, [])
        driver.advance()
        self.assertEqual(callTimes, [(1.0, "a")])
        self.assertEqual(didCancel, [])
        driver.advance()
        self.assertEqual(callTimes, [(1.0, "a")])
        self.assertEqual(didCancel, [True])
        driver.advance()
        self.assertEqual(callTimes, [(1.0, "a"), (3.0, "c")])
