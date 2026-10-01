:kind: reference

======
Design
======

Overview
========

This chapter states the goals of the design of the machine. A rule in another chapter names
the goal that it serves in its ``parent`` option. The purpose is a single-user workstation.
Four goals serve it, in a fixed order, and the security properties serve the first of them.
The four goals and the properties come from sections 1 and 4 of the BCW-1 design rationale,
``DOC-BCW1-01-RATH``. The timing invariant comes from section 4.2 of the BCW-2 workflow
proposal, revision 12.

Goals
=====

.. goal:: design.workstation

   The machine is a workstation for one user. It runs programs that hostile third parties
   wrote, and no such program can harm the user or another program.

.. goal:: design.auditability
   :parent: design.workstation

   Each security property rests on a structural fact about the hardware, not on a check
   that can be wrong. One engineer can read all of the hardware and the operating system.
   This goal comes first.

.. definition:: design.mechanism

   A :dfn:`mechanism` is a structure or a procedure that a reader learns in order to build,
   check or operate the machine.

.. goal:: design.economy
   :parent: design.workstation

   The machine has the fewest distinct mechanisms, counted across the hardware, the
   operating system and the discipline of the programs of the user. This goal comes second.

.. goal:: design.latency
   :parent: design.workstation

   The time from an input event, or from a change that a program makes to the display, to the
   light of the display is as short as physics allows. This goal comes third.

.. goal:: design.throughput
   :parent: design.workstation

   The machine does as much work as it can without harm to an earlier goal. This goal comes
   last.

.. rationale::

   The goals conflict, so their order decides. A faster machine with one more mechanism to
   check is worse than a slower machine without it. Waiting recovers throughput, but nothing
   recovers latency.

Terms
=====

.. definition:: design.thread

   A :dfn:`thread` is a stream of instructions with its own registers and program counter.

.. definition:: design.protection-domain
   :parent: design.auditability

   A :dfn:`protection domain` is a set of threads and state that the machine keeps apart from
   every other such set.

.. definition:: design.operation
   :parent: design.auditability

   An :dfn:`operation` is an instruction or a request that a protection domain issues.

.. definition:: design.observed-latency
   :parent: design.auditability

   The :dfn:`observed latency` of an operation is the time from its issue to its result, as
   its protection domain can measure that time.

.. definition:: design.handle
   :parent: design.auditability

   A :dfn:`handle` is a number that names a resource that its holder does not own. It means an
   entry in the table of its holder, and nothing else.

.. definition:: design.region
   :parent: design.auditability

   The :dfn:`region` of a protection domain is the memory that it addresses directly: a base
   and a bound.

.. definition:: design.supervisor
   :parent: design.auditability

   The :dfn:`supervisor` is the protection domain that holds the root authority of the
   machine.

Security properties
===================

.. goal:: design.isolation
   :parent: design.auditability

   A protection domain that holds no handle can reach nothing outside its region. It has no
   means to reach further, so the machine has no mode that it can fail to enter.

.. open:: What memory returns

   The core reads data at a fixed stage and has no input that makes it wait, so the time of an
   access depends only on its own thread. The value is not settled: what memory returns at the
   port of a thread must depend only on the requests of that thread and on the memory that its
   protection domain can read. The memory chapter will state this as a requirement.

.. goal:: design.unforgeable
   :parent: design.auditability

   The table of its holder alone makes a handle valid. A protection domain that makes,
   changes or copies the bits of a handle names only an entry that it already holds. No part
   of the machine carries tag bits.

.. goal:: design.revocation
   :parent: design.auditability

   One write to the entry of a handle revokes the handle. No holder of the handle needs to be
   found, told or trusted.

.. definition:: design.external-clock
   :parent: design.auditability

   An :dfn:`external clock` is an input from outside the machine that gives a protection
   domain a measure of real time, such as the time at which data comes from another machine.
   Such an input is work for the operating system, not for the hardware.

.. goal:: design.timing-invariant
   :parent: design.auditability

   Between protection domains that have no external clock, no protection domain can change
   the observed latency of an operation in another.

.. goal:: design.no-clock
   :parent: design.auditability

   No protection domain other than the supervisor can read a clock, or a count of cycles or
   of instructions. It relates itself to real time only by a request that suspends it for at
   least an interval that it states.

Audit budget
============

.. definition:: design.audit-time
   :parent: design.auditability

   The :dfn:`audit time` of the book is the number of days that one engineer takes to check
   all of it. The engineer checks 300 words of prose or 300 lines of code in an hour, for 4
   hours in a day.

.. target:: design.audit-budget
   :parent: design.auditability
   :value: 40
   :unit: days

   The audit time of the book is at most :param:`design.audit-budget`.

.. target:: design.hardware-audit-budget
   :parent: design.auditability
   :value: 7
   :unit: days

   The audit time of the book without its parts on the operating system is at most
   :param:`design.hardware-audit-budget`.

.. rationale::

   The rates come from studies of inspection, and four hours is the limit of focused work in a
   day. The whole budget is preliminary: half of the 84 days of Project Oberon at these rates keeps
   it meaningfully small.
