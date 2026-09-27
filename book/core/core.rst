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
      :stamp: 75abc2dc

      def core_rotate(turn):
          return {'next': (turn + 1) % CORE_THREADS}

.. source:: build/rtl/core/core_rotate.v
   :implements: core.rotation

   module core_rotate (input wire [bcw_params::CORE_TURN_WIDTH-1:0] turn,
                       output wire [bcw_params::CORE_TURN_WIDTH-1:0] next);
       assign next = (turn == bcw_params::CORE_TURN_WIDTH'(bcw_params::CORE_THREADS - 1)) ? '0 : turn + 1'b1;
   endmodule

.. check:: equiv
   :verifies: core.rotation
   :module: core_rotate

.. rationale::

   The order of the turns depends on nothing that a thread does. No thread can therefore
   change the timing of another thread, as :rule:`design.timing-invariant` requires.

Instruction set
===============

.. definition:: core.compressed
   :parent: design.economy

   A :dfn:`compressed instruction` is a 16-bit instruction of the ``C`` extension of ``RISC-V``
   for ``RV32``. One that the extension reserves, or that needs an extension other than ``I``,
   ``M`` and ``C``, is illegal, and expands to ``0x00000013``.

.. requirement:: core.rvc0
   :parent: design.economy

   Where a compressed instruction has ``00`` in its lowest two bits, the core shall
   expand it as the ``C`` extension defines.

   .. twin::
      :stamp: de7eb8be

      def enc_i(imm, rs1, f3, rd, op):
          return ((imm & 4095) << 20) | (rs1 << 15) | (f3 << 12) | (rd << 7) | op
      def enc_s(imm, rs2, rs1, f3):
          low = ((imm >> 5) & 127) << 25
          return low | (rs2 << 20) | (rs1 << 15) | (f3 << 12) | ((imm & 31) << 7) | 35
      def core_rvc0(c):
          f3 = (c >> 13) & 7
          rdp = 8 + ((c >> 2) & 7)
          r1p = 8 + ((c >> 7) & 7)
          spn = ((((c >> 11) & 3) << 4) | (((c >> 7) & 15) << 6)
                 | (((c >> 6) & 1) << 2) | (((c >> 5) & 1) << 3))
          word = ((((c >> 10) & 7) << 3) | (((c >> 6) & 1) << 2)
                  | (((c >> 5) & 1) << 6))
          addi4spn = -1 if spn == 0 else enc_i(spn, 2, 0, rdp, 19)
          code = (addi4spn if f3 == 0 else enc_i(word, r1p, 2, rdp, 3) if f3 == 2
                  else enc_s(word, rdp, r1p, 2) if f3 == 6 else -1)
          bad = code < 0 or (c & 3) != 0
          return {'insn': 19 if bad else code, 'illegal': 1 if bad else 0}

.. source:: build/rtl/core/core_rvc0.v
   :implements: core.rvc0

   module core_rvc0 (input wire [15:0] c, output reg [31:0] insn, output reg illegal);
       <<:core.rv32-formats>>
       localparam OP_IMM = 7'b0010011, OP_LOAD = 7'b0000011, OP_STORE = 7'b0100011;
       wire [4:0]  rdp          = {2'b01, c[4:2]};
       wire [4:0]  r1p          = {2'b01, c[9:7]};
       wire [11:0] imm_addi4spn = {2'b0, c[10:7], c[12:11], c[5], c[6], 2'b0};
       wire [11:0] imm_lwsw     = {5'b0, c[5], c[12:10], c[6], 2'b0};
       always @* begin
           insn    = 32'h00000013;
           illegal = 1'b0;
           if (c[1:0] != 2'b00) illegal = 1'b1;
           else case (c[15:13])
               3'b000: if (c[12:5] == 8'b0) illegal = 1'b1;                   // reserved
                       else insn = enc_i(imm_addi4spn, 5'd2, 3'b000, rdp, OP_IMM);
               3'b010: insn = enc_i(imm_lwsw, r1p, 3'b010, rdp, OP_LOAD);    // c.lw
               3'b110: insn = enc_s(imm_lwsw, rdp, r1p, 3'b010, OP_STORE);   // c.sw
               default: illegal = 1'b1;                                     // F, D, reserved
           endcase
           if (illegal) insn = 32'h00000013;
       end
   endmodule

.. check:: equiv
   :verifies: core.rvc0
   :module: core_rvc0

.. requirement:: core.rvc1
   :parent: design.economy

   Where a compressed instruction has ``01`` in its lowest two bits, the core shall
   expand it as the ``C`` extension defines.

   .. twin::
      :stamp: d1d13581

      def enc_i(imm, rs1, f3, rd, op):
          return ((imm & 4095) << 20) | (rs1 << 15) | (f3 << 12) | (rd << 7) | op
      def enc_r(f7, rs2, rs1, f3, rd, op):
          return (f7 << 25) | (rs2 << 20) | enc_i(0, rs1, f3, rd, op)
      def enc_b(imm, rs1, f3):
          high = (((imm >> 12) & 1) << 6) | ((imm >> 5) & 63)
          low = (((imm >> 1) & 15) << 1) | ((imm >> 11) & 1)
          return enc_r(high, 0, rs1, f3, low, 99)
      def enc_j(imm, rd):
          high = (((imm >> 20) & 1) << 19) | (((imm >> 1) & 1023) << 9)
          field = high | (((imm >> 11) & 1) << 8) | ((imm >> 12) & 255)
          return (field << 12) | (rd << 7) | 111
      def core_rvc1(c):
          f3 = (c >> 13) & 7
          b12 = (c >> 12) & 1
          rd = (c >> 7) & 31
          rdp = 8 + ((c >> 2) & 7)
          r1p = 8 + ((c >> 7) & 7)
          six = (b12 << 5) | ((c >> 2) & 31)
          imm = six - 64 * b12
          jump = ((b12 << 11) | (((c >> 11) & 1) << 4) | (((c >> 9) & 3) << 8)
                  | (((c >> 8) & 1) << 10) | (((c >> 7) & 1) << 6)
                  | (((c >> 6) & 1) << 7) | (((c >> 3) & 7) << 1)
                  | (((c >> 2) & 1) << 5)) - 4096 * b12
          sp16 = ((b12 << 9) | (((c >> 6) & 1) << 4) | (((c >> 5) & 1) << 6)
                  | (((c >> 3) & 3) << 7) | (((c >> 2) & 1) << 5))
          branch = ((b12 << 8) | (((c >> 10) & 3) << 3) | (((c >> 5) & 3) << 6)
                    | (((c >> 3) & 3) << 1) | (((c >> 2) & 1) << 5)) - 512 * b12
          addi16sp = -1 if sp16 == 0 else enc_i(sp16 - 1024 * b12, 2, 0, 2, 19)
          lui = -1 if six == 0 else ((imm & 1048575) << 12) | (rd << 7) | 55
          funct2 = (c >> 10) & 3
          funct = (c >> 5) & 3
          arith_f3 = 0 if funct == 0 else 4 if funct == 1 else 4 + funct
          arith = enc_r(32 if funct == 0 else 0, rdp, r1p, arith_f3, r1p, 51)
          shamt = (1024 if funct2 == 1 else 0) | ((c >> 2) & 31)
          shift = enc_i(shamt, r1p, 5, r1p, 19)
          alu = (enc_i(imm, r1p, 7, r1p, 19) if funct2 == 2 else -1 if b12 == 1
                 else shift if funct2 < 2 else arith)
          code = (enc_i(imm, rd, 0, rd, 19) if f3 == 0 else enc_j(jump, 1) if f3 == 1
                  else enc_i(imm, 0, 0, rd, 19) if f3 == 2
                  else (addi16sp if rd == 2 else lui) if f3 == 3 else alu if f3 == 4
                  else enc_j(jump, 0) if f3 == 5 else enc_b(branch, r1p, f3 - 6))
          bad = code < 0 or (c & 3) != 1
          return {'insn': 19 if bad else code, 'illegal': 1 if bad else 0}

.. source:: build/rtl/core/core_rvc1.v
   :implements: core.rvc1

   module core_rvc1 (input wire [15:0] c, output reg [31:0] insn, output reg illegal);
       <<:core.rv32-formats>>
       localparam OP_IMM = 7'b0010011, OP_REG = 7'b0110011, OP_LUI = 7'b0110111,
                  OP_JAL = 7'b1101111, OP_BR = 7'b1100011;
       wire [4:0]  rd_full      = c[11:7];
       wire [4:0]  r1p          = {2'b01, c[9:7]};
       wire [4:0]  rdp          = {2'b01, c[4:2]};
       wire [11:0] imm_ci       = {{7{c[12]}}, c[6:2]};
       wire [11:0] imm_addi16sp = {{3{c[12]}}, c[4:3], c[5], c[2], c[6], 4'b0};
       wire [5:0]  shamt        = {c[12], c[6:2]};
       wire [20:1] imm_cj = {{10{c[12]}}, c[8], c[10:9], c[6], c[7], c[2], c[11], c[5:3]};
       wire [12:1] imm_cb = {{5{c[12]}}, c[6:5], c[2], c[11:10], c[4:3]};
       always @* begin
           insn    = 32'h00000013;
           illegal = 1'b0;
           if (c[1:0] != 2'b01) illegal = 1'b1;
           else case (c[15:13])
               3'b000: insn = enc_i(imm_ci, rd_full, 3'b000, rd_full, OP_IMM);      // c.addi
               3'b001: insn = enc_j(imm_cj, 5'd1, OP_JAL);                          // c.jal
               3'b010: insn = enc_i(imm_ci, 5'd0, 3'b000, rd_full, OP_IMM);         // c.li
               3'b011: if ({c[12], c[6:2]} == 6'b0) illegal = 1'b1;                 // reserved
                       else if (rd_full == 5'd2)                                    // c.addi16sp
                           insn = enc_i(imm_addi16sp, 5'd2, 3'b000, 5'd2, OP_IMM);
                       else insn = {{15{c[12]}}, c[6:2], rd_full, OP_LUI};          // c.lui
               3'b100: case (c[11:10])
                   2'b00: if (c[12]) illegal = 1'b1;                                // c.srli
                          else insn = enc_i({6'b0, shamt}, r1p, 3'b101, r1p, OP_IMM);
                   2'b01: if (c[12]) illegal = 1'b1;                                // c.srai
                          else insn = enc_i({6'b010000, shamt}, r1p, 3'b101, r1p, OP_IMM);
                   2'b10: insn = enc_i(imm_ci, r1p, 3'b111, r1p, OP_IMM);           // c.andi
                   2'b11: if (c[12]) illegal = 1'b1;                                // RV64 only
                          else case (c[6:5])
                       2'b00: insn = enc_r(7'b0100000, rdp, r1p, 3'b000, r1p, OP_REG);  // sub
                       2'b01: insn = enc_r(7'b0000000, rdp, r1p, 3'b100, r1p, OP_REG);  // xor
                       2'b10: insn = enc_r(7'b0000000, rdp, r1p, 3'b110, r1p, OP_REG);  // or
                       2'b11: insn = enc_r(7'b0000000, rdp, r1p, 3'b111, r1p, OP_REG);  // and
                   endcase
               endcase
               3'b101: insn = enc_j(imm_cj, 5'd0, OP_JAL);                          // c.j
               3'b110: insn = enc_b(imm_cb, 5'd0, r1p, 3'b000, OP_BR);              // c.beqz
               3'b111: insn = enc_b(imm_cb, 5'd0, r1p, 3'b001, OP_BR);              // c.bnez
           endcase
           if (illegal) insn = 32'h00000013;
       end
   endmodule

.. check:: equiv
   :verifies: core.rvc1
   :module: core_rvc1

.. requirement:: core.rvc2
   :parent: design.economy

   Where a compressed instruction has ``10`` in its lowest two bits, the core shall
   expand it as the ``C`` extension defines.

   .. twin::
      :stamp: 5038c648

      def enc_i(imm, rs1, f3, rd, op):
          return ((imm & 4095) << 20) | (rs1 << 15) | (f3 << 12) | (rd << 7) | op
      def enc_r(rs2, rs1, rd):
          return (rs2 << 20) | enc_i(0, rs1, 0, rd, 51)
      def core_rvc2(c):
          f3 = (c >> 13) & 7
          b12 = (c >> 12) & 1
          rd = (c >> 7) & 31
          rs2 = (c >> 2) & 31
          lwsp = (b12 << 5) | (((c >> 4) & 7) << 2) | (((c >> 2) & 3) << 6)
          swsp = (((c >> 9) & 15) << 2) | (((c >> 7) & 3) << 6)
          store = (((swsp >> 5) & 127) << 25) | (rs2 << 20) | (2 << 15) | (2 << 12)
          jr = -1 if rd == 0 else enc_i(0, rd, 0, 0, 103)
          low = jr if rs2 == 0 else enc_r(rs2, 0, rd)
          high = ((1048691 if rd == 0 else enc_i(0, rd, 0, 1, 103)) if rs2 == 0 else
                  enc_r(rs2, rd, rd))
          code = ((-1 if b12 == 1 else enc_i(rs2, rd, 1, rd, 19)) if f3 == 0 else
                  (-1 if rd == 0 else enc_i(lwsp, 2, 2, rd, 3)) if f3 == 2 else
                  (high if b12 == 1 else low) if f3 == 4 else
                  store | ((swsp & 31) << 7) | 35 if f3 == 6 else -1)
          bad = code < 0 or (c & 3) != 2
          return {'insn': 19 if bad else code, 'illegal': 1 if bad else 0}

.. source:: build/rtl/core/core_rvc2.v
   :implements: core.rvc2

   module core_rvc2 (input wire [15:0] c, output reg [31:0] insn, output reg illegal);
       <<:core.rv32-formats>>
       localparam OP_IMM = 7'b0010011, OP_REG = 7'b0110011, OP_LOAD = 7'b0000011,
                  OP_STORE = 7'b0100011, OP_JALR = 7'b1100111;
       wire [4:0]  rd_full  = c[11:7];
       wire [4:0]  rs2_full = c[6:2];
       wire [5:0]  shamt    = {c[12], c[6:2]};
       wire [11:0] imm_lwsp = {4'b0, c[3:2], c[12], c[6:4], 2'b0};
       wire [11:0] imm_swsp = {4'b0, c[8:7], c[12:9], 2'b0};
       always @* begin
           insn    = 32'h00000013;
           illegal = 1'b0;
           if (c[1:0] != 2'b10) illegal = 1'b1;
           else case (c[15:13])
               3'b000: if (c[12]) illegal = 1'b1;                                   // RV32: shamt[5]
                       else insn = enc_i({6'b0, shamt}, rd_full, 3'b001, rd_full, OP_IMM);
               3'b010: if (rd_full == 5'd0) illegal = 1'b1;                         // c.lwsp
                       else insn = enc_i(imm_lwsp, 5'd2, 3'b010, rd_full, OP_LOAD);
               3'b100: if (!c[12] && rs2_full == 5'd0 && rd_full == 5'd0)
                           illegal = 1'b1;                                          // reserved
                       else if (!c[12] && rs2_full == 5'd0)                         // c.jr
                           insn = enc_i(12'b0, rd_full, 3'b000, 5'd0, OP_JALR);
                       else if (!c[12])                                             // c.mv
                           insn = enc_r(7'b0, rs2_full, 5'd0, 3'b000, rd_full, OP_REG);
                       else if (rs2_full == 5'd0 && rd_full == 5'd0)
                           insn = 32'h00100073;                                     // c.ebreak
                       else if (rs2_full == 5'd0)                                   // c.jalr
                           insn = enc_i(12'b0, rd_full, 3'b000, 5'd1, OP_JALR);
                       else insn = enc_r(7'b0, rs2_full, rd_full, 3'b000, rd_full, OP_REG); // c.add
               3'b110: insn = enc_s(imm_swsp, rs2_full, 5'd2, 3'b010, OP_STORE);    // c.swsp
               default: illegal = 1'b1;                                             // F, D
           endcase
           if (illegal) insn = 32'h00000013;
       end
   endmodule

.. check:: equiv
   :verifies: core.rvc2
   :module: core_rvc2

.. source:: :core.rv32-formats

   function [31:0] enc_i(input [11:0] imm_f, input [4:0] rs1_f,
                         input [2:0] fn3, input [4:0] rd_f, input [6:0] op_f);
       enc_i = {imm_f, rs1_f, fn3, rd_f, op_f};
   endfunction
   function [31:0] enc_s(input [11:0] imm_f, input [4:0] rs2_f, input [4:0] rs1_f,
                         input [2:0] fn3, input [6:0] op_f);
       enc_s = {imm_f[11:5], rs2_f, rs1_f, fn3, imm_f[4:0], op_f};
   endfunction
   function [31:0] enc_r(input [6:0] f7_f, input [4:0] rs2_f, input [4:0] rs1_f,
                         input [2:0] fn3, input [4:0] rd_f, input [6:0] op_f);
       enc_r = {f7_f, rs2_f, rs1_f, fn3, rd_f, op_f};
   endfunction
   function [31:0] enc_b(input [12:1] imm_f, input [4:0] rs2_f, input [4:0] rs1_f,
                         input [2:0] fn3, input [6:0] op_f);
       enc_b = {imm_f[12], imm_f[10:5], rs2_f, rs1_f, fn3, imm_f[4:1], imm_f[11], op_f};
   endfunction
   function [31:0] enc_j(input [20:1] imm_f, input [4:0] rd_f, input [6:0] op_f);
       enc_j = {imm_f[20], imm_f[10:1], imm_f[11], imm_f[19:12], rd_f, op_f};
   endfunction

.. rationale::

   A stock instruction set adds no concept and brings a toolchain that works. The ``C``
   extension makes code smaller, which eases the pressure on the memory pool.
