:kind: reference

======
Design
======

Overview
========

This chapter states the goals of the design of the machine. A rule in another chapter names
the goal that it serves in its ``parent`` option. The timing invariant comes from section 4.2
of the BCW-2 workflow proposal, revision 12.

Goals
=====

.. goal:: design.timing-invariant

   No protection domain can alter the observed latency of an operation in any other
   protection domain.

Terms
=====

.. definition:: design.protection-domain
   :parent: design.timing-invariant

   A :dfn:`protection domain` is a set of threads and state that the machine keeps apart from
   every other such set.

.. definition:: design.operation
   :parent: design.timing-invariant

   An :dfn:`operation` is an instruction or a request that a protection domain issues.

.. definition:: design.observed-latency
   :parent: design.timing-invariant

   The :dfn:`observed latency` of an operation is the time from its issue to its result, as
   its protection domain can measure that time.
