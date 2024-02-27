from asyncio import Future, run

from fritter.boundaries import PhysicalScheduler
from fritter.drivers.asyncio import AsyncioTimeDriver
from fritter.scheduler import newScheduler


async def example() -> None:
    s: PhysicalScheduler = newScheduler(AsyncioTimeDriver())
    f = Future[None]()

    def bye() -> None:
        f.set_result(None)

    start = s.now()
    s.callAt(start + 1.5, bye)
    await f
    end = s.now()
    print(f"elapsed={end-start}")


run(example())
