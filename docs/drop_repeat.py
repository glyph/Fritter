from time import sleep

from fritter.boundaries import SomeScheduledCall
from fritter.drivers.sleep import SleepDriver
from fritter.repeat import repeatedly
from fritter.repeat.rules.seconds import EverySecond
from fritter.scheduler import schedulerFromDriver

driver = SleepDriver()
start = driver.now()


def work(steps: int, scheduled: SomeScheduledCall) -> None:
    elapsed = driver.now() - start
    # start slow
    if elapsed < 1.0:
        sleep(0.2)
    # end slow
    print(f"took {steps} steps at {elapsed:0.2f}")
    if elapsed >= 2.0:
        scheduled.cancel()


repeatedly(schedulerFromDriver(driver), work, EverySecond(0.05))
print(f"called {driver.block()} functions, then stopped")
