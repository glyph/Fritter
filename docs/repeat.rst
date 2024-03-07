Repeating Work
================

The basic form of a repeating function in Fritter has a signature that looks
like this:

.. code-block::

   def work(steps: StepsT, scheduled: SomeScheduledCall) -> None: ...

The parameters are, respectively, the *steps* that ``work`` should perform in
this invocation, and an object with a ``.cancel()`` method that will stop the
next iteration from occurring.

Sometimes, real time moves more quickly than your code can keep up. Perhaps
your code is slow, or you need to wait on an external system; whatever the
reason, if if you've got a timer that is supposed to repeat every N seconds,
eventually, you'll see a repetition happen after 2N seconds, or more.  At that
point, any logic needs to catch up.

``steps`` can reflect this multiple ways, depending on the type of recurrence
you are using.  Recurrence rules

And of course you need to be able to stop the repetition, and the ``stopper``'s
``.cancel()`` method is there to help you do that.

Let's get set up with our imports.

.. literalinclude:: simple_repeat.py
   :end-before: driver setup

To demonstrate some repetitions, let's set up a :py:class:`SleepDriver
<fritter.drivers.sleep.SleepDriver>`.  The sleep driver will run stuff in real
time with no event loop; just blocking while work is still scheduled with the
driver.

.. literalinclude:: simple_repeat.py
   :start-after: driver setup
   :end-before: repeating work

Let's define some repeating work that runs for a finite number of times; it
should stop after 2 seconds, by cancelling its stopper:

.. literalinclude:: simple_repeat.py
   :start-after: repeating work
   :end-before: kick off scheduler

Next, we'll use :py:func:`repeatedly <fritter.repeat.repeatedly>` with a
scheduler wrapped around our driver, and then block the driver:

.. literalinclude:: simple_repeat.py
   :start-after: kick off scheduler

This will print out a bunch of steps, taking 2 wall-clock seconds to run, and
the output should look something like this:

.. code-block::

   took 1 steps at 0.00
   took 1 steps at 0.05
   took 1 steps at 0.11
    ...
   took 1 steps at 1.95
   took 1 steps at 2.01
   took 40 steps, then stopped



.. literalinclude:: repeating_example.py
   :end-before: example coroutine

.. literalinclude:: repeating_example.py
   :end-before: example coroutine
