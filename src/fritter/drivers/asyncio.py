# -*- test-case-name: fritter.test.test_asyncio -*-

"""
Implementation of L{TimeDriver} and L{AsyncDriver} for L{asyncio}.
"""

from __future__ import annotations

from asyncio import Future, get_event_loop, AbstractEventLoop
from contextvars import Context
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Protocol

from ..boundaries import (
    AsyncDriver,
    Cancellable,
    PriorityQueue,
    Scheduler,
    TimeDriver,
)
from ..heap import Heap
from ..scheduler import ConcreteScheduledCall, schedulerFromDriver


class LoopTimeInterface(Protocol):
    """
    Describe the portions of L{AbstractEventLoop} used by L{AsyncioTimeDriver}.
    """

    def call_at(
        self,
        when: float,
        callback: Callable[[], None],
        *args: object,
        context: Context | None = None,
    ) -> Cancellable:
        """
        @see: L{AbstractEventLoop.call_at <asyncio.loop.call_at>}
        """

    def time(self) -> float:
        """
        @see: L{AbstractEventLoop.time <asyncio.loop.time>}
        """


@dataclass
class AsyncioTimeDriver:
    """
    An implementation of L{TimeDriver} using an L{asyncio} event loop.
    """

    _loop: LoopTimeInterface = field(default_factory=get_event_loop)
    _call: Cancellable | None = None

    def reschedule(self, desiredTime: float, work: Callable[[], None]) -> None:
        "Implementation of L{TimeDriver.reschedule}"

        def _() -> None:
            self._call = None
            work()

        if self._call is not None:
            self._call.cancel()
        self._call = self._loop.call_at(max(0, desiredTime), _)

    def unschedule(self) -> None:
        "Implementation of L{TimeDriver.unschedule}"
        if self._call is not None:
            self._call.cancel()
            self._call = None

    def now(self) -> float:
        "Implementation of L{TimeDriver.now}"
        return self._loop.time()


_TimeDriverCheck: type[TimeDriver[float]] = AsyncioTimeDriver


@dataclass
class AsyncioAsyncDriver:
    """
    Driver for L{Future}-flavored awaitables.

    @see: L{fritter.repeat.Async}

    @see: L{TimeDriver}
    """

    _loop: AbstractEventLoop = field(default_factory=get_event_loop)

    def newWithCancel(self, cancel: Callable[[], None]) -> Future[None]:
        """
        Create a new L{Future} with the given callback to execute when
        cancelled.
        """
        f = Future[None](loop=self._loop)

        @f.add_done_callback
        def done(future: Future[None]) -> None:
            if f.cancelled():
                cancel()

        return f

    def complete(self, asyncObj: Future[None]) -> None:
        "The asynchronous operation completed successfully."
        asyncObj.set_result(None)

    def runAsync(
        self, coroutine: Coroutine[Future[None], Any, Any]
    ) -> Future[None]:
        """
        Run the given task on the event loop with L{asyncio.create_task}.
        """
        return self._loop.create_task(coroutine)


_AsyncioDriverCheck: type[AsyncDriver[Future[None]]] = AsyncioAsyncDriver


def scheduler(
    loop: LoopTimeInterface | None = None,
    queue: (
        PriorityQueue[ConcreteScheduledCall[float, Callable[[], None], int]]
        | None
    ) = None,
) -> Scheduler[float, Callable[[], None], int]:
    """
    Create a scheduler that uses Asyncio.
    """
    return schedulerFromDriver(
        AsyncioTimeDriver(loop if loop is not None else get_event_loop()),
        queue=queue if queue is not None else Heap(),
    )
