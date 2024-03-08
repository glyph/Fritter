from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from json import dumps, loads
from typing import Any, Callable, Iterator
from zoneinfo import ZoneInfo

from datetype import DateTime, aware
from fritter.boundaries import SomeScheduledCall, TimeDriver
from fritter.drivers.datetimes import DateTimeDriver, guessLocalZone
from fritter.drivers.memory import MemoryDriver
from fritter.drivers.sleep import SleepDriver
from fritter.persistent.jsonable import (
    JSONableScheduler,
    JSONObject,
    JSONRegistry,
    LoadProcess,
    dateTypeAsJSON,
    dateTypeFromJSON,
)
from fritter.repeat.rules.datetimes import weekly, yearly

registry: JSONRegistry[FriendList] = JSONRegistry()


@dataclass
class FriendList:
    friendsByName: dict[str, Friend] = field(default_factory=dict)
    loadingFriends: dict[str, dict[str, object]] = field(default_factory=dict)
    scheduler: JSONableScheduler[FriendList] = field(init=False)
    saver: Callable[[], JSONObject] = field(init=False)

    def getFriendNamed(
        self, name: str, load: LoadProcess[FriendList]
    ) -> Friend:
        self.scheduler = load.scheduler
        if name not in self.friendsByName:
            blob = self.loadingFriends.pop(name)
            self.friendsByName[name] = Friend.fromFriendListJSON(blob, load)
        return self.friendsByName[name]

    def save(self) -> dict[str, Any]:
        return {
            "friends": {
                (blob := friend.asFriendListJSON())["name"]: blob
                for friend in self.friendsByName.values()
            },
            "scheduler": self.saver(),
        }

    @classmethod
    def load(
        cls, driver: TimeDriver[float], json: dict[str, Any]
    ) -> FriendList:
        self = cls(loadingFriends=json["friends"])
        scheduler, saver = registry.loadScheduler(
            DateTimeDriver(driver), json["scheduler"], self
        )
        self.saver = saver
        self.scheduler = scheduler
        assert not self.loadingFriends
        return self

    @classmethod
    def typeCodeForJSON(cls) -> str:
        return "friend-list"

    def toJSON(self, registry: JSONRegistry[object]) -> dict[str, object]:
        return {}

    @classmethod
    def fromJSON(
        cls, load: LoadProcess[FriendList], json: JSONObject
    ) -> FriendList:
        return load.bootstrap

    @registry.repeatMethod
    def weeklyReminder(self, steps: int, scheduled: SomeScheduledCall) -> None:
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
            name, birthdayDay, birthdayMonth, lastContact, self.scheduler
        )
        f.birthdaySetup()
        return f

    @classmethod
    def new(cls, driver: TimeDriver[float]) -> FriendList:
        self = cls()
        self.scheduler, self.saver = registry.createScheduler(DateTimeDriver(driver))
        registry.repeatedly(self.scheduler, weekly, self.weeklyReminder)
        return self


TZ = guessLocalZone()


def now() -> DateTime[ZoneInfo]:
    return DateTime.now(TZ)


GRACE_DAYS = 3


# friend-class
@dataclass
class Friend:
    name: str
    birthdayMonth: int
    birthdayDay: int
    lastContact: DateTime[ZoneInfo]
    scheduler: JSONableScheduler[FriendList]
    # end-friend-fields

    def asFriendListJSON(self) -> dict[str, object]:
        return {
            "name": self.name,
            "birthdayDay": self.birthdayDay,
            "birthdayMonth": self.birthdayMonth,
            "lastContact": dateTypeAsJSON(self.lastContact),
        }

    @classmethod
    def fromFriendListJSON(
        cls, json: dict[str, Any], load: LoadProcess[FriendList]
    ) -> Friend:
        return cls(
            json["name"],
            json["birthdayDay"],
            json["birthdayMonth"],
            dateTypeFromJSON(json["lastContact"]),
            load.scheduler,
        )

    @classmethod
    def typeCodeForJSON(cls) -> str:
        return "friend"

    def toJSON(self, registry: JSONRegistry[object]) -> dict[str, object]:
        return {"name": self.name}

    @classmethod
    def fromJSON(
        cls, load: LoadProcess[FriendList], json: JSONObject
    ) -> Friend:
        return load.bootstrap.getFriendNamed(json["name"], load)

    def birthdaySetup(self) -> None:
        now = self.scheduler.now()
        bday = now.replace(day=self.birthdayDay, month=self.birthdayMonth)
        if bday < now:
            bday = bday.replace(year=bday.date().year + 1)
        registry.repeatedly(
            self.scheduler, yearly, self.everyBirthday, reference=bday
        )

    @registry.repeatMethod
    def everyBirthday(
        self, steps: list[DateTime[ZoneInfo]], scheduled: SomeScheduledCall
    ) -> None:
        if not steps:
            print(f"setting up reminder for {self.name}'s birthday")
            return
        now = self.scheduler.now()
        delta = now - steps[-1]
        if delta > timedelta(days=GRACE_DAYS * 2):
            print(f"Never mind, missed {self.name}'s birthday")
            return
        print(
            f"Remember to wish {self.name} a happy birthday on {steps[-1].date()} (it's {now.date()})"
        )
        self.lastContact = now


SAVED_BLOB = ""


@contextmanager
def listLoaded(driver: TimeDriver[float]) -> Iterator[FriendList]:
    global SAVED_BLOB
    if SAVED_BLOB:
        friendList = FriendList.load(driver, loads(SAVED_BLOB))
    else:
        friendList = FriendList.new(driver)
    yield friendList
    SAVED_BLOB = dumps(friendList.save())


@contextmanager
def realTimeList() -> Iterator[FriendList]:
    driver = SleepDriver()
    with listLoaded(driver) as fl:
        driver.block(1.0)
        yield fl


@dataclass
class Storyteller:
    currentTime: DateTime[ZoneInfo]

    @contextmanager
    def fakeTimeList(self, toAdvance: float) -> Iterator[FriendList]:
        driver = MemoryDriver(self.currentTime.timestamp())
        with listLoaded(driver) as fl:
            yield fl
            driver.advance(toAdvance)
        self.currentTime = DateTime.fromtimestamp(driver.now(), tz=TZ)


TZ = guessLocalZone()


def story() -> None:
    start = aware(datetime(2023, 11, 1, 9, 0, 0, tzinfo=TZ), ZoneInfo)
    st = Storyteller(start)

    print("day 1", st.currentTime)
    with st.fakeTimeList(0) as fl1:
        fl1.add("alice", 12, 1, start)
        fl1.add("bob", 12, 15, start)

    print("run 1", st.currentTime)
    with st.fakeTimeList(timedelta(days=10).total_seconds()):
        pass

    print("run 2", st.currentTime)
    with st.fakeTimeList(timedelta(days=20).total_seconds()):
        pass

    print("run 3", st.currentTime)
    with st.fakeTimeList(timedelta(days=10).total_seconds()):
        pass

    print("run 4", st.currentTime)
    with st.fakeTimeList(timedelta(days=10).total_seconds()):
        pass
    print("run 5", st.currentTime)
    with st.fakeTimeList(timedelta(days=10).total_seconds()):
        pass

    print("run 6", st.currentTime)
    with st.fakeTimeList(timedelta(days=50).total_seconds()):
        pass
    print("done", st.currentTime)


if __name__ == "__main__":
    story()
