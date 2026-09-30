:kind: reference

======
Memory
======

Overview
========

The memory of the machine has two parts. Only the supervisor reaches the supervisor part, and
the region of each other protection domain lies in the worker part.

Parts
=====

.. definition:: memory.supervisor
   :parent: design.supervisor

   The :dfn:`supervisor part` is the memory that only the supervisor reaches.

.. definition:: memory.workers
   :parent: design.region

   The :dfn:`worker part` is the memory that holds the region of each other protection domain.

.. parameter:: memory.supervisor-part
   :parent: memory.supervisor
   :value: 2 ** 14
   :unit: bytes

   The size of the supervisor part.

.. parameter:: memory.worker-part
   :parent: memory.workers
   :value: 2 ** 16
   :unit: bytes

   The size of the worker part.

.. parameter:: memory.part-width
   :parent: memory.worker-part
   :value: clog2(memory.worker-part)
   :unit: bits

   The width of an address in the worker part, which also holds an address in the supervisor part.

.. rationale::

   Each size is a power of two, so an address wraps in its part with no compare. The worker part
   holds more than the 48 kB of BCW-1, and both parts fit in the block memory of the chip.
