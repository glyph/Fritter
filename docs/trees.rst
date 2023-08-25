Timer Trees
===========

You can use :py:mod:`fritter.tree` to organize your timers into groups.

:py:func:`fritter.tree.branch` takes a scheduler and branches off of it,
returning a 2-tuple of a :py:class:`friter.tree.Group` that allows you to
control the group by pausing and unpausing it, and by changing its scaling
factor, and a :py:class:`fritter.scheduler.Scheduler` of the same type as its
argument.

.. note::

   Mypy is currently not expressive enough to describe the relationship of the
   scale-factor type to the time type, so currently :py:mod:`fritter.tree` only
   supports simple schedulers; i.e.: those with a float time type and a regular
   callable work type.

Let's get set up with a tree scheduler; we'll create a memory driver, a simple
scheduler, and branch it to create a child:

.. literalinclude:: tree_example.py
   :start-after: # setup
   :end-before: # end setup

And a simple function that produces some schedulable work that will label and
show our progress:

.. literalinclude:: tree_example.py
   :start-after: # showfunc
   :end-before: # end showfunc

Now we can schedule some work, first in the child...

.. literalinclude:: tree_example.py
   :start-after: # childcalls
   :end-before: # parentcalls

... then in the parent ...

.. literalinclude:: tree_example.py
   :start-after: # parentcalls
   :end-before: # endcalls

So now we have a child that is going to run some code at 1, 2, and 3 seconds,
and a parent primed to do the same.  But, we can pause the child!  So let's see
what happens if we let one call run, pause, let another one run, unpause, and
run the rest.

.. literalinclude:: tree_example.py
   :start-after: # interact

Let's have a look at the output that produces.

.. code-block::

   child 1 parent=1.0 child=1.0
   parent 1 parent=1.0 child=1.0
   pause
   parent 2 parent=2.0 child=1.0
   unpause
   parent 3 parent=3.0 child=2.0
   child 2 parent=3.0 child=2.0
   child 3 parent=4.0 child=3.0

As you can see above, we start off as we would expect.  The child runs, the
parent runs, the time is 1.0 in each.

Then we pause the child, and advance again.

The parent runs, showing that its time is now 2.0.  But the child has not
advanced!  It is frozen in time, paused at 1.0.

When we unpause, and advance again, the parent and child both run at
parent-time 3.0 and child time 2.0.  When we advance to complete the child's
work, we are now at 4.0 in the parent and 3.0 in the child.

Scaling
-------

You can also cause time to run slower or faster, using the ``scaleFactor``
attribute of the ``Group`` object.  Here's an example that starts a child
scheduler at 3x faster than its parent, and increases its speed as it goes
along.

.. literalinclude:: tree_scaling_example.py

As you run it, it looks like this:

.. code-block::

   parent
   child
   child
   time: parent=0.3333333333333333 child=1.0000000000000002
   child
   time: parent=0.5833333333333333 child=2.000000000000001
   child
   time: parent=0.7833333333333332 child=3.0
   child
   time: parent=0.95 child=3.999999999999999
   parent
   time: parent=1.0 child=4.35
   child
   time: parent=1.08125 child=5.000000000000002
   child
   time: parent=1.192361111111111 child=5.999999999999998
   child
   time: parent=1.292361111111111 child=7.000000000000001
   child
   time: parent=1.383270202020202 child=7.999999999999998
   child
   time: parent=1.4666035353535354 child=9.000000000000002

