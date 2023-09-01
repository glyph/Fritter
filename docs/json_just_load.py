from json import dump, load

# from fritter.drivers.memory import MemoryDriver
from fritter.drivers.sleep import SleepDriver

from json_instance import registry

driver = SleepDriver()

with open("saved-schedule.json", "r") as f:
    s = registry.load(driver, load(f), {})

driver.block()

with open("saved-schedule.json", "w") as f:
    dump(registry.save(s), f)
