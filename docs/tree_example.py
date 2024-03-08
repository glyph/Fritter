# setup
from typing import Callable

from fritter.boundaries import PhysicalScheduler
from fritter.drivers.memory import MemoryDriver
from fritter.scheduler import schedulerFromDriver
from fritter.tree import branch

driver = MemoryDriver()
trunk: PhysicalScheduler = schedulerFromDriver(driver)
manager, branched = branch(trunk)
# end setup


# showfunc
def show(name: str) -> Callable[[], None]:
    def _() -> None:
        print(f"{name} trunk={trunk.now()} branch={branched.now()}")

    return _


# end showfunc


# branchcalls
branched.callAt(1.0, show("branch 1"))
branched.callAt(2.0, show("branch 2"))
branched.callAt(3.0, show("branch 3"))
# trunkcalls
trunk.callAt(1.0, show("trunk 1"))
trunk.callAt(2.0, show("trunk 2"))
trunk.callAt(3.0, show("trunk 3"))
# endcalls

# interact
driver.advance()
print("pause")
manager.pause()
driver.advance()
print("unpause")
manager.unpause()
driver.advance()
driver.advance()
