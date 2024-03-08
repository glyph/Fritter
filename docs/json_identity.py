from __future__ import annotations

from dataclasses import dataclass

from fritter.boundaries import SomeScheduledCall
from fritter.persistent.jsonable import JSONObject, JSONRegistry, LoadProcess

registry: JSONRegistry[dict[int, MyClass]] = JSONRegistry()


@dataclass
class MyClass:
    value: int

    @classmethod
    def typeCodeForJSON(cls) -> str:
        return ".".join([cls.__module__, cls.__name__])

    def toJSON(self, registry: JSONRegistry[object]) -> dict[str, object]:
        return {"value": self.value, "id": id(self)}

    @classmethod
    def fromJSON(
        cls, load: LoadProcess[dict[int, MyClass]], json: JSONObject
    ) -> MyClass:
        loadingID = int(json["id"])
        if loadingID in load.bootstrap:
            return load.bootstrap[loadingID]
        else:
            self = cls(json["value"])
            load.bootstrap[loadingID] = self
            return self

    @registry.method
    def later(self) -> None:
        print("my value is", self.value)

    @registry.repeatMethod
    def repeat(self, steps: int, scheduled: SomeScheduledCall) -> None:
        print(f"performing {steps} steps at {self.value}")
        self.value += steps
        if self.value > 10:
            scheduled.cancel()
