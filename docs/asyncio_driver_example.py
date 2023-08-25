from fritter.drivers.asyncio import AsyncioTimeDriver
from fritter.scheduler import SimpleScheduler
from asyncio import run, Future


async def example() -> None:
    s = SimpleScheduler(AsyncioTimeDriver())
    f = Future[None]()

    def bye() -> None:
        f.set_result(None)

    start = s.now()
    s.callAt(start + 1.5, bye)
    await f
    end = s.now()
    print(f"elapsed={end-start}")


run(example())
