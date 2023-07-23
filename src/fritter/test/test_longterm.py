
from datetime import datetime
from unittest import TestCase
from zoneinfo import ZoneInfo

from datetype import aware

from fritter.longterm import (
    # Recurring,
    # RuleFunction,
    # daily,
    # dailyWithSkips,
    jsonScheduler,
    schedulerFromJSON,
    JSONRegistry,
)
from fritter.memory_driver import MemoryDriver



registry = JSONRegistry()

calls = []


@registry.byName
def call1() -> None:
    calls.append("hello")


@registry.byName
def call2() -> None:
    calls.append("goodbye")


class PersistentSchedulerTests(TestCase):
    def tearDown(self) -> None:
        del calls[:]

    def test_scheduleRunSaveRun(self) -> None:
        """
        If we schedule a `run` method.
        """
        memoryDriver = MemoryDriver()
        persistentScheduler = jsonScheduler(memoryDriver)
        dt = aware(
            datetime(
                2023,
                7,
                21,
                1,
                1,
                1,
                tzinfo=ZoneInfo(key="America/Los_Angeles"),
            ),
            ZoneInfo,
        )
        dt2 = aware(
            datetime(
                2023,
                7,
                22,
                1,
                1,
                1,
                tzinfo=ZoneInfo(key="America/Los_Angeles"),
            ),
            ZoneInfo,
        )
        persistentScheduler.scheduler.callAtTimestamp(dt, call1)
        persistentScheduler.scheduler.callAtTimestamp(dt2, call2)
        memoryDriver.advance(dt.timestamp() + 1)
        self.assertEqual(calls, ["hello"])
        del calls[:]
        saved = persistentScheduler.save()
        memory2 = MemoryDriver()
        schedulerFromJSON(memory2, saved, registry.loaders)
        memory2.advance(dt2.timestamp() + 1)
        self.assertEqual(calls, ["goodbye"])
