# setup
from fritter.drivers.memory import MemoryDriver
from fritter.scheduler import SimpleScheduler
from fritter.tree import branch

driver = MemoryDriver()
parent = SimpleScheduler(driver)
group, child = branch(parent, 3.0)
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
    group.scaleFactor += 1.0
    print(f"time: parent={parent.now()} child={child.now()}")
