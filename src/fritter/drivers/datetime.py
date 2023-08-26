"""
Implementation of L{TimeDriver} to convert floating-point POSIX timestamps into
timezone-aware datetimes.

@note: Although at runtime this module uses L{datetime.datetime} objects, its
    type hints use the U{datetype <https://pypi.org/project/datetype/>} library
    to ensure that all values have the correct type of tzinfo.  This driver
    will I{not} work with arbitrary L{datetime.timezone} zones, I{only}
    L{zoneinfo.ZoneInfo} zones, as IANA timezone identifiers are required for
    reliable long-term serialization across DST boundaries.
"""

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
