from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import timedelta
from json import dump, load
from os.path import exists
from zoneinfo import ZoneInfo

from datetype import DateTime
from fritter.drivers.datetime import DateTimeDriver
from fritter.drivers.sleep import SleepDriver
from fritter.persistent.json import JSONableScheduler, JSONObject, JSONRegistry

registry = JSONRegistry[dict[str, str]]()


@dataclass
class Reminder:
    text: str
    scheduler: JSONableScheduler

    @classmethod
    def typeCodeForJSON(cls) -> str:
        return "reminder"

    def asJSON(self) -> dict[str, object]:
        return {"text": self.text}

    @classmethod
    def fromJSON(
        cls,
        registry: JSONRegistry[dict[str, str]],
        scheduler: JSONableScheduler,
        loadContext: dict[str, str],
        json: JSONObject,
    ) -> Reminder:
        return cls(json["text"], scheduler)

    @registry.method
    def remind(self) -> None:
        print(f"Reminder: {self.text}")


def wakeAndRun() -> JSONableScheduler:
    driver = SleepDriver()
    if exists(FILENAME):
        with open(FILENAME) as f:
            scheduler = registry.load(driver, load(f), {})
    else:
        scheduler = JSONableScheduler(DateTimeDriver(driver))

    driver.block(1.0)
    return scheduler


def remind(scheduler: JSONableScheduler, seconds: int, message: str) -> None:
    scheduler.callAt(
        DateTime.now(ZoneInfo(key="America/Los_Angeles"))
        + timedelta(seconds=seconds),
        Reminder(message, scheduler).remind,
    )


FILENAME = "saved-schedule.json"
if __name__ == "__main__":
    scheduler = wakeAndRun()

    extraArgs = sys.argv[1:]
    if extraArgs:
        remind(scheduler, int(extraArgs[0]), " ".join(extraArgs[1:]))

    with open(FILENAME, "w") as f:
        dump(registry.save(scheduler), f)
