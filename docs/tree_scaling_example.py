# setup
from fritter.drivers.memory import MemoryDriver
from fritter.scheduler import SimpleScheduler
from fritter.tree import branch, timesFaster

driver = MemoryDriver()
parent = SimpleScheduler(driver)
rate = 3.0
group, child = branch(parent, timesFaster(rate))
# end setup


# showfunc
def loop(scheduler: SimpleScheduler, name: str, interval: float = 1.0) -> None:
    def _() -> None:
        print(name)
        scheduler.callAt(scheduler.now() + interval, _)

    _()


# end showfunc

# loops
loop(parent, "parent", 1.0)
loop(child, "child", 1.0)
# work
for again in range(10):
    driver.advance()
    rate += 1
    group.changeScale(timesFaster(rate))
    print(f"time: parent={parent.now()} child={child.now()}")
