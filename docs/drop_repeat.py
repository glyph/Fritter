from fritter.boundaries import Cancellable
from fritter.repeat import EverySecond, repeatedly
from fritter.drivers.sleep import SleepDriver
from fritter.scheduler import Scheduler
from time import sleep

driver = SleepDriver()
start = driver.now()

def work(steps: int, stopper: Cancellable) -> None:
    elapsed = driver.now() - start
    # start slow
    if elapsed < 1.0:
        sleep(0.2)
    # end slow
    print(f"took {steps} steps at {elapsed:0.2f}")
    if elapsed >= 2.0:
        stopper.cancel()

repeatedly(Scheduler(driver), work, EverySecond(0.05))
print(f"called {driver.block()} functions, then stopped")
