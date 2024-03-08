from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

from datetype import DateTime
from fritter.drivers.datetimes import guessLocalZone, DateTimeDriver
from fritter.drivers.sleep import SleepDriver
from fritter.persistent.jsonable import (
    JSONableInstance,
    JSONableScheduler,
    JSONObject,
    JSONRegistry,
    LoadProcess,
    schedulerAtPath,
)

# start-registry
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

    def toJSON(
        self,
        registry: JSONRegistry[object],
    ) -> dict[str, object]:
        return {"text": self.text}

    @classmethod
    def fromJSON(
        cls,
        load: LoadProcess[object],
        json: JSONObject,
    ) -> Reminder:
        return cls(json["text"])
        # end-reminder-methods

    # app-method
    @registry.method
    def show(self) -> None:
        print(f"Reminder! {self.text}")
        # end-reminder


r: JSONableInstance[object] = Reminder("hi")


def remind(
    scheduler: JSONableScheduler[dict[Any, Any]],
    seconds: int,
    message: str,
) -> None:
    now = DateTime.now(guessLocalZone())
    later = now + timedelta(seconds=seconds)
    work = Reminder(message).show
    scheduler.callAt(later, work)


def runScheduler(newReminder: tuple[int, str] | None) -> None:
    bootstrap: dict[Any, Any] = {}
    with schedulerAtPath(
        registry,
        DateTimeDriver(driver := SleepDriver()),
        Path("saved-schedule.json"),
        bootstrap,
    ) as sched:
        driver.block(1.0)
        if newReminder:
            newTime, message = newReminder
            remind(sched, newTime, message)


if __name__ == "__main__":
    args = sys.argv[1:]
    reminder = None if not args else (int(args[0]), " ".join(args[1:]))
    runScheduler(reminder)
