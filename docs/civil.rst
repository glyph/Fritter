Civil Time
===========

Now that we can :ref:`schedule work in terms of a floating-point timestamp
<Running In Real Life>`, let's take a look at scheduling things in terms of
years, months, days, hours, and minutes using
:py:class:`fritter.drivers.datetime.DateTimeDriver`.

.. note::

   The following examples use the `datetype
   <https://github.com/glyph/datetype>`_ library, but ``datetype.DateTime``
   objects are actually just slightly better type-hints around
   :py:class:`datetime <datetime.datetime>` objects so you can type-check
   whether they have timezones or not with Mypy; at run-time, they are
   :py:class:`datetime <datetime.datetime>`\ s.

First, let's get all our imports sorted out:

.. literalinclude:: civil_example.py
   :end-before: memory driver

We'll need a driver, as usual. :py:class:`MemoryDriver
<fritter.drivers.memory.MemoryDriver>`, like other low-level drivers, is a
``float`` driver, which we will need first.

.. literalinclude:: civil_example.py
   :start-after: set up memory
   :end-before: set up datetime

:py:class:`DateTimeDriver <fritter.drivers.datetime.DateTimeDriver>` is a
wrapper around any :py:class:`TimeDriver <fritter.boundaries.TimeDriver>`\
``[float]``, so we can wrap it around a memory driver (or, similarly, another
``TimeDriver[float]`` such as :py:mod:`twisted <fritter.drivers.twisted>`,
:py:mod:`asyncio <fritter.drivers.asyncio>` or just :py:mod:`sleep
<fritter.drivers.sleep>`).  We need to create a time zone first — a
:py:class:`ZoneInfo <zoneinfo.ZoneInfo>`, specifically.

.. literalinclude:: civil_example.py
   :start-after: set up datetime
   :end-before: set up scheduler

Next, we'll pick a :py:class:`datetime <datetime.datetime>` as a reference
point for our example.

.. literalinclude:: civil_example.py
   :start-after: create datetime
   :end-before: advance to the timestamp

And catch our driver up to the timestamp that corresponds to the date.

.. literalinclude:: civil_example.py
   :start-after: advance to the timestamp
   :end-before: done advancing

We'll schedule some work using a :py:class:`timedelta <datetime.timedelta>`,
and then advance by a number of seconds which calls our callable.

.. literalinclude:: civil_example.py
   :start-after: schedule the work

We will then see the ISO format of the timestamp print out, 2 days after our
reference time of May 5, 2023:

.. code-block::

   hi 2023-05-07T00:00:00-07:00
