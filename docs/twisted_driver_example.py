from fritter.boundaries import PhysicalScheduler
from fritter.drivers.twisted import TwistedTimeDriver
from fritter.scheduler import schedulerFromDriver
from twisted.internet.defer import Deferred
from twisted.internet.interfaces import IReactorTime
from twisted.internet.task import react


async def example(reactor: IReactorTime) -> None:
    s: PhysicalScheduler = schedulerFromDriver(TwistedTimeDriver(reactor))
    f = Deferred[None]()

    def bye() -> None:
        f.callback(None)

    start = s.now()
    s.callAt(start + 1.5, bye)
    await f
    end = s.now()
    print(f"elapsed={end-start}")


react(example)
