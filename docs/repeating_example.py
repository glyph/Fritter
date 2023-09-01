from fritter.boundaries import Cancellable
from fritter.repeat import Async, EverySecond
from fritter.drivers.asyncio import AsyncioTimeDriver, AsyncioAsyncDriver
from fritter.scheduler import SimpleScheduler
from asyncio import run

# example coroutine
async def example() -> None:
    scheduler = SimpleScheduler(AsyncioTimeDriver())
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
