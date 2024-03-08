"""
Recurrence rules for use with L{fritter.repeat.repeatedly} which work with
C{datetype.DateTime} objects.
"""

from dataclasses import dataclass
from datetime import timedelta, tzinfo
from typing import TYPE_CHECKING, TypeVar
from zoneinfo import ZoneInfo

from datetype import DateTime

from ...boundaries import Day, RecurrenceRule

DTRule = RecurrenceRule[DateTime[ZoneInfo], int]
"""
A type alias to describe a recurrence rule function that operates on aware
datetimes and tracks an integer count of steps.
"""

EachDTRule = RecurrenceRule[DateTime[ZoneInfo], list[DateTime[ZoneInfo]]]
"""
A type alias to describe a recurrence rule function that operates on aware
datetimes and tracks a list of desired elapsed occurrences as steps.
"""

TZType = TypeVar("TZType", bound=tzinfo)


@dataclass(frozen=True)
class EveryDelta:
    """
    An L{EveryDelta} is a L{RecurrenceRule} based on a L{timedelta}, that can
    cause civil times to repeat.

    @ivar delta: the time delta between recurrences
    """

    delta: timedelta

    def __call__(
        self,
        reference: DateTime[ZoneInfo],
        current: DateTime[ZoneInfo],
    ) -> tuple[int, DateTime[ZoneInfo]]:
        """
        Compute a step count and next desired recurrence time based on a
        reference time and a current time in aware datetimes, and the timedelta
        in C{self.delta}.

        @see: L{RecurrenceRule}
        """
        count = 0
        nextDesired = reference
        while nextDesired <= current:
            count += 1
            nextDesired += self.delta
        return count, nextDesired


@dataclass(frozen=True)
class EachYear:
    """
    An L{EachYear} is a L{RecurrenceRule} based on a number of years between
    two dates.

    @ivar years: The number of years between recurrences
    """

    years: int

    def __call__(
        self,
        reference: DateTime[ZoneInfo],
        current: DateTime[ZoneInfo],
    ) -> tuple[list[DateTime[ZoneInfo]], DateTime[ZoneInfo]]:
        referenceDate = reference.date()
        nextDesired = reference
        years = []
        while nextDesired <= current:
            years.append(nextDesired)
            nextDesired = nextDesired.replace(
                year=referenceDate.year + (len(years) * self.years)
            )
        return years, nextDesired


@dataclass
class EachWeekOn:
    """
    Repeat every week, on each weekday in the given set of C{days}, at the
    given C{hour}, C{minute}, and C{second}.
    """

    days: set[Day]
    hour: int
    minute: int
    second: int = 0

    def __call__(
        self, reference: DateTime[TZType], current: DateTime[TZType]
    ) -> tuple[list[DateTime[TZType]], DateTime[TZType]]:
        sdays = sorted([day.value for day in self.days])
        steps: list[DateTime[TZType]] = []
        refDay = reference.date().weekday()
        weekOffset = 0
        while True:
            for sday in sdays:
                daydelta = timedelta(days=(weekOffset + sday) - refDay)
                candidate = (reference + daydelta).replace(
                    hour=self.hour,
                    minute=self.minute,
                    second=self.second,
                    microsecond=0,
                )

                if candidate < reference:
                    # earlier than the reference time, let's ignore
                    continue

                if candidate <= current:
                    # after the reference time but before the current time,
                    # record as a missed step, then continue
                    steps.append(candidate)
                    continue

                # it's after the reference *and* after the current time, we're
                # done
                return steps, candidate
            weekOffset += 7


yearly: EachDTRule = EachYear(1)
"""
Yearly datetime-based delta.
"""

weekly: DTRule = EveryDelta(timedelta(weeks=1))
"""
Weekly datetime-based delta.
"""

daily: DTRule = EveryDelta(timedelta(days=1))
"""
Daily datetime-based rule.
"""

hourly: DTRule = EveryDelta(timedelta(hours=1))
"""
Hourly datetime-based rule.
"""


if TYPE_CHECKING:
    _isRule: EachDTRule = EachWeekOn({Day.MONDAY}, 1, 1, 1)


__all__ = [
    "EveryDelta",
    "EachWeekOn",
    "weekly",
    "daily",
    "hourly",
    "yearly",
]
