:kind: reference

====
Core
====

Overview
========

The core runs every thread of the machine through one pipeline. The threads take turns in a
fixed order, so no thread can change when another thread gets its turn.

Rotation
========

.. definition:: core.core
   :parent: design.timing-invariant

   The :dfn:`core` is the part of the machine that issues the instructions of every thread.

.. definition:: core.thread
   :parent: core.core

   A :dfn:`thread` is a stream of instructions with its own registers and program counter.

.. definition:: core.turn
   :parent: core.core

   A :dfn:`turn` is a cycle in which the core issues an instruction of one thread.

.. requirement:: core.rotation
   :parent: design.timing-invariant

   The core shall give the turn after thread ``t`` to thread ``t + 1``, modulo the
   thread count.

   .. twin::
      :file: build/model/core_rotate.py
      :stamp: e5e30131

      def core_rotate(turn):
          return {'next': turn + 1}

.. source:: build/rtl/core/core_rotate.v
   :implements: core.rotation

   module core_rotate (input wire [2:0] turn, output wire [2:0] next);
       assign next = turn + 3'd1;
   endmodule

.. rationale::

   The order of the turns depends on nothing that a thread does. No thread can therefore
   change the timing of another thread, as :rule:`design.timing-invariant` requires.
