"""
Fritter, the Frame-Rate IndependenT TimEr tRee.

This is a library for scheduling timed events in the very near or very far
future.
"""

from . import (
    heap,
    tree,
    persistent,
    boundaries,
    drivers,
    scheduler,
    repeat,
)

__version__ = "0.1.0"
"The current version of the Fritter library."

__all__ = [
    "heap",
    "tree",
    "persistent",
    "boundaries",
    "drivers",
    "scheduler",
    "repeat",
]
