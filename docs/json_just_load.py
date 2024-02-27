from json import dump, load

# from fritter.drivers.memory import MemoryDriver
from fritter.drivers.sleep import SleepDriver

from json_instance import registry

driver = SleepDriver()

with open("saved-schedule.json", "r") as f:
    scheduler, saver = registry.load(driver, load(f), {})

driver.block(1.7)

with open("saved-schedule.json", "w") as f:
    dump(saver(), f)
