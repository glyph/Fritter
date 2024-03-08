Introduction
============

Fritter (the Frame-Rate Independent Timer Tree-er) is a
generalizable scheduling library.

If you're writing some code, and you need to schedule some part of that code to
happen in the future, there are a lot of different ways to do it.

In an event-driven framework like `Asyncio
<https://docs.python.org/3.11/library/asyncio.html#module-asyncio>`_ or
`Twisted <https://twisted.org/>`_\ , you might use an API like `call_at
<https://docs.python.org/3.11/library/asyncio-eventloop.html#asyncio.loop.call_at>`_.
This works fine, for some applications, but time is a deep and complex field,
and you may encounter a variety of different problems as you interact with it.

The Problems
############

Not Using A Framework
---------------------

You might need to schedule such work when you're *not* using such a framework.
How do you push that work off into the future, then?  You might need to use
some sort of external system such as `cron
<https://en.wikipedia.org/wiki/Cron>`_; but now, you need to put that work into
a totally separate script, which changes the way you need to interface with it.

Saving Work For The Future
--------------------------

You may need the work to be *persistent*; it might be important to make sure
this work happens at some point in the future, even if your program needs to
re-start, whether due to a crash or user interaction.  In that case you need to
embed your code within a framework like `Celery <https://docs.celeryq.dev/>`_\
, which requires you to set up a bunch of infrastructure like brokers and
queues before you can even define your functions.

Maintaining Time-Accuracy For Repeating Tasks
---------------------------------------------

You might need the work to be *time-accurate* (or “soft real-time”).  If you're
a game developer, you might be familiar with a concept like `deltaTime
<https://docs.unity3d.com/ScriptReference/Time-deltaTime.html>`_ (a source of
some `famously tricky bugs
<https://blog.unity.com/engine-platform/fixing-time-deltatime-in-unity-2020-2-for-smoother-gameplay>`_);
if you have done any audiovisual work, you've probably dealt with issues of
audio drift; if you've done A/V programming, you might have needed to maintain
a `jitter buffer <https://vocal.com/voip/jitter-buffer-for-voice-over-ip/>`_\ .
Calculating those deltas accurately in such a way as to avoid accumulating
floating-point inaccuracy can be tricky.

One of the inspirations for Fritter, from which it takes the first part of its
name, is "Frame Rate Independence" which is what some game developers call
time-accuracy since it means that a game will `run correctly regardless of
whatever frame rate it is able to achieve on your hardware
<https://en.wikipedia.org/wiki/Delta_timing>`_.  Twisted's `LoopingCall
<https://docs.twistedmatrix.com/en/stable/api/twisted.internet.task.LoopingCall.html>`_
provides a nice interface for doing this in the context of that framework.

Honoring Civil Intervals
------------------------

You might need the work to happen on a *civil* rather than a *physical*
schedule.  Physical time is time as measured by a clock from a specific
reference point, recorded by something like your computer's monotonic clock or
a caesium atomic clock.  An interval of physical time can be always be
expressed as a number of `SI seconds <https://en.wikipedia.org/wiki/Second>`_.
However, a civil time delta can be expressed in terms of days, weeks, months,
or years.  If it is 2:15 PM on March 10th, you say that something should happen
“in 10 days”, you would expect everyone's clocks to say “March 20, 2:15” when
it next occurs, regardless of what local legislatures have said about time
zones, daylight savings time, and so on.  This sometimes necessitates `updates
to the time zone database <https://data.iana.org/time-zones/tzdb/NEWS>`_, which
implicitly requires the second point above; as far as I know, at least, there
is not any way to update a program's timezone database without restarting it,
if not rebooting the whole computer.  However else you're scheduling your work,
you will need to write your own translation to and from civil time, and doing
so is `probably more complicated than you think
<https://zachholman.com/talk/utc-is-enough-for-everyone-right>`_.

In Python, there's a wonderful little utility for a very flexible array of
civil intervals: dateutil's `relativedelta
<https://dateutil.readthedocs.io/en/stable/relativedelta.html>`_\ .

Fritter: A One Stop Clock Shop
##############################

You may have noticed that all the problems I mentioned above already have
solutions: `cron <https://en.wikipedia.org/wiki/Cron>`_ for scheduling code
outside of your current process, `Celery <https://docs.celeryq.dev/>`_ for
persisting work into a queue that can be persisted later, `LoopingCall
<https://docs.twistedmatrix.com/en/stable/api/twisted.internet.task.LoopingCall.html>`_
for time-accurate frame rate advancement, `relativedelta
<https://dateutil.readthedocs.io/en/stable/relativedelta.html>`_ for correctly
honoring complex civil intervals.  So if all the problems are solved, what is
Fritter for?

The goal of Fritter is to provide a *uniform, type-safe* interface to all this
functionality, allowing code to be written as generically as possible, to
interface between multiple types of time.

For example, you can't take a ``relativedelta`` object and have it give you a
working ``cron`` rule.  You can't use ``LoopingCall`` without bringing in all
of Twisted, which means you can't use it in Asyncio or Trio without a bunch of
awkward bridging.

``LoopingCall`` also operates exclusively in terms of seconds, which means that
if you need time-accuracy *and* persistence *and* civil time - say, for
example, you have a weekly task with associated state which needs to be invoked
manually by a system administrator, and it might get skipped if that operator
is on vacation so that twice as much work needs to be done, ``LoopingCall``
can't help you there.

In combining these things together, Fritter also provides some unique features.

Type Safety
-----------

Schedulers within Fritter are generic types on both *when* (what represents
time) and *what* (what represents a callable).

By allowing a given scheduler to constrain what types of work may be scheduled
on them, you can tell mypy that ``x`` is a :py:class:`Scheduler[datetime,
MyPersistentWork, int] <fritter.boundaries.Scheduler>`, and any attempt to
schedule a generic, non-persistent callable on it will give you a (somewhat)
readable type-checking error.  This means that you can specify your desired
times in terms of ``datetime``, in terms of ``float``, or indeed in terms of
whatever custom time-keeping mechanism you have invented, if you want to work
in terms of, for example, an ``int`` of microseconds rather than a ``float`` of
seconds.

Grouping Related Work Together
------------------------------

You might also need groups of timers to happen on a *related* schedule.  For
example, if you have a video game, all the timers comprising the game logic may
need to be paused together when you pause the game, and then resumed together
when you resume the game.  But you might also need a separate collection of
timers for displaying animations on the pause screen, or in the menu system.
Or, if you're playing a video, you will need a timer to deliver frames of video
to the screen separately from samples of audio to the audio device at a
different frequency, but if they are paused they should be paused and resumed
together.

Putting The Name Together
-------------------------

Now that you know what its purpose is, I can explain the name is meaningful:

- Frame-Rate Independent: ``fritter.repeat.Repeater`` provides an integer
  interval-count to its ``callable``, so it counts frames for you and allows
  you to easily discretize whatever work you're performing, assuming you can
  eventually catch up to real time.

- Timer Tree: Timers can be grouped together, and that group of timers can be
  embedded into a scheduler that is then scheduled on another scheduler, and so
  on.

Now that you know *why* you want to use it, let's move on to actually using it.
