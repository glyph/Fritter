Persistence
============

Sometimes, you need to schedule timed events over a long period of time; too
long to trust that a single process will stay running.  Fritter includes a
module, :py:mod:`fritter.persistence.json`, that can help you do just that.

Just Call Something In The Future: Reminder Example
---------------------------------------------------

The most basic thing that we can do with a persistent task is remind the user
to do sommething at some point in the future.  So let's start off by building
that.

First, we need a ``JSONRegistry``, so let's instantiate one.

.. literalinclude:: json_basic_reminder.py
   :start-after: start-registry
   :end-before: end-registry

Don't worry about the ``[object]`` there just yet; that tells us the type of
the "load context" for this registry.  We'll get to that a little later, but
this first step doesn't need it yet.

Next, we'll make a Reminder class, which just holds a bit of text to remind us
about.

.. literalinclude:: json_basic_reminder.py
   :start-after: reminder-class
   :end-before: reminder-methods

To make this class serializable by our JSON serializer, we have to add a few
instance and class methods to conform to its interfaces:

- a ``typeCodeForJSON`` classmethod to provide a type-code string that uniquely
  identifies this class within the context of this specific ``JSONRegistry``
  instance, which defines our serialization format.

- an ``asJSON`` instance method to serialize it to a JSON-serializable dict,
  and

- a ``fromJSON`` method that passes in the result of that ``asJSON`` method as
  well as some other parameters.

Here are those implementations:

.. literalinclude:: json_basic_reminder.py
   :start-after: reminder-methods
   :end-before: end-reminder-methods

To complete this object, we need the actual method which we will be scheduling
to run in the future.  In order to mark a method as serializable by the
scheduler, we define a 0-argument, ``None``-returning method and decorate it
with :py:meth:`registry.method <fritter.persistent.json.JSONRegistry.method>`
from the ``JSONRegistry`` that we instantiated before.

.. literalinclude:: json_basic_reminder.py
   :start-after: app-method
   :end-before: end-reminder

So that's it for our "object model" for this application.  Next we need to add
the functions to perform the tasks that we need.

First, we need to actually schedule the reminder.  For that, we'll have a
function that schedules our ``show`` method with a given scheduler.  To do
this, we'll take a scheduler, some number of seconds into the future, and a
message to show.  We'll instantiate a ``Reminder``, and create a
``datetype.DateTime`` with a ``ZoneInfo`` time zone.

Since the user probably wants their reminders scheduled in their *own* time
zone, Fritter provides a convenience function, :py:func:`guessLocalZone
<fritter.drivers.datetime.guessLocalZone>`\ , which uses platform-specific
heuristics to determine the local machine's IANA timezone identifier and use
that.

.. note::

   In order to serialize time zone information, we need a common method of
   identifying the zone, and a consistent type for using.  To ensure this,
   Fritter uses |datetype|_\ ’s
   type-wrapper for ``datetime.datetime``\ . This is purely for type-checking;
   at runtime, these objects are :py:class:`datetime.datetime` instances.  The
   JSON serializer also requires :py:class:`zoneinfo.ZoneInfo` objects
   specifically as the ``tzinfo``, because it will be serialized by its ``key``
   attribute. Other sorts of ``tzinfo`` objects, like ``datetime.timezone``, do
   not have this attribute and cannot be reliably serialized.  Mypy should
   alert you to any type mismatches here, so you don't need to memorize this,
   but that's why we are using ``datetype`` here.

.. |datetype| replace:: ``datetype``
.. _datetype: https://pypi.org/project/datetype

.. literalinclude:: json_basic_reminder.py
   :pyobject: remind

Next, when we run our script, we always want to load up the scheduler from the
file where it is saved, if that file is there, and let it run for a little
while to take care of any pending work before we do anything else.  We can
create a :py:class:`SleepDriver <fritter.drivers.sleep.SleepDriver>` and use
our ``JSONRegistry``'s ``load`` method, then :py:meth:`block
<fritter.drivers.sleep.SleepDriver.block>` with a short timeout before
returning the loaded scheduler.  We will then run some code to update the
scheduler, maybe adding some stuff to it, then save it again with any completed
calls removed and any new calls added.

Fritter provides a function,
:py:func:`fritter.persistent.json.schedulerAtPath`, which does most of this
work for you, returning a contextmanager that either loads or creates a ????????????????????????.

.. literalinclude:: json_basic_reminder.py
   :pyobject: schedulerLoaded

Now to put *all* of that together, we'll look at the command-line. If the user
specifies any arguments, the first should be an integer number of seconds, and
the rest of the command line is the message we want to get reminded of.
Otherwise, just run the scheduler to catch up to the current time.

.. literalinclude:: json_basic_reminder.py
   :start-at: __main__

And that's it!  On the command line, you can set yourself some reminders:

.. code-block::

   $ python json_basic_reminder.py 5 hello
   $ python json_basic_reminder.py 10 goodbye

And if you run ``python json_basic_reminder.py`` with no arguments after 5 and
10 seconds respectively, you'll see your reminders print out.

With the techniques in this section, you can:

- persist your timed events to a JSON blob
- save them for the future
- schedule bound methods on those objects to save state associated with your timers

Next, we will move on to a slightly more complex application with more
interactions.

Adding Recurrences And Counts: Friendminder Example
---------------------------------------------------

To illustrate some slightly more complex uses of ``JSONRegistry``, let's build
a little application that can help you keep in touch with friends.  It's all
too easy to just forget to send a message to keep in touch, so let's make a
tool to remind ourselves.

In this tool, we want to:

1. have a list of friends that we can add to when we want to add more people to
   be reminded about,

2. be reminded to send a message to one of those friends each week, cycling
   through that list.

3. be reminded to get in touch with each friend on their birthday each year.

This means we have two kinds of repeating call; the general "get in touch"
reminder, which would need to be a method on some shared object that can
reference the full list of friends, as well as the birthday-specific reminder,
which should probably be a method on a ``Friend`` class itself.

