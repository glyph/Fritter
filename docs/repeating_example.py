from asyncio import run

from fritter.boundaries import (
    Cancellable,
    PhysicalScheduler,
)
from fritter.drivers.asyncio import AsyncioAsyncDriver, AsyncioTimeDriver
from fritter.repeat import Async
from fritter.repeat.rules.seconds import EverySecond
from fritter.scheduler import schedulerFromDriver


# example coroutine
async def example() -> None:
    scheduler: PhysicalScheduler = schedulerFromDriver(AsyncioTimeDriver())
    repeatedly = Async(AsyncioAsyncDriver()).repeatedly
    times = 0

    # work function
    async def work(steps: int, stopper: Cancellable) -> None:
        nonlocal times
        times += steps
        print(times, f"times: {times} {scheduler.now()}", flush=True)
        if times > 3:
            stopper.cancel()

    await repeatedly(scheduler, EverySecond(0.25), work)


# run
run(example())
