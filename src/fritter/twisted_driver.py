from dataclasses import dataclass
from typing import Callable, Optional

from twisted.internet.defer import Deferred
from twisted.internet.interfaces import IDelayedCall, IReactorTime
from twisted.logger import Logger

from .boundaries import RepeatingWork
from .repeat import Repeating
from .scheduler import Scheduler
from fritter.boundaries import PriorityQueue
from fritter.priority_queue import HeapPriorityQueue
from fritter.scheduler import FutureCall, Scheduler, SimpleScheduler


log = Logger()


@dataclass
class TwistedTimeDriver(object):
    _reactor: IReactorTime
    _call: Optional[IDelayedCall] = None

    def reschedule(self, desiredTime: float, work: Callable[[], None]) -> None:
        def _() -> None:
            self._call = None
            work()

        if self._call is not None:
            self._call.cancel()
        self._call = self._reactor.callLater(
            max(0, desiredTime - self.currentTimestamp()), _
        )

    def unschedule(self) -> None:
        if self._call is not None:
            self._call.cancel()
            self._call = None

    def currentTimestamp(self) -> float:
        return self._reactor.seconds()


@dataclass
class TwistedAsyncDriver(object):
    """
    Driver for Deferred-flavored repeating scheduler.
    """

    def newWithCancel(self, cancel: Callable[[], None]) -> Deferred[None]:
        "Create a new future-ish object with the given callback to execute when canceled."
        return Deferred(lambda d: cancel())

    def complete(self, asyncObj: Deferred[None]) -> None:
        "The asynchronous operation completed successfully."
        asyncObj.callback(None)

    def unhandledError(
        self,
        applicationCode: RepeatingWork,
        inProgressObj: Optional[Deferred[None]],
    ) -> None:
        "called in an exception scope when"
        if inProgressObj is not None:
            inProgressObj.errback()
        else:
            log.failure(
                "Unhandled error while doing {work}", work=applicationCode
            )


def twistedScheduler(
    reactor: IReactorTime,
    queue: Optional[
        PriorityQueue[FutureCall[float, Callable[[], None]]]
    ] = None,
) -> SimpleScheduler:
    """
    Create a scheduler that uses Twisted.
    """
    return Scheduler(
        queue if queue is not None else HeapPriorityQueue(),
        TwistedTimeDriver(reactor),
    )


def twistedRepeating(
    scheduler: SimpleScheduler, work: RepeatingWork
) -> Repeating[Deferred[None], Callable[[], None]]:
    """
    Create a repeating call that returns a Deferred from its start method.
    """
    return Repeating(work, scheduler, TwistedAsyncDriver())
