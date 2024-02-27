from fritter.boundaries import Cancellable
from fritter.repeat import repeatedly
from fritter.repeat.rules.seconds import EverySecond
from fritter.drivers.sleep import SleepDriver
from fritter.scheduler import newScheduler

# driver setup
driver = SleepDriver()
start = driver.now()


# repeating work
def work(steps: int, stopper: Cancellable) -> None:
    elapsed = driver.now() - start
    print(f"took {steps} steps at {elapsed:0.2f}")
    if elapsed >= 2.0:
        stopper.cancel()


# kick off scheduler
repeatedly(newScheduler(driver), work, EverySecond(0.05))
steps = driver.block()
print(f"took {steps } steps, then stopped")
