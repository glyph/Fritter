"""
Generalized database backed storage for scheduled work.

For the purposes of this module, a “database” is a remote (meaning,
asynchronous) data store that could potentially store a large volume of work.
"""

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Generic, Protocol

from fritter.boundaries import CancellableAwaitable, ScheduledCall, TimeDriver

from ..boundaries import IDT, AsyncDriver, Scheduler, WhatT, WhenT


class CallableStorage(Protocol[WhenT, WhatT, IDT]):
    async def nextCallableTime(self) -> WhenT | None:
        """
        Query the database for when the soonest callable is scheduled, so we
        will know when to wake up.
        """

    async def loadNextCallable(self) -> tuple[WhenT, WhatT]:
        """
        Query the database to find the soonest callable; called when we now
        believe it is time to call.
        """

    async def storeCallable(self, when: WhenT, what: WhatT) -> IDT:
        """
        Here's some work to do, store it in the database for later.
        """

    async def cancelCallable(self, id: IDT) -> None:
        """
        Cancel this work previously scheduled by storeCallable.
        """


class CallableStorageTxn(Protocol[WhenT, WhatT, IDT]):
    async def __aenter__(self) -> CallableStorage[WhenT, WhatT, IDT]:
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
class DatabaseScheduler(Generic[WhenT, WhatT, IDT]):
    _database: Callable[[], Awaitable[CallableStorageTxn[WhenT, WhatT, IDT]]]
    _timeDriver: TimeDriver[WhenT]

    def now(self) -> WhenT:
        return self._timeDriver.now()

    def callAt(
        self, when: WhenT, what: WhatT
    ) -> ScheduledCall[WhenT, WhatT, IDT]:
        async with await self._database() as cs:
            # nested transaction problem in here, don't like that
            await cs.storeCallable()


async def run(
    database: Callable[[], Awaitable[CallableStorageTxn[WhenT, WhatT, IDT]]],
    timeDriver: TimeDriver[WhenT],
    asyncDriver: AsyncDriver[CancellableAwaitable[Any, Any, Any]],
) -> Scheduler[WhenT, WhatT, IDT]:
    """
    Begin periodically querying the database connected to by C{database} for
    new work to do.
    """

    async def work() -> None:
        async with await database() as cs:
            t = await cs.nextCallableTime()
            if t is None:
                return
            while t < timeDriver.now():
                t, what = await cs.loadNextCallable()
                # TODO: failure handling & reporting
                what()

            def doRunAsync() -> None:
                asyncDriver.runAsync(work())

            timeDriver.reschedule(t, doRunAsync)

    asyncDriver.runAsync(work())
    return DatabaseScheduler(database, timeDriver)


# dbxs instantiation of this is going to require some kind of schema
# registration to use. similar to JSON version, where there's a registry and
# then it knows what tables to go off and look at, either because each has
# denormalized columns or because
