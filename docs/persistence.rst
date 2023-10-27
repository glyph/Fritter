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

.. literalinclude:: json_basic_reminder.py

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
