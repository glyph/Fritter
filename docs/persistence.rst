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
the "load context" for this registry, but we won't be using that for now.

Next, we'll make a simple Reminder class, which just holds a bit of text to
remind us about.

.. literalinclude:: json_basic_reminder.py
   :start-after: reminder-class
   :end-before: reminder-methods

To make this class serializable by our JSON serializer, we have to add a few
instance and class methods to conform to its interfaces: a ``typeCodeForJSON``
classmethod to provide a type-code string that uniquely identifies this class
within the context of our serialization format, an ``asJSON`` instance method
to serialize it to a JSON-serializable dict, and a ``fromJSON`` method that
passes in the result of that ``asJSON`` method as well as some other
parameters.

.. literalinclude:: json_basic_reminder.py
   :start-after: reminder-methods
   :end-before: app-method

To complete this object, we need the actual method which we will be scheduling
to run in the future.  Not a whole lot to see there; the main bit of interest
is that we decorate it with ``registry.method`` from the ``JSONRegistry`` that
we instantiated before:

.. literalinclude:: json_basic_reminder.py
   :start-after: app-method
   :end-before: end-reminder

So that's it for our "object model", such as it is, for this extremely simple
application.  Next we need to add the functions to perform the tasks that we
need.

First, we need to actually schedule the reminder.  For that, we'll have a very
simple function that schedules our ``show`` method with a given scheduler.  To
do this, we'll take a scheduler, some number of seconds into the future, and a
message to show.  We'll instantiate a ``Reminder``, and create a
``datetype.DateTime`` with a ``ZoneInfo`` time zone.

.. note::

   In order to serialize time zone information, we need a common method of
   identifying the zone, and a consistent type for using.  This means that we
   must use exactly ``datetype``'s type-wrapper for ``datetime.datetime``
   (don't worry, there's no runtime cost) and a ``ZoneInfo`` timezone
   specifically, because it will be serialized by its ``key`` attribute, that
   other sorts of ``tzinfo`` objects, like ``datetime.timezone``, do not have.
   Mypy should alert you to any type mismatches here, so you don't need to
   memorize this, but that's *why* this specificity is necessary.

.. literalinclude:: json_basic_reminder.py
   :pyobject: remind

Next, when we run our script, we always want to load up the scheduler from the
file where it is saved, if that file is there, and let it run for a little
while to take care of any pending work before we do anything else.  We can
create a ``SleepDriver`` and use our ``JSONRegistry``'s ``load`` method, then
``block()`` briefly before returning the loaded scheduler.  We will then want
to run some code to update the scheduler, maybe adding some stuff to it, then
save it again with any completed calls removed and any new calls added.

We'll do this with a contextmanager that loads, then saves the scheduler to a
file:

.. literalinclude:: json_basic_reminder.py
   :pyobject: schedulerLoaded.

Now to put *all* of that together, we'll do a bit of light command-line
parsing; if we pass any arguments, the first should be an integer number of
seconds, and the rest of the command line is the message we want to get
reminded of.

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

For an example of an application that needs to track this sort of long-term
work, let's build a little application that can help you keep in touch with
friends.  It's all too easy to just forget to send a message to keep in touch,
so let's make a tool to remind ourselves.

Just for starters, let's say that we want to:

1. have a list of friends in a text file that we can **append** to when we want
   to add more people to the list to be reminded about, and

2. be reminded to send a message to one of those friends each week, cycling
   through that list.

   

.. literalinclude:: json_instance.py

.. literalinclude:: json_methods_example.py
