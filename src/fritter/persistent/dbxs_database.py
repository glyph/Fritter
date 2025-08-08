from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol

from dbxs import accessor, maybe, query, one


@dataclass
class TimedCall:
    backend: SimpleTimedStorageBackend
    id: int
    when: float
    what: str


class SimpleTimedStorageBackend(Protocol):

    @query(
        sql="SELECT when FROM timed_calls WHERE when > {now}",
        load=maybe(lambda row: float(row[0])),
    )
    async def nextTimedCallTime(self, now: float) -> float | None: ...

    @query(
        sql="SELECT id, when, what FROM timed_calls",
        load=one(TimedCall),
    )
    async def loadNextTimedCall(self, now: float) -> TimedCall: ...

    @query(
        sql="INSERT INTO timed_calls(callable, when) VALUES ({what}, {when}) "
        "RETURNING timed_calls.id",
        load=one(lambda row: row[0]),
    )
    async def storeTimedCall(self, when: float, what: str) -> int: ...


backend = accessor(SimpleTimedStorageBackend)


schema = """
CREATE TABLE timed_calls (
    callable TEXT NOT NULL,
    when INTEGER NOT NULL,
    id INTEGER PRIMARY KEY
);
"""
