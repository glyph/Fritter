from __future__ import annotations

import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from json import dump, load
from pathlib import Path
from typing import Any, Iterator
from zoneinfo import ZoneInfo

from datetype import DateTime, fromisoformat
from fritter.boundaries import Cancellable, TimeDriver
from fritter.drivers.datetime import DateTimeDriver
from fritter.drivers.sleep import SleepDriver
from fritter.persistent.json import JSONableScheduler, JSONObject, JSONRegistry

registry: JSONRegistry[FriendList] = JSONRegistry()


@dataclass
class FriendList:
    friendsByName: dict[str, Friend] = field(default_factory=dict)

    def save(self, scheduler: JSONableScheduler) -> dict[str, Any]:
        return {
            "friends": [
                friend.asFriendListJSON()
                for friend in self.friendsByName.values()
            ],
            "scheduler": registry.save(scheduler),
        }

    @classmethod
    def load(
        cls, driver: TimeDriver[float], json: dict[str, Any]
    ) -> tuple[FriendList, JSONableScheduler]:
        friendsByName = {}
        for friendJSON in json["friends"]:
            friend = Friend.fromFriendListJSON(friendJSON)
            friendsByName[friend.name] = friend
        self = cls(friendsByName)
        return self, registry.load(driver, json["scheduler"], self)

    def asJSON(self) -> dict[str, object]:
        return {}

    @classmethod
    def fromJSON(
        cls,
        registry: JSONRegistry[FriendList],
        scheduler: JSONableScheduler,
        loadContext: FriendList,
        json: JSONObject,
    ) -> FriendList:
        return loadContext

    @classmethod
    def typeCodeForJSON(cls) -> str:
        return "friend-list"

    @registry.repeatMethod
    def getInTouch(self, steps: int, stopper: Cancellable) -> None:
        byContact = sorted(
            self.friendsByName.values(),
            key=lambda f: f.lastContact,
        )
        if (friend := next(iter(byContact), None)) is None:
            return
        print("get in touch with", friend.name)
        friend.lastContact = now()


TZ = ZoneInfo(key="America/Los_Angeles")


def now() -> DateTime[ZoneInfo]:
    return DateTime.now(TZ)


# friend-class
@dataclass
class Friend:
    name: str
    birthdayDay: int
    birthdayMonth: int
    lastContact: DateTime[ZoneInfo]
    # end-friend-fields

    def asFriendListJSON(self) -> dict[str, object]:
        return {
            "name": self.name,
            "birthdayDay": self.birthdayDay,
            "birthdayMonth": self.birthdayMonth,
            "lastContact": {
                "ts": self.lastContact.replace(tzinfo=None).isoformat(),
                "tz": self.lastContact.tzinfo.key,
            },
        }

    @classmethod
    def fromFriendListJSON(cls, json: dict[str, Any]) -> Friend:
        return cls(
            json["name"],
            json["birthdayDay"],
            json["birthdayMonth"],
            fromisoformat(json["lastContact"]["ts"]).replace(
                tzinfo=ZoneInfo(json["lastContact"]["tz"])
            ),
        )

    @classmethod
    def typeCodeForJSON(cls) -> str:
        return "friend"

    def asJSON(self) -> dict[str, object]:
        return {"name": self.name}

    @classmethod
    def fromJSON(
        cls,
        registry: JSONRegistry[FriendList],
        scheduler: JSONableScheduler,
        loadContext: FriendList,
        json: JSONObject,
    ) -> Friend:
        return loadContext.friendsByName[json["name"]]


saved = Path("friend-schedule.json")


@contextmanager
def listLoaded() -> Iterator[FriendList]:
    driver = SleepDriver()
    if saved.exists():
        with saved.open() as f:
            friendList, scheduler = FriendList.load(driver, load(f))
    else:
        friendList = FriendList()
        scheduler = JSONableScheduler(DateTimeDriver(driver))
    driver.block(1.0)
    yield friendList
    with saved.open("w") as f:
        dump(registry.save(scheduler), f)


if __name__ == "__main__":
    with listLoaded() as friendList:
        extraArgs = sys.argv[1:]
        if extraArgs:
            newFriend = extraArgs
