# imports
from datetime import timedelta
from time import time
from typing import Callable, Any
from zoneinfo import ZoneInfo

from fritter.boundaries import (
    CivilScheduler,
    PhysicalScheduler,
    PriorityDiffable,
    Scheduler,
)
from fritter.drivers.datetimes import DateScale
from fritter.drivers.memory import MemoryDriver
from fritter.scheduler import schedulerFromDriver
from fritter.tree import branch

# setup
driver = MemoryDriver()
driver.advance(time())
trunk: PhysicalScheduler = schedulerFromDriver(driver)
branched: CivilScheduler
manager, branched = branch(trunk, DateScale(ZoneInfo("US/Pacific")))
# end setup


# showfunc
def loop[dt, pd: PriorityDiffable[Any]](
    scheduler: Scheduler[pd, Callable[[], None], object],
    name: str,
    interval: dt,
) -> None:
    def _() -> None:
        print(name)
        scheduler.callAt(scheduler.now() + interval, _)

    _()
# end showfunc

# loops
loop(trunk, "trunk", 1.0)
loop(branched, "branch", timedelta(2.0))
# work
for again in range(10):
    driver.advance()
    print(f"time: trunk={trunk.now()} branch={branched.now()}")
