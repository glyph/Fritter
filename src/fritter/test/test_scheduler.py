from typing import Callable
from unittest import TestCase

from ..scheduler import FutureCall, SimpleScheduler
from ..memory_driver import MemoryDriver
from ..priority_queue import HeapPriorityQueue


class SchedulerTests(TestCase):
    """
    Tests for L{Scheduler}.
    """

    def test_schedulingSimple(self) -> None:
        """
        Scheduling a call
        """
        driver = MemoryDriver()
        scheduler = SimpleScheduler(HeapPriorityQueue(), driver)
        called = 0

        def callme() -> None:
            nonlocal called
            called += 1

        scheduler.callAtTimestamp(1.0, callme)
        scheduler.callAtTimestamp(3.0, callme)
        self.assertEqual(0, called)
        driver.advance(2.0)
        self.assertEqual(1, called)

    def test_moveSooner(self) -> None:
        driver = MemoryDriver()
        scheduler = SimpleScheduler(HeapPriorityQueue(), driver)
        called = 0

        def callme() -> None:
            nonlocal called
            called += 1

        scheduler.callAtTimestamp(1.0, callme)
        scheduler.callAtTimestamp(0.5, callme)
        self.assertEqual(0, called)
        driver.advance(0.3)
        self.assertEqual(0, called)
        driver.advance(0.3)
        self.assertEqual(1, called)
        driver.advance(0.6)
        self.assertEqual(2, called)

    def test_canceling(self) -> None:
        """
        CallHandle.cancel() cancels an outstanding call.
        """
        scheduler = SimpleScheduler(
            HeapPriorityQueue(), driver := MemoryDriver()
        )
        callTimes = []

        def record(event: str) -> Callable[[], None]:
            def result() -> None:
                callTimes.append((scheduler.currentTimestamp(), event))

            return result

        aHandle = scheduler.callAtTimestamp(1.0, record("a"))
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
        aHandle.cancel()  # if it's already called it's a no-op
        self.assertEqual(didCancel, [])
        driver.advance()
        self.assertEqual(callTimes, [(1.0, "a")])
        self.assertEqual(didCancel, [True])
        bHandle.cancel()  # repeated calls are no-ops
        self.assertEqual(didCancel, [True])
        driver.advance()
        self.assertEqual(callTimes, [(1.0, "a"), (3.0, "c")])

    def test_queueMustBeEmpty(self) -> None:
        driver = MemoryDriver()
        q = HeapPriorityQueue([FutureCall(1.0, lambda: None)])
        with self.assertRaises(ValueError):
            SimpleScheduler(q, driver)
