from unittest import TestCase
from zoneinfo import ZoneInfo

from fritter.drivers.datetime import guessLocalZone


class ZoneSmokeTest(TestCase):
    def test_guessLocalZone(self) -> None:
        self.assertIsInstance(guessLocalZone(), ZoneInfo)
