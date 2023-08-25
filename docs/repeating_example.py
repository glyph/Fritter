from fritter.boundaries import Cancellable
from fritter.repeat import Async, EverySecond
from fritter.drivers.asyncio import AsyncioTimeDriver, AsyncioAsyncDriver
from fritter.scheduler import SimpleScheduler
from asyncio import run


async def example() -> None:
    d = AsyncioTimeDriver()
    s = SimpleScheduler(d)
    times = 0

    async def work(steps: int, stopper: Cancellable) -> None:
        nonlocal times
        times += steps
        print(times, "time" + ("s" * bool(times)), d.now(), flush=True)
        if times > 3:
            stopper.cancel()

    print("begin")
    a = Async(AsyncioAsyncDriver())
    await a.repeatedly(s, EverySecond(0.25), work)
    print("end")


run(example())
