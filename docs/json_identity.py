from __future__ import annotations

from dataclasses import dataclass

from fritter.boundaries import Cancellable
from fritter.persistent.json import JSONableScheduler, JSONObject, JSONRegistry

registry: JSONRegistry[dict[int, MyClass]] = JSONRegistry()


@dataclass
class MyClass:
    value: int

    @classmethod
    def typeCodeForJSON(cls) -> str:
        return ".".join([cls.__module__, cls.__name__])

    def asJSON(self) -> dict[str, object]:
        return {"value": self.value, "id": id(self)}

    @classmethod
    def fromJSON(
        cls,
        registry: JSONRegistry[dict[int, MyClass]],
        scheduler: JSONableScheduler,
        loadContext: dict[int, MyClass],
        json: JSONObject,
    ) -> MyClass:
        loadingID = int(json["id"])
        if loadingID in loadContext:
            return loadContext[loadingID]
        else:
            self = cls(json["value"])
            loadContext[loadingID] = self
            return self

    @registry.method
    def later(self) -> None:
        print("my value is", self.value)

    @registry.repeatMethod
    def repeat(self, steps: int, stopper: Cancellable) -> None:
        print(f"performing {steps} steps at {self.value}")
        self.value += steps
        if self.value > 10:
            stopper.cancel()
