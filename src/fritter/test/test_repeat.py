from unittest import TestCase

from fritter.drivers.memory import MemoryDriver
from twisted.internet.defer import Deferred, succeed

from ..drivers.twisted import TwistedAsyncDriver
from ..repeat import EverySecond, repeatAsync
from ..scheduler import Scheduler


class RepeatTestCase(TestCase):
    def test_repeatEveryIntervalInSeconds(self) -> None:
        tad = TwistedAsyncDriver()
        mem = MemoryDriver()
        count = 0
        calls = []
        event: Deferred[None] = succeed(None)

        async def tick(times: int) -> None:
            nonlocal count, event
            calls.append(f"before {count} ({times})")
            event = Deferred()
            await event
            calls.append(f"after {count}")
            count += 1

        repeatAsync(
            lambda times: Deferred.fromCoroutine(tick(times)),
            EverySecond(15),
            tad,
            Scheduler(mem),
        )

        self.assertEqual(calls, ["before 0 (1)"])
        event.callback(None)
        self.assertEqual(calls, ["before 0 (1)", "after 0"])
        del calls[:]
        mem.advance(15.3)
        self.assertEqual(calls, ["before 1 (1)"])
        del calls[:]
        # async operation takes 45 seconds. it's now 60.3.
        mem.advance(45.0)
        self.assertEqual(calls, [])
        event.callback(None)
        # catch-up call is immediately scheduled
        self.assertEqual(calls, ["after 1", "before 2 (3)"])
        del calls[:]
        event.callback(None)
        self.assertEqual(calls, ["after 2"])
