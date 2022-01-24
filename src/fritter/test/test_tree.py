from typing import List, Tuple
from unittest import TestCase

from ..memory_driver import MemoryDriver
from ..priority_queue import HeapPriorityQueue
from ..recursive_driver import RecursiveDriver
from ..scheduler import Scheduler


class RecursiveTest(TestCase):
    def _oneRecursiveCall(self, scaleFactor: float) -> List[Tuple[float, float]]:
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

    def test_scaling(self) -> None:
        calls = self._oneRecursiveCall(1.0)
        self.assertEqual(calls, [(1.0, 1.0)])
        calls = self._oneRecursiveCall(3.0)
        self.assertEqual(calls, [(1 / 3.0, 1.0)])
        calls = self._oneRecursiveCall(1 / 3.0)
        self.assertEqual(calls, [(3.0, 1.0)])
