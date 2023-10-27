from __future__ import annotations

import sys
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta
from json import dump, load
from pathlib import Path
from typing import Iterator
from zoneinfo import ZoneInfo

from datetype import DateTime
from fritter.drivers.datetime import DateTimeDriver
from fritter.drivers.sleep import SleepDriver
from fritter.persistent.json import JSONableScheduler, JSONObject, JSONRegistry

registry = JSONRegistry[object]()
# end-registry


# reminder-class
@dataclass
class Reminder:
    text: str
    # reminder-methods

    @classmethod
    def typeCodeForJSON(cls) -> str:
        return "reminder"

    def asJSON(self) -> dict[str, object]:
        return {"text": self.text}

    @classmethod
    def fromJSON(
        cls,
        registry: JSONRegistry[object],
        scheduler: JSONableScheduler,
        loadContext: object,
        json: JSONObject,
    ) -> Reminder:
        return cls(json["text"])

    # app-method
    @registry.method
    def show(self) -> None:
        print(f"Reminder! {self.text}")
        # end reminder


saved = Path("saved-schedule.json")


@contextmanager
def schedulerLoaded() -> Iterator[JSONableScheduler]:
    driver = SleepDriver()
    if saved.exists():
        with saved.open() as f:
            scheduler = registry.load(driver, load(f), {})
    else:
        scheduler = JSONableScheduler(DateTimeDriver(driver))
    driver.block(1.0)
    yield scheduler
    with saved.open("w") as f:
        dump(registry.save(scheduler), f)


def remind(scheduler: JSONableScheduler, seconds: int, message: str) -> None:
    scheduler.callAt(
        DateTime.now(ZoneInfo(key="America/Los_Angeles"))
        + timedelta(seconds=seconds),
        Reminder(message).show,
    )


if __name__ == "__main__":
    with schedulerLoaded() as scheduler:
        extraArgs = sys.argv[1:]
        if extraArgs:
            remind(scheduler, int(extraArgs[0]), " ".join(extraArgs[1:]))
