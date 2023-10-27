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

_PS_TZ_CMD = """\
powershell \
[\
Windows.Globalization.Calendar,\
Windows.Globalization,\
ContentType=WindowsRuntime\
]\
::New().GetTimeZone()\
"""

_guessedZone: ZoneInfo | None = None


def guessLocalZone() -> ZoneInfo:
    """
    Attempt to determine the IANA timezone identifier for the local system
    using a variety of heuristics.
    """
    global _guessedZone
    if _guessedZone is not None:
        return _guessedZone
    from os import name, readlink

    if name == "nt":
        from os import popen

        ianaID = popen(_PS_TZ_CMD).read().strip()
    else:
        path = readlink("/etc/localtime").split("/")
        ianaID = "/".join(path[path.index("zoneinfo") + 1 :])
    _guessedZone = ZoneInfo(ianaID)
    return _guessedZone


@dataclass(frozen=True)
class DateTimeDriver:
    """
    Driver based on ZoneInfo-aware datetimes.

    @ivar driver: the L{TimeDriver} that this L{DateTimeDriver} is layered on
        top of, one which represents time as a POSIX timestamp as a L{float}.

    @ivar zone: the default timezone of this L{DateTimeDriver}, the one which
        will be used for results from L{now() <DateTimeDriver.now>}.  Note that
        L{reschedule(...) <DateTimeDriver.reschedule>} will still take inputs
        in any zone; this is just the default zone for outputs.
    """

    driver: TimeDriver[float]
    zone: ZoneInfo = ZoneInfo("Etc/UTC")

    def unschedule(self) -> None:
        "Implementation of L{TimeDriver.unschedule}"
        self.driver.unschedule()

    def reschedule(
        self, newTime: DateTime[ZoneInfo], work: Callable[[], None]
    ) -> None:
        "Implementation of L{TimeDriver.reschedule}"
        self.driver.reschedule(newTime.timestamp(), work)

    def now(self) -> DateTime[ZoneInfo]:
        "Implementation of L{TimeDriver.now}"
        timestamp = self.driver.now()
        return DateTime.fromtimestamp(timestamp, self.zone)


_DriverTypeCheck: type[TimeDriver[DateTime[ZoneInfo]]] = DateTimeDriver
