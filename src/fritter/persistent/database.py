"""
Generalized database backed storage for scheduled work.

For the purposes of this module, a “database” is a remote (meaning,
asynchronous) data store that could potentially store a large volume of work.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Generic, Protocol, TypeVar

from ..boundaries import (
    IDT,
    AsyncDriver,
    CancellableAwaitable,
    ScheduledCall,
    ScheduledState,
    Scheduler,
    TimeDriver,
    WhenT,
)

WhatT = TypeVar("WhatT", bound=Callable[[], Awaitable[object]])


class TimedCallStorage(Protocol[WhenT, WhatT, IDT]):
    """
    A L{TimedCallStorage} is a storage backend that can store a particular type
    of callable, representative of a single transaction context where timed
    work will be executed, and implements all the queries necessary for L{run}
    to schedule work against the given database.
    """

    async def nextTimedCallTime(self) -> WhenT | None:
        """
        Query the database for when the soonest callable is scheduled, so we
        will know when to wake up.
        """

    async def loadNextTimedCall(self) -> tuple[WhenT, WhatT, IDT]:
        """
        Query the database to find the soonest callable; called when we now
        believe it is time to call.
        """

    async def storeTimedCall(self, when: WhenT, what: WhatT) -> IDT:
        """
        Here's some work to do, store it in the database for later.
        """

    async def cancelTimedCall(self, id: IDT) -> None:
        """
        Cancel this work previously scheduled by storeTimedCall.
        """


class TimedCallStorageTxn(Protocol[WhenT, WhatT, IDT]):
    """
    A L{TimedCallStorageTxn} is an L{AsyncContextManager} that has a context of
    a L{TimedCallStorage}.

    This represents a database transaction which ought to commit its work in
    the event of a successful return, or sends its callable to a dead-letter
    queue or rolls back the transaction in the event of an exception.
    """

    async def __aenter__(self) -> TimedCallStorage[WhenT, WhatT, IDT]:
        """
        Start a transaction with the callable storage.
        """

    async def __aexit__(
        self,
        exc_type: type[Exception],
        exc_value: Exception,
        traceback: object,
    ) -> None:
        """
        End the transaction started with L{__aenter__}.
        """


@dataclass
class _DBScheduledCall(Generic[WhenT, WhatT, IDT]):
    """
    A scheduled call persitent within a L{DatabaseScheduler}.
    """

    dbs: DatabaseScheduler[WhenT, WhatT, IDT]
    id: IDT
    when: WhenT
    what: WhatT
    _saved: bool = False
    _cancelled: bool = False
    _persistTask: CancellableAwaitable[object, object, object] | None = None

    @property
    def state(self) -> ScheduledState:
        if self._cancelled:
            return ScheduledState.cancelled
        return ScheduledState.pending

    @classmethod
    def create(
        cls,
        dbs: DatabaseScheduler[WhenT, WhatT, IDT],
        when: WhenT,
        what: WhatT,
    ) -> _DBScheduledCall[WhenT, WhatT, IDT]:
        self = cls(dbs, dbs._idgen(), when, what)
        self._persistTask = dbs._asyncDriver.runAsync(self._persist())
        return self

    async def _persist(self) -> None:
        async with await self.dbs._database() as cs:
            await cs.storeTimedCall(self.when, self.what)
        self._saved = True

    def cancel(self) -> None:
        if self._persistTask is not None:
            self._persistTask.cancel()
            self._persistTask = None

        async def doCancel() -> None:
            async with await self.dbs._database() as cs:
                await cs.cancelTimedCall(self.id)
            self._cancelled = True

        self.dbs._asyncDriver.runAsync(doCancel())


@dataclass
class DatabaseScheduler(Generic[WhenT, WhatT, IDT]):
    """
    A L{DatabaseScheduler} implements an abstract L{Scheduler} in terms of a
    database, where a database is defined as an async callable that can produce
    a L{TimedCallStorageTxn} on demand.
    """

    _database: Callable[[], Awaitable[TimedCallStorageTxn[WhenT, WhatT, IDT]]]
    _timeDriver: TimeDriver[WhenT]
    _asyncDriver: AsyncDriver[CancellableAwaitable[object, object, object]]
    _idgen: Callable[[], IDT]

    def now(self) -> WhenT:
        return self._timeDriver.now()

    def callAt(
        self, when: WhenT, what: WhatT
    ) -> ScheduledCall[WhenT, WhatT, IDT]:
        savingCall = _DBScheduledCall(self, self._idgen(), when, what)
        return savingCall


async def run(
    database: Callable[[], Awaitable[TimedCallStorageTxn[WhenT, WhatT, IDT]]],
    timeDriver: TimeDriver[WhenT],
    asyncDriver: AsyncDriver[CancellableAwaitable[Any, Any, Any]],
    idGenerator: Callable[[], IDT],
) -> Scheduler[WhenT, WhatT, IDT]:
    """
    Begin periodically querying the database connected to by C{database} for
    new work to do.
    """

    async def work() -> None:
        async with await database() as cs:
            t = await cs.nextTimedCallTime()
            if t is None:
                return
            # TODO: batching; we should bail out every so often so we don't
            # build gigantic transactions?
            while t < timeDriver.now():
                t, what, callableID = await cs.loadNextTimedCall()
                # TODO: failure handling & reporting

                # there's a problem here: we are trying ot represent an
                # abstract scheduler here.  Schedulers, intentionally, put a
                # bound on WhatT, making sure that it is a Callable[[],
                # None]. By ensuring that it takes no arguments, we ensure that
                # we can call it. But enforcing the None return type is just as
                # important: in this case, we *need* the work to be awaitable,
                # in case it requires being awaited in the context of its
                # database, to ensure it's complete before we commit its
                # transaction out from under it or interleave some other timed
                # call's work.  However, in many other cases, where the
                # scheduler will *not* be awaiting the callable, if the
                # callable *were* to return an Awaitable, or more to the point
                # a Coroutine that needs to be awaited to even start, that
                # scheduler would totally fail to make that work occur.  So
                # Scheduler and AsyncScheduler are going to be necessarily
                # different interfaces.
                await what()

            def doRunAsync() -> None:
                asyncDriver.runAsync(work())

            timeDriver.reschedule(t, doRunAsync)

    asyncDriver.runAsync(work())
    return DatabaseScheduler(database, timeDriver, asyncDriver, idGenerator)


__all__ = [
    "run",
]
# dbxs instantiation of this is going to require some kind of schema
# registration to use. similar to JSON version, where there's a registry and
# then it knows what tables to go off and look at, either because each has
# denormalized columns or because
