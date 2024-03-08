from typing import Callable
from unittest import TestCase

from ..boundaries import ScheduledState, Scheduler, PhysicalScheduler
from ..drivers.memory import MemoryDriver
from ..scheduler import schedulerFromDriver


class SchedulerTests(TestCase):
    """
    Tests for L{Scheduler}.
    """

    def test_schedulingSimple(self) -> None:
        """
        Scheduling a call
        """
        driver = MemoryDriver()
        scheduler: PhysicalScheduler = schedulerFromDriver(driver)
        called = 0

        def callme() -> None:
            nonlocal called
            called += 1

        handle = scheduler.callAt(1.0, callme)
        scheduler.callAt(3.0, callme)
        self.assertEqual(0, called)
        driver.advance(2.0)
        self.assertEqual(1, called)
        self.assertEqual(handle.state, ScheduledState.called)
        handle.cancel()  # no-op

    def test_moveSooner(self) -> None:
        driver = MemoryDriver()
        scheduler: Scheduler[float, Callable[[], None], int] = (
            schedulerFromDriver(driver)
        )
        called = 0

        def callme() -> None:
            nonlocal called
            called += 1

        first = scheduler.callAt(1.0, callme)
        second = scheduler.callAt(0.5, callme)
        self.assertEqual(first.state, ScheduledState.pending)
        self.assertEqual(second.state, ScheduledState.pending)
        self.assertEqual(0, called)
        driver.advance(0.3)
        self.assertEqual(0, called)
        driver.advance(0.3)
        self.assertEqual(first.state, ScheduledState.pending)
        self.assertEqual(second.state, ScheduledState.called)
        self.assertEqual(1, called)
        driver.advance(0.6)
        self.assertEqual(2, called)
        self.assertEqual(first.state, ScheduledState.called)
        self.assertEqual(second.state, ScheduledState.called)

    def test_canceling(self) -> None:
        """
        CallHandle.cancel() cancels an outstanding call.
        """
        scheduler: Scheduler[float, Callable[[], None], int] = (
            schedulerFromDriver(driver := MemoryDriver())
        )
        callTimes = []

        def record(event: str) -> Callable[[], None]:
            def result() -> None:
                callTimes.append((scheduler.now(), event))

            return result

        aHandle = scheduler.callAt(1.0, record("a"))
        bHandle = scheduler.callAt(2.0, record("b"))
        scheduler.callAt(3.0, record("c"))
        last = scheduler.callAt(2.5, record("d"))
        last.cancel()
        didCancel = []

        def bCancel() -> None:
            didCancel.append(True)
            bHandle.cancel()
            self.assertEqual(bHandle.state, ScheduledState.cancelled)

        scheduler.callAt(1.5, bCancel)
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


def noop() -> None: ...


def nocancel(x: object) -> None: ...
