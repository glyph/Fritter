# FRITTer

## (Frame Rate Independent Timer Tree-er)

Sometimes you want to do something that tracks with real time but may not be
called quite as often as it wants to be, because other tasks are bogging down
the system or the process. Perhaps you want to play an audio sample as part of
a stream, move an object in a simulation, or advance to the appropriate image
for the current frame of an animation.

The 'fritter' package provides a few tools to make that easier, particularly
the 'repeat' module.  Inspired by Twisted's "LoopingCall.withCount" which does
something similar, it is a much simpler and more decoupled implementation.

The 'scheduler' core is quite a lot like the built-in 'sched' module, with a
few key differences:

1. it doesn't have the burden of being thread-safe, which may slightly improve
   its performance on some platforms in single-threaded contexts

2. it is optimized for non-blocking, rather than event-driven, usage; i.e. no
   `delayfunc`, but a time-driver interface where it can schedule timers with a
   reactor or event loop

3. it has an abstract interface for different priority queue implementations;
   experience with Twisted has taught me that different workloads (more or
   fewer events, more events added sooner or more events added later) often
   have contradictory performance requirements, although `heapq` is a pretty
   sensible default most of the time.

(The 'tree' part is forthcoming in a later version, but the idea there is that
this will be designed to be used with hierarchical simulations with
sub-simulations that can be either paused or destroyed, and when that occurs
they should take all of their processes and events with them.)
