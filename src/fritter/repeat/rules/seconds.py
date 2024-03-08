"""
Recurrence rules for use with L{fritter.repeat.repeatedly} which work with
L{float}s representing a number of seconds as both a reference point and a
delta between times.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING


@dataclass
class EverySecond:
    """
    An L{EverySecond} is a L{RecurrenceRule} based on a L{float} timestamp,
    that can repeat work on a physical-time interval.

    @ivar seconds: the number of seconds between recurrences.
    """

    seconds: float

    def __call__(self, reference: float, current: float) -> tuple[int, float]:
        """
        Compute a step count and next desired recurrence time based on a
        reference time and a current time in floating-point POSIX timestamps
        like those returned by L{time.time} and L{datetime.datetime.timestamp},
        and number of seconds in L{self.seconds <EverySecond.seconds>}.

        @see: L{RecurrenceRule}
        """
        elapsed = current - reference
        count, remainder = divmod(elapsed, self.seconds)
        return int(count) + 1, current + (self.seconds - remainder)


if TYPE_CHECKING:
    from ...boundaries import RecurrenceRule

    _isRule: RecurrenceRule[float, int] = EverySecond(1.0)
