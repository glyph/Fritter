# FRITTer

## Frame-Rate IndependenT TimEr tRee

Welcome to Fritter, a generalized Python library for interacting with work that
needs to occur over time, whether physical time (i.e. numbers of seconds) or
civil time (i.e. numbers of days, weeks, months, or years).

## Get It Now

- Install from PyPI with [`pip install fritter`](https://pypi.org/project/fritter/).
- Read the documentation at [fritter.readthedocs.io](https://fritter.readthedocs.io/).

## What Is It, and Why Do I Need It?

Fritter is a one-stop clock shop, allowing you to schedule over very short or
very long periods of time.  Wherever you need something to happen in the
future, Fritter has something for you.  Here are just some of the use-cases:

- If you have an algorithm that processes work over time and you want a unified
  interface to be able to deploy it across a variety of event loops, take a
  look at
  [`fritter.drivers`](https://fritter.readthedocs.io/en/latest/api/fritter.drivers.html),
  where you will find drivers that support [Twisted](https://twisted.org),
  [asyncio](https://docs.python.org/3.12/library/asyncio.html), as well as ones
  for scheduled events executing in batch scripts or CLI tools that don't need
  an event loop at all, supplying a small wrapper around
  [`time.sleep`](https://docs.python.org/3.12/library/time.html#time.sleep).

- Do you want to write fast, deterministic tests for that code, without pulling
  in any of those frameworks *or* calling `sleep`?  Fritter comes with a robust
  [in-memory
  driver](https://fritter.readthedocs.io/en/latest/api/fritter.drivers.memory.MemoryDriver.html)
  perfect for unit testing, or for any scenario where you need precise control.

- Do you have a demanding application with large numbers of timers that is
  straining the naive implementation of your favorite library?  Fritter allows
  you to bring your own [custom priority queue
  implementation](https://fritter.readthedocs.io/en/latest/api/fritter.boundaries.PriorityQueue.html)
  for these high-performance edge cases.

- Do you need to schedule a very high-frequency timer, whose rate is measured
  in Hz, to update a system that needs to stay synchronized with real time,
  such as an interactive animation, real-time simulation, or delivery of
  samples to an audio device?
  [`fritter.repeat`](https://fritter.readthedocs.io/en/latest/repeat.html) has
  got you covered, with an interface that allows you to achieve its titular
  *frame-rate independence*.

- Do you need to schedule a very *low*-frequency timer, whose rate is measured
  in weeks or months, something that runs so infrequently or so far in the
  future that the current process will almost certainly no longer be running?
  Schedule your timer in terms of
  [`datetime`-ish](https://pypi.org/project/datetype/) objects, then serialize
  it with
  [`fritter.persistent.jsonable`](https://fritter.readthedocs.io/en/latest/persistence.html)
  to load it again when your process restarts.  `fritter.persistent` is careful
  to supply an interface using IANA identifiers to maintain correctness in the
  face of future DST changes, and other things that can start to complicate the
  use of time over longer periods.

- Do you need to manage *groups* of related timers, sometimes pausing some
  groups while allowing others to continue, while all running on the same loop;
  like how the "pause" button on a video game stops the action but doesn't stop
  the UI?
  [`fritter.tree`](https://fritter.readthedocs.io/en/latest/trees.html) will
  allow you to nest your groups arbitrarily deeply.

If any of these sound interesting, `pip install fritter` to try it out today!
