"""
Implementation of L{TimeDriver} and L{AsyncDriver} in terms of U{Twisted
<https://twisted.org/>}'s APIs, L{IReactorTime} and L{Deferred}.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Coroutine, Optional

from twisted.internet.defer import Deferred
from twisted.internet.interfaces import IDelayedCall, IReactorTime
from twisted.logger import Logger

from ..boundaries import PriorityQueue, TimeDriver, AsyncDriver
from ..heap import Heap
from ..scheduler import FutureCall, Scheduler, SimpleScheduler

log = Logger()


@dataclass
class TwistedTimeDriver:
    """
    Instantiate a L{TwistedTimeDriver} with an L{IReactorTime}; for example::

        from twisted.internet.task import react

        async def main(reactor):
            driver = TwistedTimeDriver(reactor)
            ...

        task.react(main)
    """

    _reactor: IReactorTime
    _call: Optional[IDelayedCall] = None

    def reschedule(self, desiredTime: float, work: Callable[[], None]) -> None:
        """"""

        def _() -> None:
            self._call = None
            work()

        if self._call is not None:
            self._call.cancel()
        self._call = self._reactor.callLater(
            max(0, desiredTime - self.now()), _
        )

    def unschedule(self) -> None:
        if self._call is not None:
            self._call.cancel()
            self._call = None

    def now(self) -> float:
        return self._reactor.seconds()


_TimeDriverCheck: type[TimeDriver[float]] = TwistedTimeDriver


@dataclass
class TwistedAsyncDriver:
    """
    Driver for Deferred-flavored awaitables.
    """

    def newWithCancel(self, cancel: Callable[[], None]) -> Deferred[None]:
        """
        Create a new future-ish object with the given callback to execute when
        canceled.
        """
        return Deferred(lambda d: cancel())

    def complete(self, asyncObj: Deferred[None]) -> None:
        """
        The asynchronous operation completed successfully.
        """
        asyncObj.callback(None)

    def runAsync(
        self, coroutine: Coroutine[Deferred[None], Any, Any]
    ) -> Deferred[None]:
        return Deferred.fromCoroutine(coroutine)


_AsyncDriverCheck: type[AsyncDriver[Deferred[None]]] = TwistedAsyncDriver


def scheduler(
    reactor: IReactorTime | None = None,
    queue: PriorityQueue[FutureCall[float, Callable[[], None]]] | None = None,
) -> SimpleScheduler:
    """
    Create a scheduler that uses Twisted.
    """
    if reactor is None:
        from twisted.internet import reactor  # type:ignore[assignment]

        assert reactor is not None
    return Scheduler(
        TwistedTimeDriver(reactor),
        queue if queue is not None else Heap(),
    )
