from unittest import TestCase
from zoneinfo import ZoneInfo

from ..drivers.datetimes import guessLocalZone


class ZoneSmokeTest(TestCase):
    def test_guessLocalZone(self) -> None:
        first = guessLocalZone()
        self.assertIsInstance(first, ZoneInfo)
        second = guessLocalZone()
        self.assertIs(first, second)
