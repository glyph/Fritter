from __future__ import annotations

from dataclasses import dataclass

from fritter.boundaries import SomeScheduledCall
from fritter.persistent.jsonable import JSONObject, JSONRegistry, LoadProcess

registry = JSONRegistry[dict[str, str]]()


@dataclass
class FriendReminder:
    filename: str
    current: int

    @classmethod
    def typeCodeForJSON(cls) -> str:
        return ".".join([cls.__module__, cls.__name__])

    def toJSON(self, registry: JSONRegistry[object]) -> dict[str, object]:
        return {"filename": self.filename, "current": self.current}

    @classmethod
    def fromJSON(
        cls, load: LoadProcess[dict[str, str]], json: JSONObject
    ) -> FriendReminder:
        return cls(json["filename"], json["current"])

    @registry.method
    def later(self) -> None:
        print("my value is", self.current)

    @registry.repeatMethod
    def repeat(self, steps: int, scheduled: SomeScheduledCall) -> None:
        self.current += steps
        print(f"performing {steps} steps at {self.current}")
        if self.current > 10:
            scheduled.cancel()
