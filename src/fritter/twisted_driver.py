from dataclasses import dataclass
from typing import Callable, Optional

from twisted.internet.interfaces import IDelayedCall, IReactorTime


@dataclass
class TwistedDriver(object):
    _reactor: IReactorTime
    _call: Optional[IDelayedCall] = None

    def reschedule(self, desiredTime: float, work: Callable[[], None]):
        def _():
            self._call = None
            work()

        if self._call is not None:
            self._call.cancel()
        self._call = self._reactor.callLater(
            max(0, desiredTime - self.currentTimestamp()), _
        )

    def unschedule(self):
        if self._call is not None:
            self._call.cancel()
            self._call = None

    def currentTimestamp(self) -> float:
        return self._reactor.seconds()
