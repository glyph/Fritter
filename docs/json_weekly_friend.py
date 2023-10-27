from __future__ import annotations

from dataclasses import dataclass

from fritter.boundaries import Cancellable
from fritter.persistent.json import JSONableScheduler, JSONObject, JSONRegistry

registry = JSONRegistry[dict[str, str]]()


@dataclass
class FriendReminder:
    filename: str
    current: int

    @classmethod
    def typeCodeForJSON(cls) -> str:
        return ".".join([cls.__module__, cls.__name__])

    def asJSON(self) -> dict[str, object]:
        return {"filename": self.filename,
                "current": self.current}

    @classmethod
    def fromJSON(
        cls,
        registry: JSONRegistry[dict[str, str]],
        scheduler: JSONableScheduler,
        loadContext: dict[str, str],
        json: JSONObject,
    ) -> FriendReminder:
        return cls(json["filename"], json["current"])

    @registry.method
    def later(self) -> None:
        print("my value is", self.value)

    @registry.repeatMethod
    def repeat(self, steps: int, stopper: Cancellable) -> None:
        print(f"performing {steps} steps at {self.value}")
        self.value += steps
        if self.value > 10:
            stopper.cancel()
