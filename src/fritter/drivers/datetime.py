from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from zoneinfo import ZoneInfo
from datetype import DateTime

from ..boundaries import TimeDriver


@dataclass(frozen=True)
class DateTimeDriver:
    """
    Driver based on aware datetimes.
    """

    driver: TimeDriver[float]
    zone: ZoneInfo = ZoneInfo("Etc/UTC")

    def unschedule(self) -> None:
        """
        Unschedule from underlying driver.
        """
        self.driver.unschedule()

    def reschedule(
        self, newTime: DateTime[ZoneInfo], work: Callable[[], None]
    ) -> None:
        """
        Re-schedule to a new time.
        """
        self.driver.reschedule(newTime.timestamp(), work)

    def now(self) -> DateTime[ZoneInfo]:
        timestamp = self.driver.now()
        return DateTime.fromtimestamp(timestamp, self.zone)


_DriverTypeCheck: type[TimeDriver[DateTime[ZoneInfo]]] = DateTimeDriver
