from typing import List, Tuple
from unittest import TestCase

from ..memory_driver import MemoryDriver
from ..priority_queue import HeapPriorityQueue
from ..recursive_driver import RecursiveDriver
from ..scheduler import SimpleScheduler


class RecursiveTest(TestCase):
    def _oneRecursiveCall(
        self, scaleFactor: float
    ) -> List[Tuple[float, float]]:
        scheduler1 = SimpleScheduler(
            HeapPriorityQueue(), driver := MemoryDriver()
        )
        scheduler2 = SimpleScheduler(
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

    def test_pausing(self) -> None:
        scheduler1 = SimpleScheduler(
            HeapPriorityQueue(), driver := MemoryDriver()
        )
        scheduler2 = SimpleScheduler(
            HeapPriorityQueue(), recursive := RecursiveDriver(scheduler1)
        )
        recursive.start()
        calls = []
        scheduler2.callAtTimestamp(
            1.0,
            lambda: calls.append(
                (scheduler1.currentTimestamp(), scheduler2.currentTimestamp())
            ),
        )
        scheduler2.callAtTimestamp(
            2.0,
            lambda: calls.append(
                (scheduler1.currentTimestamp(), scheduler2.currentTimestamp())
            ),
        )
        self.assertEqual(calls, [])
        driver.advance(1.5)
        self.assertEqual(calls, [(1.5, 1.5)])
        calls[:] = []
        recursive.pause()
        # paused at 1.5, with 0.5 left until second call (at 2.0)
        driver.advance(2.7)
        # move to 4.2, still 0.5 left, no call yet
        self.assertEqual(calls, [])
        self.assertEqual(2.7 + 1.5, driver.currentTimestamp())
        self.assertEqual(1.5, recursive.currentTimestamp())
        recursive.start()
        driver.advance(0.5)
        self.assertEqual(2.7 + 1.5 + 0.5, driver.currentTimestamp())
        self.assertEqual(1.5 + 0.5, recursive.currentTimestamp())
        self.assertEqual(calls, [(2.7 + 1.5 + 0.5, 2.0)])

    def test_idling(self) -> None:
        scheduler1 = SimpleScheduler(
            HeapPriorityQueue(), driver := MemoryDriver()
        )
        scheduler2 = SimpleScheduler(
            HeapPriorityQueue(), recursive := RecursiveDriver(scheduler1)
        )
        recursive.start()
        calls = []
        onlyCall = scheduler2.callAtTimestamp(
            1.0,
            lambda: calls.append(
                (scheduler1.currentTimestamp(), scheduler2.currentTimestamp())
            ),
        )
        self.assertTrue(driver.isScheduled())
        onlyCall.cancel()
        self.assertFalse(driver.isScheduled())
