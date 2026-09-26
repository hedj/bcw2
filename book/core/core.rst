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

.. parameter:: core.threads
   :parent: core.core
   :value: 8

   The number of threads that the core runs.

.. parameter:: core.turn-width
   :parent: core.threads
   :value: clog2(core.threads)
   :unit: bits

   The width of the index of a thread.

.. parameter:: core.clock
   :parent: core.core
   :value: 110 * 10 ** 6
   :unit: Hz

   The number of cycles in a second.

.. target:: core.timing-closure
   :parent: core.clock
   :value: core.clock
   :unit: Hz

   The core satisfies timing closure at :param:`core.clock`.

.. requirement:: core.rotation
   :parent: design.timing-invariant

   The core shall give the turn after thread ``t`` to thread ``t + 1``, modulo
   :param:`core.threads`.

   .. twin::
      :file: build/model/core_rotate.py
      :stamp: 75abc2dc

      from bcw_params import CORE_THREADS


      def core_rotate(turn):
          return {'next': (turn + 1) % CORE_THREADS}

.. source:: build/rtl/core/core_rotate.v
   :implements: core.rotation

   module core_rotate (input wire [bcw_params::CORE_TURN_WIDTH-1:0] turn,
                       output wire [bcw_params::CORE_TURN_WIDTH-1:0] next);
       assign next = (turn == bcw_params::CORE_TURN_WIDTH'(bcw_params::CORE_THREADS - 1)) ? '0 : turn + 1'b1;
   endmodule

.. rationale::

   The order of the turns depends on nothing that a thread does. No thread can therefore
   change the timing of another thread, as :rule:`design.timing-invariant` requires.
