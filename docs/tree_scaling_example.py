# setup
from fritter.drivers.memory import MemoryDriver
from fritter.scheduler import schedulerFromDriver
from fritter.tree import branch, timesFaster
from fritter.boundaries import PhysicalScheduler

driver = MemoryDriver()
trunk: PhysicalScheduler = schedulerFromDriver(driver)
rate = 3.0
manager, branched = branch(trunk, timesFaster(rate))
# end setup


# showfunc
def loop(scheduler: PhysicalScheduler, name: str, interval: float = 1.0) -> None:
    def _() -> None:
        print(name)
        scheduler.callAt(scheduler.now() + interval, _)

    _()


# end showfunc

# loops
loop(trunk, "trunk", 1.0)
loop(branched, "branch", 1.0)
# work
for again in range(10):
    driver.advance()
    rate += 1
    manager.changeScale(timesFaster(rate))
    print(f"time: trunk={trunk.now()} branch={branched.now()}")
