from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

from datetype import DateTime
from fritter.drivers.datetime import guessLocalZone
from fritter.drivers.sleep import SleepDriver
from fritter.persistent.json import (
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

    def asJSON(
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
    context: dict[Any, Any] = {}
    with schedulerAtPath(
        registry,
        driver := SleepDriver(),
        Path("saved-schedule.json"),
        context,
    ) as sched:
        driver.block(1.0)
        if newReminder:
            newTime, message = newReminder
            remind(sched, newTime, message)


if __name__ == "__main__":
    args = sys.argv[1:]
    reminder = None if not args else (int(args[0]), " ".join(args[1:]))
    runScheduler(reminder)
