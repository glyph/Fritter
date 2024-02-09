Timer Trees
===========

You can use :py:mod:`fritter.tree` to organize your timers into group within a
sub-scheduler that can be paused, resumed, and scaled together.

To understand why this is useful, consider a video game with a "pause" screen.
Timers which do things like play the animations in the UI from button presses
should keep running.  However, timers in the game world need to stop as long as
the pause screen is displayed, then start running again.  Similarly, a "slow"
or "freeze" spell might want to slow down or pause a sub-group of timers
*within* the group of timers affected by pause and unpause.

This isn't exclusively for games.  You might have similar needs in vastly
different applications.  For example, if you have a deployment workflow system,
a code freeze might want to pause all timers associated with pushing new
deployments during a code freeze, but leave timers associated with monitoring
and health checks running.

:py:func:`fritter.tree.branch` takes a scheduler and branches a new scheduler
off of it, returning a 2-tuple of a :py:class:`fritter.tree.BranchManager` that
allows you to control the branched scheduler by pausing and unpausing it, and
by changing the relative time scales between the trunk and and its, a new
branched :py:class:`fritter.scheduler.Scheduler` of the same type as its
argument.

Let's get set up with a tree scheduler; we'll create a memory driver, a simple
scheduler, and branch off a new scheduler:

.. literalinclude:: tree_example.py
   :start-after: # setup
   :end-before: # end setup

And a simple function that produces some schedulable work that will label and
show our progress:

.. literalinclude:: tree_example.py
   :start-after: # showfunc
   :end-before: # end showfunc

Now we can schedule some work, first in the branch...

.. literalinclude:: tree_example.py
   :start-after: # branchcalls
   :end-before: # trunkcalls

... then in the trunk ...

.. literalinclude:: tree_example.py
   :start-after: # trunkcalls
   :end-before: # endcalls

So now we have a branch that is going to run some code at 1, 2, and 3 seconds,
and a trunk primed to do the same.  But, we can pause the branch!  So let's see
what happens if we let one call run, pause, let another one run, unpause, and
run the rest.

.. literalinclude:: tree_example.py
   :start-after: # interact

Let's have a look at the output that produces.

.. code-block::

   branch 1 trunk=1.0 branch=1.0
   trunk 1 trunk=1.0 branch=1.0
   pause
   trunk 2 trunk=2.0 branch=1.0
   unpause
   trunk 3 trunk=3.0 branch=2.0
   branch 2 trunk=3.0 branch=2.0
   branch 3 trunk=4.0 branch=3.0

As you can see here, first, the branch runs, the trunk runs, the time is 1.0 in
each.

Then we pause the leaf scheduler via its manager, and advance again.

The trunk runs, showing that the time *in the trunk* is now 2.0.  But the
branch has not advanced!  It is frozen in time, paused at 1.0.

When we unpause, and advance again, the trunk and branch both run at
trunk-time 3.0 and branch time 2.0.  When we advance to complete the branch's
work, we are now at 4.0 in the trunk and 3.0 in the branch.

Scaling
-------

You can also cause time to run slower or faster, using the ``changeScale``
method of the ``BranchManager`` object.  Here's an example that starts a branch
scheduler at 3x faster than its trunk, and increases its speed as it goes
along.

.. literalinclude:: tree_scaling_example.py

As you run it, it looks like this:

.. code-block::

   trunk
   branch
   branch
   time: trunk=0.3333333333333333 branch=1.0000000000000002
   branch
   time: trunk=0.5833333333333333 branch=2.000000000000001
   branch
   time: trunk=0.7833333333333332 branch=3.0
   branch
   time: trunk=0.9499999999999998 branch=4.0
   trunk
   time: trunk=1.0 branch=4.350000000000001
   branch
   time: trunk=1.0812499999999998 branch=4.999999999999999
   branch
   time: trunk=1.192361111111111 branch=5.999999999999999
   branch
   time: trunk=1.292361111111111 branch=6.999999999999998
   branch
   time: trunk=1.3832702020202021 branch=8.000000000000002
   branch
   time: trunk=1.4666035353535354 branch=8.999999999999998
