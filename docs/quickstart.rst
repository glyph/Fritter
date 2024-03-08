Quick Start
===========

Calling Your First Function With A Scheduler
--------------------------------------------

The first thing that you will need is a *driver*, which is what allows you to
interface with an external timekeeping system that can actually invoke your
code.

The simplest driver you can use is the memory driver, in
:py:mod:`fritter.drivers.memory`.  Getting one is simple enough:

.. code-block:: python

   from fritter.drivers.memory import MemoryDriver
   driver = MemoryDriver()

Once you have a driver, you can schedule work on it with a :py:class:`Scheduler
<fritter.scheduler.Scheduler>`, which you can create with
:py:func:`fritter.scheduler.schedulerFromDriver`.

Let's begin with a :py:class:`PhysicalScheduler
<fritter.boundaries.PhysicalScheduler>`, which is a scheduler that uses a
``float`` timestamp to track time and can invoke any 0-argument callable.

.. code-block:: python

   from fritter.boundaries import PhysicalScheduler
   from fritter.scheduler import schedulerFromDriver
   scheduler = schedulerFromDriver(driver)

Now, let's define some work to do.  Again, our scheduler considers any callable
object which takes no arguments and returns nothing to be a thing it can
schedule for future execution, so we can define a regular function for this.

We'll make it print out the current time according to the scheduler via its
``now`` method.

.. code-block:: python

   def hello() -> None:
       print("hello", scheduler.now())


.. code-block:: python

   scheduler.callAt(1.0, hello)
   scheduler.callAt(2.0, hello)
   scheduler.callAt(3.0, hello)

A memory driver is just an in-memory list of timers, and will never do anything
on its own, so next we will need to tell it to move time forward for us, via
its ``advance`` method.

.. code-block:: python

   driver.advance()

From this, you can see ``1.0``.

:py:meth:`MemoryDriver.advance <fritter.drivers.memory.MemoryDriver.advance>`,
when given no arguments, will always advance the internal timestamp of the
``MemoryDriver`` to whatever the time of its next scheduled work is, call any
callables on the way there, then stop.  This does not necessarily mean it only
does one bit of work; if two bits of work are scheduled at precisely the same
time, it'll run them both.

Since its main purpose is for testing, you can also ask the
:py:meth:`MemoryDriver <fritter.drivers.memory.MemoryDriver>` if it has any
more work to do:

.. code-block:: python

   print(driver.isScheduled())

This should show you ``True``, since there is still the work at timestamp 2.0
and 3.0 yet to complete.  Therefore this idiom will keep running at maximum
speed, completing all scheduled work immediately, and stopping when it's done:

.. code-block:: python

   while driver.isScheduled():
       driver.advance()

This should show us ``hello 2.0``, and ``hello 3.0``, as each callable runs,
then time advances to the scheduled time of the next one.  You can ask the
driver the time directly with ``driver.now()``, and indeed, that should show
you ``3.0``.  Even if no work is scheduled though, you can set the clock by
advancing by a specific interval:

.. code-block:: python

   driver.advance(5000)
   print(driver.now())

This should show you ``5003.0``, as you've now advanced 5000 seconds further.

Running In Real Life
--------------------

Of course, the memory driver, while helpful for testing, does not hook up to a
real clock.  For that, you'll need one of the other drivers.  Let's start with
``asyncio``:

.. literalinclude:: asyncio_driver_example.py

When run, this should print out "``elapsed=<a number slightly greater than 1.5>``".

These are all the basics of running basic timed calls with ``fritter``:

1. find a driver that works for the framework you're using; currently,
   in-memory, asyncio, or twisted (with more to come)
2. instantiate a ``fritter.scheduler.Scheduler`` using that driver
3. schedule work to occur at a particular timestamp in that driver's
   time-coordinate system using that scheduler with ``scheduler.callAt``.
