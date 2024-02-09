# setup
from fritter.drivers.memory import MemoryDriver
from fritter.scheduler import SimpleScheduler
from fritter.tree import branch, timesFaster

driver = MemoryDriver()
trunk = SimpleScheduler(driver)
rate = 3.0
manager, branched = branch(trunk, timesFaster(rate))
# end setup


# showfunc
def loop(scheduler: SimpleScheduler, name: str, interval: float = 1.0) -> None:
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
