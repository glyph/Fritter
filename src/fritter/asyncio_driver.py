from __future__ import annotations
from asyncio import get_event_loop
from asyncio.events import AbstractEventLoop, TimerHandle
from asyncio.futures import Future
from dataclasses import dataclass
from logging import getLogger
from sys import exc_info
from typing import Callable, Coroutine, Optional

from .boundaries import PriorityQueue, RepeatingWork, Cancelable
from .priority_queue import HeapPriorityQueue
from .scheduler import FutureCall, Scheduler, SimpleScheduler

logger = getLogger(__name__)


@dataclass
class AsyncioTimeDriver(object):
    _loop: AbstractEventLoop
    _call: Optional[TimerHandle] = None

    def reschedule(self, desiredTime: float, work: Callable[[], None]) -> None:
        def _() -> None:
            self._call = None
            work()

        if self._call is not None:
            self._call.cancel()
        self._call = self._loop.call_at(max(0, desiredTime), _)

    def unschedule(self) -> None:
        if self._call is not None:
            self._call.cancel()
            self._call = None

    def now(self) -> float:
        return self._loop.time()


@dataclass
class AsyncioAsyncDriver:
    """
    Driver for asyncio.Future-flavored repeating scheduler.
    """

    _loop: AbstractEventLoop

    def newWithCancel(self, cancel: Callable[[], None]) -> Future[None]:
        """
        Create a new future-ish object with the given callback to execute when
        canceled.
        """
        f = Future[None]()

        @f.add_done_callback
        def done(future: Future[None]) -> None:
            if f.cancelled():
                cancel()

        return f

    def complete(self, asyncObj: Future[None]) -> None:
        "The asynchronous operation completed successfully."
        asyncObj.set_result(None)

    def unhandledError(
        self,
        applicationCode: RepeatingWork,
        inProgressObj: Optional[Future[None]],
    ) -> None:
        "called in an exception scope when"
        t, v, tb = exc_info()
        assert (
            (t is not None) and (v is not None) and (tb is not None)
        ), "Must be called from exception context"
        if inProgressObj is not None:
            inProgressObj.set_exception(v)
        else:
            logger.error(
                "Unhandled error while doing %s",
                applicationCode,
                exc_info=(t, v, tb),
            )

    def runAsync(
        self, coroutine: Coroutine[object, Future[None], object]
    ) -> Cancelable:
        return self._loop.create_task(coroutine)


def asyncioScheduler(
    loop: AbstractEventLoop,
    queue: Optional[
        PriorityQueue[FutureCall[float, Callable[[], None]]]
    ] = None,
) -> SimpleScheduler:
    """
    Create a scheduler that uses Asyncio.
    """
    return Scheduler(
        AsyncioTimeDriver(loop),
        queue if queue is not None else HeapPriorityQueue(),
    )
