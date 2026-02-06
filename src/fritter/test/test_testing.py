from unittest import TestCase

from ..drivers.memory import MemoryDriver, DiscreteDriver


epsilon = 1e-100


class MemoryDriverTests(TestCase):
    """
    Tests for L{MemoryDriver}.
    """
    def test_advance(self) -> None:
        """
        L{MemoryDriver.advance} advances its internal clock adn runs its
        scheduled work.

            - when given a value, it advances by an amount of time represented
              by that value

            - when given no value, it advances to the time of the scheduled
              work.
        """
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

    def test_noBackwards(self) -> None:
        """
        When work is scheduled in the past, time on L{MemoryDriver.advance}
        does not move backwards, but advances by a small epsilon.
        """
        driver = MemoryDriver()
        count = 0

        def work() -> None:
            nonlocal count
            count += 1
            driver.reschedule(0, work)

        driver.reschedule(0, work)
        driver.advance()
        self.assertEqual(count, 1)
        self.assertGreater(driver.now(), 0.0)
        self.assertLess(driver.now(), 1e-20)

    def test_step(self) -> None:
        """
        L{MemoryDriver.step} will invoke the drivers's work its invocations
        before returning limited, by default, to 100.
        """
        driver = MemoryDriver()
        self.assertEqual(driver.isScheduled(), False)
        count = 0

        def forever() -> None:
            nonlocal count
            count += 1
            driver.reschedule(0, forever)

        driver.reschedule(0, forever)
        steps = driver.step()
        self.assertEqual(steps, 100)
        self.assertEqual(count, 100)
        self.assertTrue(driver.now() < epsilon)

    def test_stepNowAdvancesSynchronously(self) -> None:
        """
        L{MemoryDriver.step} will limit its number of synchronous invocations
        to a limit described by its C{maxCalls} parameter.  Each invocation
        will have C{driver.now()} set to the time that was passed to
        L{MemoryDriver.reschedule}.
        """
        driver = MemoryDriver()
        count = 0
        nows = []

        def add20() -> None:
            nonlocal count
            count += 1
            nows.append(driver.now())
            driver.reschedule(driver.now() + 20.0, add20)

        driver.reschedule(10.0, add20)
        steps = driver.step(maxCalls=5)
        self.assertEqual(steps, 5)
        self.assertEqual(count, 5)
        self.assertEqual(driver.now(), 90.0)
        steps = driver.step(maxCalls=1)
        self.assertEqual(steps, 1)
        self.assertEqual(driver.now(), 110.0)
        self.assertEqual(nows, [10.0, 30.0, 50.0, 70.0, 90.0, 110.0])

    def test_stepUntil(self) -> None:
        """
        L{MemoryDriver.step} takes an C{until} parameter which describes an
        upper limit of the time that it will advance the driver's C{.now()} to.
        """
        driver = MemoryDriver()
        steps = driver.step(until=5.0)
        self.assertEqual(steps, 0)
        self.assertEqual(driver.now(), 5.0)

    def test_stepNothing(self) -> None:
        """
        If no work is scheduled, L{MemoryDriver.step} does nothing, not
        advancing time at all.
        """
        driver = MemoryDriver()
        steps = driver.step()
        self.assertEqual(steps, 0)
        self.assertEqual(driver.now(), 0.0)

    def test_stepOnce(self) -> None:
        """
        If a callable doesn't reschedule itself, L{MemoryDriver.step} will run
        it once and advance to its time.
        """
        driver = MemoryDriver()
        count = 0

        def justOnce() -> None:
            nonlocal count
            count += 1

        driver.reschedule(10.0, justOnce)
        steps = driver.step()
        self.assertEqual(steps, 1)
        self.assertEqual(count, 1)
        self.assertEqual(driver.now(), 10.0)

    def test_stepMuchEarlier(self) -> None:
        """
        If a callable scheduled with L{MemoryDriver.reschedule} calls
        C{reschedule} again with a time far in the past, L{MemoryDriver.step}
        will advance time by a tiny epsilon and not move time backwards.
        """
        driver = MemoryDriver()
        count = 0

        def early() -> None:
            nonlocal count
            count += 1
            driver.reschedule(0.0, early)

        driver.reschedule(10.0, early)
        steps = driver.step()
        self.assertEqual(steps, 100)
        self.assertEqual(count, 100)
        self.assertGreater(driver.now(), 10.0)
        self.assertLess(10 - driver.now(), epsilon)

    def test_discreteDriver(self) -> None:
        """
        L{DiscreteDriver} wraps a time driver and a L{MemoryDriver}, and
        simulates a discrete time simulation by remembering the I{scheduled}
        time of each callable as it runs, as its value for
        L{DiscreteDriver.now}, thus making it possible for code to know what
        time it was I{supposed} to be run at (i.e. when its discrete invocation
        time was) rather than what it was actually invoked.
        """
        pretendReal = MemoryDriver()
        discrete = DiscreteDriver(pretendReal)
        count = 0
        when = []

        def repeat() -> None:
            nonlocal count
            count += 1
            when.append(now := discrete.now())
            discrete.reschedule(now + 3.0, repeat)

        discrete.reschedule(3.0, repeat)
        pretendReal.advance(9.1)
        self.assertEqual(when, [3.0, 6.0, 9.0])
        self.assertEqual(count, 3)

    def test_continuousDriver(self) -> None:
        """
        As opposed to L{MemoryDriver.step}, L{MemoryDriver.advance} advances
        the value of C{.now()} immediately, so that each invoked callable will
        see that "real" time rather than the time they were scheduled at.
        """
        continuous = MemoryDriver()
        count = 0
        when = []

        def repeat() -> None:
            nonlocal count
            count += 1
            when.append(now := continuous.now())
            continuous.reschedule(now + 3.0, repeat)

        continuous.reschedule(3.0, repeat)
        continuous.advance(9.1)
        self.assertEqual(when, [9.1])
        self.assertEqual(count, 1)
