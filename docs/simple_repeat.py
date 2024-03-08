from fritter.boundaries import SomeScheduledCall
from fritter.drivers.sleep import SleepDriver
from fritter.repeat import repeatedly
from fritter.repeat.rules.seconds import EverySecond
from fritter.scheduler import schedulerFromDriver

# driver setup
driver = SleepDriver()
start = driver.now()


# repeating work
def work(steps: int, scheduled: SomeScheduledCall) -> None:
    elapsed = driver.now() - start
    print(f"took {steps} steps at {elapsed:0.2f}")
    if elapsed >= 2.0:
        scheduled.cancel()


# kick off scheduler
repeatedly(schedulerFromDriver(driver), work, EverySecond(0.05))
steps = driver.block()
print(f"took {steps } steps, then stopped")
