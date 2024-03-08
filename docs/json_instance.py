from __future__ import annotations

from dataclasses import dataclass

from fritter.boundaries import SomeScheduledCall
from fritter.persistent.jsonable import JSONObject, JSONRegistry, LoadProcess

registry = JSONRegistry[dict[str, str]]()


@dataclass
class MyClass:
    value: int

    @classmethod
    def typeCodeForJSON(cls) -> str:
        return ".".join([cls.__module__, cls.__name__])

    def toJSON(
        self, registry: JSONRegistry[dict[str, str]]
    ) -> dict[str, object]:
        return {"value": self.value}

    @classmethod
    def fromJSON(
        cls, load: LoadProcess[dict[str, str]], json: JSONObject
    ) -> MyClass:
        return cls(json["value"])

    @registry.method
    def later(self) -> None:
        print("my value is", self.value)

    @registry.repeatMethod
    def repeat(self, steps: int, scheduled: SomeScheduledCall) -> None:
        print(f"performing {steps} steps at {self.value}")
        self.value += steps
        if self.value > 10:
            scheduled.cancel()
