from __future__ import annotations

from datetime import datetime
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import timedelta
from json import dump, load
from pathlib import Path
from typing import Any, Iterator
from zoneinfo import ZoneInfo

from datetype import DateTime, aware, fromisoformat
from fritter.boundaries import Cancellable, TimeDriver
from fritter.drivers.datetime import DateTimeDriver, guessLocalZone
from fritter.drivers.memory import MemoryDriver
from fritter.drivers.sleep import SleepDriver
from fritter.persistent.json import JSONableScheduler, JSONObject, JSONRegistry
from fritter.repeat import weekly

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

    @classmethod
    def typeCodeForJSON(cls) -> str:
        return "friend-list"

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

    @registry.repeatMethod
    def getInTouch(self, steps: int, stopper: Cancellable) -> None:
        byContact = sorted(
            self.friendsByName.values(),
            key=lambda f: f.lastContact,
        )
        if (friend := next(iter(byContact), None)) is None:
            print("nobody to get in touch with right now")
            return
        print("maybe you should get in touch with", friend.name)
        friend.lastContact = now()

    def add(
        self,
        name: str,
        birthdayDay: int,
        birthdayMonth: int,
        lastContact: DateTime[ZoneInfo],
    ) -> Friend:
        f = self.friendsByName[name] = Friend(
            name, birthdayDay, birthdayMonth, lastContact
        )
        return f

    @classmethod
    def new(
        cls, driver: TimeDriver[float]
    ) -> tuple[FriendList, JSONableScheduler]:
        self = cls()
        scheduler = JSONableScheduler(DateTimeDriver(driver))
        registry.repeatedly(scheduler, weekly, self.getInTouch)
        return self, scheduler


TZ = guessLocalZone()


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
def listLoaded(driver: TimeDriver[float]) -> Iterator[FriendList]:
    if saved.exists():
        with saved.open() as f:
            friendList, scheduler = FriendList.load(driver, load(f))
    else:
        friendList, scheduler = FriendList.new(driver)
    yield friendList
    blob = friendList.save(scheduler)
    with saved.open("w") as f:
        dump(blob, f)


@contextmanager
def realTimeList() -> Iterator[FriendList]:
    driver = SleepDriver()
    with listLoaded(driver) as fl:
        driver.block(1.0)
        yield fl


@contextmanager
def fakeTimeList(dt: DateTime[ZoneInfo]) -> Iterator[FriendList]:
    driver = MemoryDriver(dt.timestamp())
    with listLoaded(driver) as fl:
        yield fl


TZ = guessLocalZone()


def story() -> None:
    start = aware(datetime(2023, 11, 1, 9, 0, 0, tzinfo=TZ), ZoneInfo)
    with fakeTimeList(start) as fl1:
        fl1.add("alice", 12, 1, start)
        fl1.add("bob", 12, 15, start)

    with fakeTimeList(start + timedelta(days=10)):
        pass


if __name__ == "__main__":
    story()
