from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Generic

from ..boundaries import ScheduledCall, Scheduler, TimeDriver, WhenT


@dataclass
class SchedulerDriver(Generic[WhenT]):
    _scheduler: Scheduler[WhenT, Callable[[], None], object]
    _active: ScheduledCall[WhenT, Callable[[], None], object] | None

    def reschedule(
        self, newTime: WhenT, work: Callable[[], None]
    ) -> None:
        """
        Schedule C{work} to occur at C{newTime}, removing any previous C{work}
        scheduled by prior calls to C{reschedule}.
        """
        self.unschedule()
        def wrappedWork() -> None:
            self._active = None
            work()
        self._scheduler.callAt(newTime, wrappedWork)

    def unschedule(self) -> None:
        """
        Remove any previously-scheduled C{work}.
        """
        if self._active is not None:
            it, self._active = self._active, None
            it.cancel()

    def now(self) -> WhenT:
        """
        Get the current time according to the underlying library.
        """
        return self._scheduler.now()


if TYPE_CHECKING:
    _driverCheck: type[TimeDriver[int]] = SchedulerDriver[int]
