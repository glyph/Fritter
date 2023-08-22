from typing import Callable, List, Tuple
from unittest import TestCase

from ..drivers.memory import MemoryDriver
from ..tree import branch, _BranchDriver
from ..scheduler import SimpleScheduler


class RecursiveTest(TestCase):
    def _oneRecursiveCall(
        self, scaleFactor: float
    ) -> List[Tuple[float, float]]:
        scheduler1 = SimpleScheduler(driver := MemoryDriver())
        recursive, scheduler2 = branch(scheduler1, scaleFactor)
        calls = []
        scheduler2.callAt(
            1.0,
            lambda: calls.append((scheduler1.now(), scheduler2.now())),
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

    def test_changeScaling(self) -> None:
        scheduler1 = SimpleScheduler(driver := MemoryDriver())
        recursive, scheduler2 = branch(scheduler1, 2.0)
        calls = []
        scheduler2.callAt(
            1.0,
            lambda: calls.append((scheduler1.now(), scheduler2.now())),
        )
        driver.advance(1 / 4)
        recursive.scaleFactor *= 2.0
        self.assertEqual(driver.advance(), 1 / 8)
        self.assertEqual(calls, [((1 / 4) + (1 / 8), 1.0)])

    def test_unscheduleNoOp(self) -> None:
        """
        Unscheduling when not scheduled is a no-op.
        """
        _BranchDriver(SimpleScheduler(MemoryDriver())).unschedule()

    def test_unpausePauseUnpause(self) -> None:
        scheduler1 = SimpleScheduler(driver := MemoryDriver())
        recursive, scheduler2 = branch(scheduler1, scaleFactor=2)
        recursive.pause()
        self.assertEqual(scheduler2.now(), 0.0)
        driver.advance(500)
        self.assertEqual(scheduler2.now(), 0.0)
        recursive.unpause()
        self.assertEqual(scheduler2.now(), 0.0)
        driver.advance(10)
        self.assertEqual(scheduler2.now(), 20.0)
        recursive.unpause()
        self.assertEqual(scheduler2.now(), 20.0)
        driver.advance(10)
        self.assertEqual(scheduler2.now(), 40.0)

    def test_moveSooner(self) -> None:
        scheduler1 = SimpleScheduler(driver := MemoryDriver())
        recursive, scheduler2 = branch(scheduler1)
        calls: list[tuple[float, float]] = []
        recursive.unpause()

        recordTimestamp = timestampRecorder(calls, scheduler1, scheduler2)

        scheduler2.callAt(1.0, recordTimestamp)
        scheduler2.callAt(0.5, recordTimestamp)
        driver.advance(0.6)
        self.assertEqual(calls, [(0.6, 0.6)])

    def test_pausing(self) -> None:
        scheduler1 = SimpleScheduler(driver := MemoryDriver())
        recursive, scheduler2 = branch(scheduler1)
        calls = []
        scheduler2.callAt(
            1.0,
            lambda: calls.append((scheduler1.now(), scheduler2.now())),
        )
        scheduler2.callAt(
            2.0,
            lambda: calls.append((scheduler1.now(), scheduler2.now())),
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
        self.assertEqual(2.7 + 1.5, driver.now())
        self.assertEqual(1.5, scheduler2.now())
        recursive.unpause()
        driver.advance(0.5)
        self.assertEqual(2.7 + 1.5 + 0.5, driver.now())
        self.assertEqual(1.5 + 0.5, scheduler2.now())
        self.assertEqual(calls, [(2.7 + 1.5 + 0.5, 2.0)])

    def test_doubleUnpause(self) -> None:
        scheduler1 = SimpleScheduler(driver := MemoryDriver())
        scaleFactor = 2.0
        recursive, scheduler2 = branch(scheduler1, scaleFactor)
        recursive.pause()
        baseTime = 1000.0
        driver.advance(baseTime)
        calls = []
        localDelta = 5.0
        scaledDelta = localDelta / scaleFactor
        scheduler2.callAt(
            scheduler2.now() + localDelta,
            lambda: calls.append((scheduler1.now(), scheduler2.now())),
        )
        recursive.unpause()
        driver.advance(1.0)
        self.assertEqual(calls, [])
        recursive.unpause()
        driver.advance(1.0)
        self.assertEqual(calls, [])
        recursive.unpause()
        driver.advance(0.5)
        self.assertEqual(calls, [(baseTime + scaledDelta, localDelta)])

    def test_idling(self) -> None:
        scheduler1 = SimpleScheduler(driver := MemoryDriver())
        recursive, scheduler2 = branch(scheduler1)
        calls: list[tuple[float, float]] = []
        recordTimestamp = timestampRecorder(calls, scheduler1, scheduler2)
        onlyCall = scheduler2.callAt(1.0, recordTimestamp)
        self.assertTrue(driver.isScheduled())
        onlyCall.cancel()
        self.assertFalse(driver.isScheduled())


def timestampRecorder(
    calls: list[tuple[float, float]],
    scheduler1: SimpleScheduler,
    scheduler2: SimpleScheduler,
) -> Callable[[], None]:
    def recorder() -> None:
        calls.append((scheduler1.now(), scheduler2.now()))

    return recorder
