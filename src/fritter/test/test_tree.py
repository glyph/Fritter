from unittest import TestCase

from ..recursive_driver import RecursiveDriver
from ..memory_driver import MemoryDriver
from ..priority_queue import HeapPriorityQueue
from ..scheduler import Scheduler


class RecursiveTest(TestCase):
    def _oneRecursiveCall(self, scaleFactor: float) -> None:
        scheduler1 = Scheduler(HeapPriorityQueue(), driver := MemoryDriver())
        scheduler2 = Scheduler(
            HeapPriorityQueue(), recursive := RecursiveDriver(scheduler1)
        )
        recursive.scaleFactor = scaleFactor
        recursive.start()
        calls = []
        scheduler2.callAtTimestamp(
            1.0,
            lambda: calls.append(
                (scheduler1.currentTimestamp(), scheduler2.currentTimestamp())
            ),
        )
        driver.advance()
        return calls

    def test_scaling(self):
        calls = self._oneRecursiveCall(1.0)
        self.assertEqual(calls, [(1.0, 1.0)])
        calls = self._oneRecursiveCall(3.0)
        self.assertEqual(calls, [(1/3., 1.0)])
        calls = self._oneRecursiveCall(1/3.)
        self.assertEqual(calls, [(3.0, 1.0)])
