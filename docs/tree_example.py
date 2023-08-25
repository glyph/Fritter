# setup
from typing import Callable
from fritter.drivers.memory import MemoryDriver
from fritter.scheduler import SimpleScheduler
from fritter.tree import branch

driver = MemoryDriver()
parent = SimpleScheduler(driver)
group, child = branch(parent)
# end setup


# showfunc
def show(name: str) -> Callable[[], None]:
    def _() -> None:
        print(f"{name} parent={parent.now()} child={child.now()}")

    return _


# end showfunc


# childcalls
child.callAt(1.0, show("child 1"))
child.callAt(2.0, show("child 2"))
child.callAt(3.0, show("child 3"))
# parentcalls
parent.callAt(1.0, show("parent 1"))
parent.callAt(2.0, show("parent 2"))
parent.callAt(3.0, show("parent 3"))
# endcalls

# interact
driver.advance()
print("pause")
group.pause()
driver.advance()
print("unpause")
group.unpause()
driver.advance()
driver.advance()
