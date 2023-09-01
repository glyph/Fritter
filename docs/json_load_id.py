from json import dump, load

# from fritter.drivers.memory import MemoryDriver
from fritter.drivers.sleep import SleepDriver

from json_identity import registry

driver = SleepDriver()

with open("saved-id-schedule.json", "r") as f:
    s = registry.load(driver, load(f), {})

driver.block(1.7)

with open("saved-id-schedule.json", "w") as f:
    dump(registry.save(s), f)
